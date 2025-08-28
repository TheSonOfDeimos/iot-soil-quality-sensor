import asyncio
from logger import log, Logger
from ha_client import HomeAssistantClient
from control_button import ControlButton
from status_led import StatusLed
from soil_sensor import SoilMoistureSensor

class StateController:
    def __init__(self, ha_client: HomeAssistantClient, button: ControlButton, led: StatusLed, soilSensor: SoilMoistureSensor, wakeup_interval: float = 100) -> None:
        self._ha_client = ha_client
        self._button = button
        self._led = led
        self._soilSensor = soilSensor
        self._wakeup_interval = wakeup_interval
        self._last_measurement = -1
        self._is_calibrated = False

    async def run(self):
        self._ha_client.connect()
        self._is_calibrated = self._soilSensor.load_calibration_settings()
        while True:
            await asyncio.sleep(self._wakeup_interval)
            await self.measure_soil_moisture()

    async def measure_soil_moisture(self):
        if not self._is_calibrated:
            return
        self._last_measurement = await self._soilSensor.measure_soil_moisture()
        self._ha_client.publish_soil_moisture(self._last_measurement)
