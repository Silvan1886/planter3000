Planter 3000: 

Raspberry Pis: 

Rot:        172.16.33.53 / b8:27:eb:f2:be:e7    (Nicht von Kit 4)
Violet:     172.16.33.30 / b8:27:eb:51:a7:12 
Schwarz 1:  172.16.32.187 / b8:27:eb:6b:fb:c2 	 
Schwarz 2:  172.16.32.170 / b8:27:eb:89:6b:85 	

Grundidee: 
- Feuchtigkeitssensoren im Pflanzentopf und bei zu wenig Feuchtigkeit wird mit einer Pumpe Wasser gegeben. 

- Pro Pflanze 1 Raspy der Feuchtigkeitssensor und Pumpe kontrolliert
	Daten werden über MQTT an den "Server" geschickt. 
	Der Server entscheidet basierend auf seinen Daten ob Wasser gegeben werden muss. 
	
- Pro Raum 1 Raspy der die Luftfeuchtigkeit und Temperatur ausliest. 
	Daten werden auch über MQTT an den "Server" geschickt. 
	Daten beinflussen evtl. Entscheidung ob Wasser gegeben wird. 
	
- Pro Anlage 1 "Server" der die Daten empfängt.
	Sendet Wassergeben Request.
	Stellt Daten in Webinterface dar.
		Evtl. Vibecode oder Opentelemetry

- MQTT Broker
	ZHAW Mqtt Broker

Material: 
- Mind. 4 Raspberry Pis
- 2x Feuchtigkeitssensor
- 2x Pumpe + Behälter
- 1x Lichtsensor
- 1x Temperatursensor
- 1x Luftfeuchtigkeitssensor
	
	
MQTT Topics

Daten an Server schicken: 
```
	planter3000/{roomNr}/{plantNr}/soilSensor
	planter3000/{roomNr}/{plantNr}/onFire
	planter3000/{roomNr}/roomSensorData
```

server subscribes to:
	
```
	planter3000/+/roomSensorData
	planter3000/+/+/soilSensor
	planter3000/+/+/onFire
```
	
	
Server schickt Daten: 
	planter3000/{roomNr}/{plantNr}/waterPlant
	
	
Webinterface mit Prometheus / Grafana
	"Server" sendet Daten über Opentelemetry an ein Grafana Dashboard welches auf dem Server gehostet ist. 


## Server Setup

Der Server ist die Python-Anwendung in `server/`. Er abonniert die MQTT-Topics und exportiert Server- und Sensormetriken per OTLP an Prometheus.

Voraussetzungen:
- Python 3
- Erreichbarer MQTT-Broker (IP in `server/main.py` unter `BROKER_IP` anpassen)
- Prometheus mit OTLP-Receiver
- Grafana mit Prometheus als Datenquelle

Starten:
```bash
cd server
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 main.py
```

Prometheus mit OTLP-Receiver starten (unterstützt ab Version 2.47):
```bash
# Prometheus 3.x
prometheus --config.file=prometheus.yml --web.enable-otlp-receiver

# Prometheus 2.47 - 2.55
prometheus --config.file=prometheus.yml --enable-feature=otlp-write-receiver
```

Ältere Versionen (z. B. das Debian-Paket 2.42) unterstützen OTLP nicht und müssen aktualisiert werden.

`--config.file` verweist auf die Prometheus-Konfiguration (Standard: `prometheus.yml` im aktuellen Verzeichnis). Für den Planter3000 sind keine Scrape-Jobs nötig, da die Metriken per OTLP gepusht werden; eine minimale Datei reicht:
```yaml
global:
  scrape_interval: 15s
```

Die Metriken werden alle 10 Sekunden an `http://localhost:9090/api/v1/otlp/v1/metrics` gesendet; die URL kann mit `OTEL_EXPORTER_OTLP_METRICS_ENDPOINT` überschrieben werden.

Links (auf dem Server; von anderen Geräten `localhost` durch die Server-IP ersetzen):
- Prometheus: <http://localhost:9090>
- Grafana: <http://localhost:3000>

In Grafana Prometheus als Datenquelle mit der URL `http://localhost:9090` eintragen. In Prometheus erscheinen z. B. `planter3000_mqtt_connected`, `planter3000_mqtt_messages_received_total` und – sobald Sensordaten eintreffen – pro Sensorfeld Gauges wie `planter3000_telemetry_soil_sensor_moisture` mit den Labels `room` und `plant`.

