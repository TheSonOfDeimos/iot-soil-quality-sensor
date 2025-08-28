import asyncio
import array
from machine import Pin, ADC
from primitives.aadc import AADC
from logger import log
from file_utils import JsonFileUtil
from math_utils import percentile, average, percentage_in_bounds

class SoilMoistureSensor:
    def __init__(self, sensor: AADC, sensor_power: Pin, probe_count: int = 100, probe_interval: float = 0.2) -> None:
        self._sensor = sensor
        self._sensor_power = sensor_power
        self._probe_count: int = probe_count
        self._probe_interval: float = probe_interval
        self._left_bound: int = 65535
        self._right_bound: int = 0
        self._settings_file = JsonFileUtil("HD-38-sensor-calibration.json")

    async def _do_measurement(self, probe_count: int = 100, probe_interval: float = 0.2) -> array.array:
        raw_moisture_probes = array.array('H')
        self._sensor_power.value(1)
        await asyncio.sleep(1)
        for _ in range(probe_count):
            raw_probe = self._sensor.read_u16(last=False)
            raw_moisture_probes.append(raw_probe)
            await asyncio.sleep(probe_interval)
        self._sensor_power.value(0)
        log.debug(f"Raw moisture probes: {raw_moisture_probes}")
        return raw_moisture_probes

    async def calibrate_dry_soil(self):
        raw = await self._do_measurement(self._probe_count, self._probe_interval)
        self._left_bound = int(average(raw))

    async def calibrate_wet_soil(self):
        raw = await self._do_measurement(self._probe_count, self._probe_interval)
        self._right_bound = int(average(raw))

    async def measure_soil_moisture(self) -> int:
        raw = await self._do_measurement(self._probe_count, self._probe_interval)
        moisture_level = int(average(raw))
        return int(percentage_in_bounds(moisture_level, self._left_bound, self._right_bound))

    def reset(self):
        self._left_bound = 65535
        self._right_bound = 0
        self._settings_file.delete()

    def store_calibration_settings(self):
        self._settings_file.rewrite({
            "left": self._left_bound,
            "right": self._right_bound
        })

    def load_calibration_settings(self) -> bool:
        data = self._settings_file.read()
        if data is None:
            return False
        self._left_bound = int(data.get("left", self._left_bound))
        self._right_bound = int(data.get("right", self._right_bound))
        return True
