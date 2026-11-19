#!/usr/bin/env python3

r"""

    File:          main.py

    Purpose:       MQTT client for the Planter3000 server.
                   It subscribes to the sensor topics described
                   in README.md and exports server and sensor
                   metrics over OTLP to the local Prometheus.


    Remarks:       - This application uses the paho-mqtt module:

                       pip install paho-mqtt

                   - Metrics are exported with the OpenTelemetry SDK,
                     see telemetry.py for the configuration.

"""

import json
import sys
import time

import paho.mqtt.client as mqtt

from telemetry import Telemetry

# paho-mqtt 2.x introduced a callback API with more arguments. Use it when
# available; on paho-mqtt 1.x the callbacks below also work, because the
# extra parameters default to None.
try:
    from paho.mqtt.enums import CallbackAPIVersion
except ImportError:  # paho-mqtt 1.x
    CLIENT_KWARGS = {}
else:
    CLIENT_KWARGS = { "callback_api_version": CallbackAPIVersion.VERSION2 }


# MQTT related globals
BROKER_IP            = "172.16.32.5"
BROKER_PORT          = int( 1883 )
CONNECTION_KEEPALIVE = int(   60 ) # unit is seconds
QUALITY_OF_SERVICE   = int(    0 )

# Topics of the Planter3000 system (see README.md)
TOPIC_PREFIX = "planter3000"
SUBSCRIPTIONS = [
  ( TOPIC_PREFIX + "/+/roomSensorData", QUALITY_OF_SERVICE ),
  ( TOPIC_PREFIX + "/+/+/soilSensor",   QUALITY_OF_SERVICE ),
  ( TOPIC_PREFIX + "/+/+/onFire",       QUALITY_OF_SERVICE ),
]


# Every publisher/subscriber requires
# a mqtt client instance.
def setup_mqtt_client( local_ip = "" ):

  mqtt_client = mqtt.Client( **CLIENT_KWARGS )
  mqtt_client.on_connect = on_mqtt_connect
  mqtt_client.on_publish = on_mqtt_publish
  mqtt_client.on_disconnect = on_mqtt_disconnect
  mqtt_client.on_message = on_mqtt_message

  try:
    mqtt_client.connect( BROKER_IP,
                         BROKER_PORT,
                         CONNECTION_KEEPALIVE,
                         local_ip )
  except OSError:
    print( "could not establish connection to broker with ip : " + BROKER_IP,
           file = sys.stderr )
    sys.exit( 1 )

  # Only start the metrics exporter once the broker is reachable, so a
  # failed startup does not wait for metrics export retries.
  server_telemetry = Telemetry()
  mqtt_client.user_data_set( server_telemetry )

  mqtt_client.loop_start()

  return mqtt_client, server_telemetry


# functions where the instance of the mqtt client points on
def on_mqtt_publish( client, userdata, mid, reason_code = None, properties = None ):
  print( "MQTT client successfully published a message to broker " + BROKER_IP )


def on_mqtt_connect( client, userdata, flags, rc, properties = None ):
  print( "connected to broker with result code: " + str( rc ) )
  if rc != 0:
    return

  userdata.record_mqtt_connect()
  client.subscribe( SUBSCRIPTIONS )


def on_mqtt_disconnect( client, userdata, *args ):
  # Callback API version 1 passes (rc), version 2 passes
  # (disconnect_flags, reason_code, properties).
  rc = args[1] if len( args ) == 3 else args[0]
  if rc != 0:
    print( "Unexpected disconnection." )
  else:
    print( "MQTT client disconnected without errors." )
  userdata.record_mqtt_disconnect( unexpected = ( rc != 0 ) )


def on_mqtt_message( client, userdata, msg ):
  parsed_topic = parse_topic( msg.topic )
  if parsed_topic is None:
    return

  kind, room, plant = parsed_topic
  userdata.record_message( kind )

  measurements = parse_measurements( msg.payload )
  if measurements is None:
    print( "could not parse payload on topic " + msg.topic )
    userdata.record_invalid_message( kind )
    return

  for field, value in measurements:
    userdata.record_reading( kind, field, value, room, plant )


# topic and payload parsing
def parse_topic( topic ):
  """Return (kind, room, plant) for a known telemetry topic, else None."""
  parts = topic.split( "/" )
  if len( parts ) == 3 and parts[0] == TOPIC_PREFIX \
     and parts[2] == "roomSensorData":
    return parts[2], parts[1], None
  if len( parts ) == 4 and parts[0] == TOPIC_PREFIX \
     and parts[3] in ( "soilSensor", "onFire" ):
    return parts[3], parts[1], parts[2]
  return None


def parse_measurements( payload ):
  """Extract (field, value) pairs from a JSON payload.

  Supports a plain JSON object (nested objects are flattened), a bare
  number or boolean, and SenML JSON with an "e" list (as used in lab 4).
  Returns None if the payload is not valid JSON.
  """
  try:
    data = json.loads( payload )
  except ValueError:
    return None

  measurements = [ ]
  collect_measurements( data, measurements )
  return measurements


def collect_measurements( data, measurements, field = None ):
  if isinstance( data, dict ):
    if isinstance( data.get( "e" ), list ):  # SenML record
      for entry in data[ "e" ]:
        collect_measurements( entry, measurements )
      return
    if "v" in data or "bv" in data or "sv" in data:  # SenML entry
      collect_senml_entry( data, measurements )
      return
    for key, value in data.items( ):
      collect_measurements( value, measurements, key )
  elif isinstance( data, list ):
    for entry in data:
      collect_measurements( entry, measurements, field )
  else:
    append_number( measurements, field or "value", data )


def collect_senml_entry( entry, measurements ):
  name = str( entry.get( "n", "" ) )
  field = name.rstrip( "/" ).rsplit( "/", 1 )[ -1 ]
  for key in ( "v", "bv", "sv" ):
    if key in entry:
      append_number( measurements, field or "value", entry[ key ] )
      return


def append_number( measurements, field, value ):
  if isinstance( value, bool ):
    measurements.append( ( field, 1.0 if value else 0.0 ) )
  elif isinstance( value, ( int, float ) ):
    measurements.append( ( field, float( value ) ) )
  elif isinstance( value, str ):
    try:
      measurements.append( ( field, float( value ) ) )
    except ValueError:
      pass


def main():
  mqtt_client, server_telemetry = setup_mqtt_client()

  # Keep the server running; the mqtt client does its work in its own loop.
  try:
    while True:
      time.sleep( 1 )
  except KeyboardInterrupt:
    pass
  finally:
    mqtt_client.disconnect()
    mqtt_client.loop_stop()
    server_telemetry.shutdown()


if __name__ == "__main__":
  main()
