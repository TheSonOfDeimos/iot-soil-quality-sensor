import network, json
from umqtt.simple import MQTTClient
import asyncio
import time
import rp2

from logger import log

rp2.country("GB")

class HomeAssistantClient:
    async def _connect_wifi(self, name: str, password: str, attempts: int = 10, timeout: int = 5):
        wlan = network.WLAN(network.STA_IF)
        wlan.active(True)

        while not wlan.isconnected():
            log.debug(f"Connecting to WiFi {name}, attempts left: {attempts}")
            if attempts <= 0:
                raise Exception(f"Failed to connect to WiFi {name}. Exceeded maximum attempts.")

            try:
                wlan.disconnect()
            except Exception:
                pass
            wlan.connect(name, password)

            start = time.ticks_ms()
            while not wlan.isconnected():
                if time.ticks_diff(time.ticks_ms(), start) > timeout * 1000:
                    log.debug("WiFi connect attempt timed out")
                    break
                await asyncio.sleep(0.25)

            attempts -= 1

        log.debug(f"Connected to WiFi {name}, IP: {wlan.ifconfig()[0]}")
    
    def _connect_mqtt(self, host : str, client_id : str):
        log.debug(f"Connecting to MQTT broker at {host} with client ID {client_id}")

        self._client = MQTTClient(
            client_id=client_id,
            server=host,
            keepalive=5,
            port=1883)

        availability_topic = f"{client_id}/availability"
        self._client.set_last_will(availability_topic, b"offline", retain=True, qos=1)
        self._client.connect()
        self._client.publish(availability_topic, b"online", retain=True, qos=1)
    
    def _register_components(self, client_id : str):
        log.debug(f"Registering components for client ID {client_id}")

        soil_moisture_sensor = "HD_38_soil_moisture_sensor"
        self._soil_moisture_sensor_state_topic =  f"{client_id}/{soil_moisture_sensor}/state"
      
        config = {
            "device" : {
                "identifiers": client_id,
                "name": client_id,
                "manufacturer": "TheSonOfDeimos",
                "model": "Raspberry Pi Pico W"
            },
            "origin" : {
                "name": "SQM OS",
                "sw_version": "1.0"
            },
            "components": {
                soil_moisture_sensor: {
                    "unique_id": soil_moisture_sensor,
                    "platform": "sensor",
                    "device_class": "moisture",
                    "unit_of_measurement":"%",
                    "state_topic": self._soil_moisture_sensor_state_topic,
                }
            },
        }    
        self._client.publish(f"homeassistant/device/{client_id}/config", json.dumps(config), retain=True, qos=1)
    
    def __init__(self, wifi_ssid : str, wifi_psk : str, mqtt_host : str):
        self._wifi_ssid = wifi_ssid
        self._wifi_psk = wifi_psk
        self._mqtt_host = mqtt_host

    async def connect(self):
        log.debug("Connecting to Home Assistant")

        device_id = "soil-quality-monitor"
        await self._connect_wifi(name=self._wifi_ssid, password=self._wifi_psk)
        self._connect_mqtt(host=self._mqtt_host, client_id=device_id)
        self._register_components(device_id)

    def publish_soil_moisture(self, moisture_level: int, attempts: int = 10):
        log.debug(f"Publishing soil moisture level: {moisture_level}")

        if moisture_level < 0 or moisture_level > 100:
            raise ValueError("Moisture level must be between 0 and 100.")
        
        while True:
            if attempts <= 0:
                raise Exception("Failed to publish soil moisture after multiple attempts.")
            try:
                self._client.publish(self._soil_moisture_sensor_state_topic, ("%.1f" % moisture_level), retain=True, qos=1)
                log.debug("Soil moisture published successfully")
                return
            except Exception as e:
                attempts -= 1
                log.debug(f"Failed to publish soil moisture: {e}, reconnecting attempts left: {attempts}")
                self._client.connect(False)
                