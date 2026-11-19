#!/usr/bin/env python3

r"""

    File:          telemetry.py

    Purpose:       OpenTelemetry metrics for the Planter3000
                   server. The metrics are exported over OTLP/HTTP
                   to the local Prometheus instance, which stores
                   them and serves them to Grafana.


    Remarks:       - Prometheus must run with its native OTLP
                     receiver enabled (supported since 2.47):

                       # Prometheus 3.x
                       prometheus --config.file=... \
                                  --web.enable-otlp-receiver

                       # Prometheus 2.47 - 2.55
                       prometheus --config.file=... \
                                  --enable-feature=otlp-write-receiver

                     The receiver endpoint is then:

                       http://localhost:9090/api/v1/otlp/v1/metrics

                   - The endpoint can be overridden with the
                     OTEL_EXPORTER_OTLP_METRICS_ENDPOINT
                     environment variable (full URL).

                   - Requires these modules:

                       pip install opentelemetry-sdk \
                                   opentelemetry-exporter-otlp-proto-http

"""

import os
import re
import time

from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.metrics import Observation
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource, SERVICE_NAME


DEFAULT_OTLP_METRICS_ENDPOINT = "http://localhost:9090/api/v1/otlp/v1/metrics"
EXPORT_INTERVAL_MILLIS       = int( 10000 )
SERVICE_NAME_VALUE           = "planter3000-server"


def metric_name_part( name ):
  """Turn an arbitrary label into a part usable in a metric name."""
  name = re.sub( r"(?<=[a-z0-9])(?=[A-Z])", "_", str( name ) )
  name = re.sub( r"[^a-zA-Z0-9_]", "_", name )
  name = name.strip( "_" ).lower()
  return name or "value"


class Telemetry:
  """Holds the meter and the instruments used by the server."""

  def __init__( self, endpoint = None ):
    if endpoint is None:
      endpoint = os.environ.get( "OTEL_EXPORTER_OTLP_METRICS_ENDPOINT",
                                 DEFAULT_OTLP_METRICS_ENDPOINT )

    exporter = OTLPMetricExporter( endpoint = endpoint )
    reader = PeriodicExportingMetricReader(
      exporter,
      export_interval_millis = EXPORT_INTERVAL_MILLIS )
    self._provider = MeterProvider(
      resource = Resource.create( { SERVICE_NAME: SERVICE_NAME_VALUE } ),
      metric_readers = [ reader ] )

    meter = self._provider.get_meter( "planter3000.server" )
    self._meter = meter
    self._start_time = time.monotonic()
    self._mqtt_connected = False
    self._sensor_gauges = { }

    # MQTT client metrics
    self._mqtt_connects = meter.create_counter(
      "planter3000.mqtt.connects",
      description = "Successful connections to the MQTT broker" )
    self._mqtt_disconnects = meter.create_counter(
      "planter3000.mqtt.disconnects",
      description = "Disconnections from the MQTT broker" )
    self._messages_received = meter.create_counter(
      "planter3000.mqtt.messages.received",
      description = "Received MQTT messages, by topic kind" )
    self._messages_invalid = meter.create_counter(
      "planter3000.mqtt.messages.invalid",
      description = "Received MQTT messages that could not be parsed" )

    meter.create_observable_gauge(
      "planter3000.mqtt.connected",
      callbacks = [ self._observe_mqtt_connected ],
      description = "1 while connected to the MQTT broker, 0 otherwise" )
    meter.create_observable_gauge(
      "planter3000.server.uptime",
      callbacks = [ self._observe_uptime ],
      unit = "s",
      description = "Seconds since the server started" )

  # observations for the asynchronous instruments

  def _observe_mqtt_connected( self, options ):
    return [ Observation( 1 if self._mqtt_connected else 0 ) ]

  def _observe_uptime( self, options ):
    return [ Observation( time.monotonic() - self._start_time ) ]

  # MQTT client metrics

  def record_mqtt_connect( self ):
    self._mqtt_connected = True
    self._mqtt_connects.add( 1 )

  def record_mqtt_disconnect( self, unexpected ):
    self._mqtt_connected = False
    self._mqtt_disconnects.add( 1, { "unexpected": bool( unexpected ) } )

  def record_message( self, kind ):
    self._messages_received.add( 1, { "kind": kind } )

  def record_invalid_message( self, kind ):
    self._messages_invalid.add( 1, { "kind": kind } )

  # sensor metrics

  def record_reading( self, kind, field, value, room, plant = None ):
    """Set the gauge for one sensor reading.

    Each (topic kind, field) pair gets its own metric, e.g.
    planter3000.telemetry.soil_sensor.moisture. The room and plant
    from the topic become attributes.
    """
    key = ( kind, field )
    gauge = self._sensor_gauges.get( key )
    if gauge is None:
      gauge = self._meter.create_gauge(
        "planter3000.telemetry."
        + metric_name_part( kind )
        + "."
        + metric_name_part( field ),
        description = "Sensor reading '" + str( field )
                      + "' from " + str( kind ) + " messages" )
      self._sensor_gauges[ key ] = gauge

    attributes = { "room": str( room ) }
    if plant is not None:
      attributes[ "plant" ] = str( plant )
    gauge.set( float( value ), attributes )

  def shutdown( self ):
    """Flush pending metrics and stop the exporter."""
    self._provider.shutdown()
