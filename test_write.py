from influxdb import InfluxDBClient
import time

client = InfluxDBClient(host="localhost", port=8086, database="obelix_sensors")

point = [{
    "measurement": "sensor_data",
    "tags":   {"unit_index": "0", "channel": "0"},
    "fields": {"value": 42.0},
    "time":   int(time.time())          # unix-timestamp
}]

client.write_points(point)
print("Testpunt geschreven.")
