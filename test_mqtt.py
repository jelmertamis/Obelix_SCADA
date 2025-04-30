# test_mqtt.py
from obelix.mqtt_client import MQTTClient

# Maak client aan (standaard in Dummy-mode)
client = MQTTClient()
# Verstuur testbericht
client.publish('obelix/test', {'msg': 'hello from Windows'})
