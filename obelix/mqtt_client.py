import os
import json
from obelix.utils import log

# Bepaal dummy- of real-mode via omgevingsvariabele
USE_DUMMY = os.getenv('MQTT_USE_DUMMY_BROKER', '1') == '1'

class DummyMQTTClient:
    """
    Dummy no-op MQTT client voor development/testing.
    """
    def __init__(self):
        log("[MQTT] Initialized DummyMQTTClient")
    
    def publish(self, topic: str, payload: dict):
        """Log een dummy-publish in plaats van echt te verzenden."""
        log(f"[MQTT][Dummy] publish to '{topic}': {payload}")

    def subscribe(self, topic: str, callback=None):
        """Log een dummy-subscribe; er komen geen berichten binnen."""
        log(f"[MQTT][Dummy] subscribe to '{topic}'")

class RealMQTTClient:
    """
    Echte MQTT-client gebaseerd op Paho-MQTT.
    """
    def __init__(self):
        try:
            import paho.mqtt.client as mqtt
        except ImportError as e:
            log(f"[MQTT] Paho-MQTT niet geïnstalleerd: {e}")
            raise

        self._broker_url  = os.getenv('MQTT_BROKER_URL', 'localhost')
        self._broker_port = int(os.getenv('MQTT_BROKER_PORT', '1883'))
        self._client      = mqtt.Client()

        # Connect en start netwerkloop
        try:
            self._client.connect(self._broker_url, self._broker_port)
            self._client.loop_start()
            log(f"[MQTT] Verbonden met broker {self._broker_url}:{self._broker_port}")
        except Exception as e:
            log(f"[MQTT] Connectie mislukt: {e}")
            raise

    def publish(self, topic: str, payload: dict):
        """Publish een JSON-payload naar het gegeven topic."""
        try:
            msg = json.dumps(payload)
            result = self._client.publish(topic, msg)
            if result.rc != 0:
                log(f"[MQTT] Publish naar '{topic}' mislukte met code {result.rc}")
        except Exception as e:
            log(f"[MQTT] Fout bij publish naar '{topic}': {e}")

    def subscribe(self, topic: str, callback):
        """Subscribe op een topic en registreer een JSON-callback."""
        def _on_message(client, userdata, msg):
            try:
                data = json.loads(msg.payload.decode())
            except Exception:
                data = msg.payload.decode()
            callback(topic, data)

        try:
            self._client.subscribe(topic)
            self._client.message_callback_add(topic, _on_message)
            log(f"[MQTT] Subscribed op '{topic}'")
        except Exception as e:
            log(f"[MQTT] Subscribe op '{topic}' mislukte: {e}")

    def disconnect(self):
        """Netjes disconnecten en netwerkloop stoppen."""
        try:
            self._client.loop_stop()
            self._client.disconnect()
            log("[MQTT] Disconnect voltooid")
        except Exception as e:
            log(f"[MQTT] Fout tijdens disconnect: {e}")

class MQTTClient:
    """
    Wrapper die Dummy of Real client kiest op basis van de omgevingsvariabele.
    """
    def __init__(self):
        if USE_DUMMY:
            self._client = DummyMQTTClient()
        else:
            self._client = RealMQTTClient()

    def publish(self, topic: str, payload: dict):
        self._client.publish(topic, payload)

    def subscribe(self, topic: str, callback):
        self._client.subscribe(topic, callback)

    def disconnect(self):
        if hasattr(self._client, 'disconnect'):
            self._client.disconnect()
