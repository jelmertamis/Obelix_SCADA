"""
Kleine helper om een meting naar InfluxDB 1.x te schrijven.
Installeer één keer:
    pip install influxdb==5.3.1
"""

from influxdb import InfluxDBClient
import time

# --- Pas deze constants zo nodig aan -----------------------------
INFLUX_HOST   = "localhost"
INFLUX_PORT   = 8086
INFLUX_DBNAME = "obelix_sensors"
# -----------------------------------------------------------------

_client = InfluxDBClient(host=INFLUX_HOST, port=INFLUX_PORT, database=INFLUX_DBNAME)

def write_sensor_reading(unit_index: int, channel: int, value: float, ts=None):
    """
    Schrijf één punt naar InfluxDB.
    • measurement: sensor_data
    • tags:        unit_index, channel
    • field:       value
    • tijd:        nu (nanoseconden)

    Fout wordt veilig genegeerd zodat het de SCADA-loop nooit onderbreekt.
    """
    try:
        if ts is None:               # seconden → nanoseconden verwacht door Influx
            ts = int(time.time() * 1_000_000_000)

        point = [{
            "measurement": "sensor_data",
            "tags":   {"unit_index": str(unit_index), "channel": str(channel)},
            "fields": {"value": float(value)},
            "time":   ts
        }]
        _client.write_points(point, time_precision="n")
    except Exception as e:
        # Logging gebruiken in plaats van exception te laten crashen
        from .utils import log
        log(f"[Influx] schrijf­fout: {e}")
