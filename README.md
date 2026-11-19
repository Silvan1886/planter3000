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
	
	
Webinterface mit Prometheus / Graphana
	"Server" sendet Daten über Opentelemetry an ein Grafana Dashboard welches auf dem Server gehostet ist. 
	
