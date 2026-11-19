# Planter 3000 – MQTT Broker

Mosquitto broker on **Rot (172.16.33.53)**. All other Pis connect to it as MQTT clients on port `1883`.

| File | Installed on the Pi as | Purpose |
|---|---|---|
| `planter3000.conf` | `/etc/mosquitto/conf.d/planter3000.conf` | Listener, authentication, ACL, logging |
| `acl` | `/etc/mosquitto/acl` | Which user may read/write which topic |
| `setup.sh` | – | Installs mosquitto, copies the files, creates the users, starts and tests the broker |

## Users

Every Pi logs in with its own user. Password for all: `planter`.

| User | Pi | Allowed |
|---|---|---|
| `admin` | Rot (broker) | read/write everything (debugging) |
| `server` | Violet | read `planter3000/#`, write `planter3000/+/+/waterPlant` |
| `room` | Schwarz 1 | write `planter3000/1/roomSensorData` |
| `plant` | Schwarz 2 | write `planter3000/1/+/soilSensor`, `planter3000/1/+/onFire`, read `planter3000/1/+/waterPlant` |
| all | – | write own status `planter3000/status/<user>` (`online` / `offline`, retained, Last Will) |

Anything not listed in `acl` is denied.

## Setup

**1. Copy this directory to the broker Pi** (from the `planter3000` folder on your PC):

```bash
scp -r broker pi@172.16.33.53:~/planter-broker
```

(or `git clone` the repo directly on the Pi)

**2. Run the setup script on the Pi:**

```bash
ssh pi@172.16.33.53
cd ~/planter-broker
sudo bash setup.sh
```

The script ends with a self-test that prints `OK`, then shows that the broker listens on `0.0.0.0:1883`.
Run it again after every change to `planter3000.conf` or `acl`.

To use a different password: `sudo PLANTER_PASSWORD=<pw> bash setup.sh`

## Test

On the broker, watch all traffic:

```bash
mosquitto_sub -h localhost -u admin -P planter -t '#' -v
```

From another Pi (needs `sudo apt install mosquitto-clients`):

```bash
# Plant Pi: allowed -> appears in the subscriber
mosquitto_pub -h 172.16.33.53 -u plant -P planter -t planter3000/1/1/soilSensor -m '{"moisture": 42}'

# Plant Pi: not allowed -> does NOT appear (ACL denies it)
mosquitto_pub -h 172.16.33.53 -u plant -P planter -t planter3000/1/1/waterPlant -m '{"seconds": 3}'

# Wrong password -> "Connection error: Not authorized"
mosquitto_pub -h 172.16.33.53 -u plant -P wrong -t planter3000/test -m x
```

From Python (`pip install paho-mqtt`):

```python
import paho.mqtt.client as mqtt

client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="planter-plant")
client.username_pw_set("plant", "planter")
client.will_set("planter3000/status/plant", "offline", qos=1, retain=True)
client.connect("172.16.33.53", 1883, keepalive=30)
client.publish("planter3000/status/plant", "online", qos=1, retain=True)
```

## Operation

| Task | Command |
|---|---|
| Status | `sudo systemctl status mosquitto` |
| Restart | `sudo systemctl restart mosquitto` |
| Live log | `sudo tail -f /var/log/mosquitto/mosquitto.log` |
| Error on start | `sudo journalctl -u mosquitto -n 30` |
| Is it listening? | `sudo ss -tlnp \| grep 1883` |

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `Connection refused` from other Pis | Broker not running or `listener 1883 0.0.0.0` missing → run `setup.sh` again |
| Connection times out, but ping works | Port 1883 blocked in the network |
| `Not authorized` | Wrong user/password |
| Connected, but messages don't arrive | ACL denies the topic (MQTT 3.1.1 drops it silently) → check `acl` and the broker log |
| Broker doesn't start after a change | Typo in `planter3000.conf`/`acl` → `journalctl -u mosquitto -n 30` |
| Two clients keep disconnecting each other | Same `client_id` used twice → make it unique per Pi |
| `setup.sh: $'\r': command not found` | File has Windows line endings → `sed -i 's/\r$//' setup.sh acl planter3000.conf` |
