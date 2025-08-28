import network, time
import ujson as json
from umqtt.simple import MQTTClient
from logger import log

class HomeAssistantClient:
    def __init__(self, wifi_ssid: str, wifi_psk: str, mqtt_host: str):
        self._wifi_ssid = wifi_ssid
        self._wifi_psk = wifi_psk
        self._mqtt_host = mqtt_host
        self._client = None
        self._soil_moisture_sensor_state_topic = None

    def _connect_wifi(self, name: str, password: str, attempts: int = 10):
        wlan = network.WLAN(network.STA_IF)
        wlan.active(True)
        while not wlan.isconnected():
            if attempts <= 0:
                raise Exception("Failed to connect to WiFi")
            wlan.connect(name, password)
            time.sleep(5)
            attempts -= 1

    def _connect_mqtt(self, host: str, client_id: str):
        self._client = MQTTClient(
            client_id=client_id,
            server=host,
            keepalive=5,
            port=1883
        )
        availability_topic = f"{client_id}/availability"
        self._client.set_last_will(availability_topic, b"offline", retain=True, qos=1)
        self._client.connect()
        self._client.publish(availability_topic, b"online", retain=True, qos=1)

    def _register_components(self, client_id: str):
        soil_moisture_sensor = "HD_38_soil_moisture_sensor"
        self._soil_moisture_sensor_state_topic = f"{client_id}/{soil_moisture_sensor}/state"
        config = {
            "device": {"identifiers": client_id, "name": client_id},
            "components": {
                soil_moisture_sensor: {
                    "unique_id": soil_moisture_sensor,
                    "platform": "sensor",
                    "device_class": "moisture",
                    "unit_of_measurement": "%",
                    "state_topic": self._soil_moisture_sensor_state_topic,
                }
            },
        }
        self._client.publish(f"homeassistant/device/{client_id}/config", json.dumps(config), retain=True, qos=1)

    def connect(self):
        device_id = "soil-quality-monitor"
        self._connect_wifi(name=self._wifi_ssid, password=self._wifi_psk)
        self._connect_mqtt(host=self._mqtt_host, client_id=device_id)
        self._register_components(device_id)

    def publish_soil_moisture(self, moisture_level: int):
        self._client.publish(self._soil_moisture_sensor_state_topic, ("%.1f" % moisture_level), retain=True, qos=1)
