#!/usr/bin/env bash
# Sets up the Planter 3000 MQTT broker on a Raspberry Pi.
# Run on the broker Pi (Rot, 172.16.33.53) from inside the broker directory:
#   sudo bash setup.sh
# Safe to run again: it overwrites config, ACL and password file with the versions from this directory.

set -euo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"
PASSWORD="${PLANTER_PASSWORD:-planter}"
USERS=(admin server room plant)

if [[ $EUID -ne 0 ]]; then
    echo "Please run as root: sudo bash setup.sh" >&2
    exit 1
fi

echo "==> Installing mosquitto"
apt-get update
apt-get install -y mosquitto mosquitto-clients

echo "==> Installing config and ACL"
install -o root -g root -m 644 "$DIR/planter3000.conf" /etc/mosquitto/conf.d/planter3000.conf
install -o mosquitto -g mosquitto -m 600 "$DIR/acl" /etc/mosquitto/acl

echo "==> Creating MQTT users: ${USERS[*]}"
rm -f /etc/mosquitto/passwd
touch /etc/mosquitto/passwd
for user in "${USERS[@]}"; do
    mosquitto_passwd -b /etc/mosquitto/passwd "$user" "$PASSWORD"
done
chown mosquitto:mosquitto /etc/mosquitto/passwd
chmod 600 /etc/mosquitto/passwd

echo "==> Starting mosquitto service"
systemctl enable mosquitto
systemctl restart mosquitto
sleep 2

if ! systemctl is-active --quiet mosquitto; then
    echo "!! mosquitto did not start, last log lines:" >&2
    journalctl -u mosquitto -n 30 --no-pager >&2
    exit 1
fi

echo "==> Self-test: publish/subscribe as admin"
received="$(mosquitto_sub -h localhost -u admin -P "$PASSWORD" -t planter3000/selftest -C 1 -W 5 & \
            sleep 1; \
            mosquitto_pub -h localhost -u admin -P "$PASSWORD" -t planter3000/selftest -m ok; \
            wait)" || true
if [[ "$received" == "ok" ]]; then
    echo "    OK"
else
    echo "!! self-test failed (no message received)" >&2
    exit 1
fi

echo
echo "Broker is running on:"
ss -tln | grep ':1883' || true
echo
echo "IP address(es): $(hostname -I)"
echo "Users: ${USERS[*]}"
echo "Watch all traffic:  mosquitto_sub -h localhost -u admin -P $PASSWORD -t '#' -v"
echo "Broker log:         sudo tail -f /var/log/mosquitto/mosquitto.log"
