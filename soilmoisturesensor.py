from machine import Pin, ADC as AADC
import asyncio
import array

from logger import log
from fileutils import JsonFileUtil
from mathutils import average, percentile, percentage_in_bounds

class SoilMoistureSensor:
    async def _do_measurement(self, probe_count : int = 100, probe_interval : float = 0.2) -> array.array :
        raw_moisture_probes = array.array('H')  # Array of unsigned short (16-bit) integers
        self._sensor_power.value(1)  
        await asyncio.sleep(1)  # Wait for sensor to stabilize
        for _ in range(probe_count):
            raw_probe = self._sensor.read_u16(last=False)
            raw_moisture_probes.append(raw_probe)
            await asyncio.sleep(probe_interval)
        self._sensor_power.value(0)  
        log.debug(f"Raw moisture probes: {raw_moisture_probes}")
        log.debug(f"Min: {min(raw_moisture_probes)}, "
                  f"Max: {max(raw_moisture_probes)}, "
                  f"Avg: {average(raw_moisture_probes)}, "
                  f"P25: {percentile(raw_moisture_probes, 25)}, "
                  f"P50: {percentile(raw_moisture_probes, 50)}, "
                  f"P75: {percentile(raw_moisture_probes, 75)}, "
                  f"P95: {percentile(raw_moisture_probes, 95)}")
        return raw_moisture_probes

    def __init__(self, sensor : AADC, sensor_power : Pin, probe_count : int = 100, probe_interval : float = 0.2) -> None:
        self._sensor = sensor
        self._sensor_power = sensor_power

        self._probe_count : int = probe_count
        self._probe_interval : float = probe_interval

        self._left_bound : int = 65535
        self._right_bound : int = 0

        self._settings_file = JsonFileUtil("HD-38-sensor-calibration.json")

    async def calibrate_dry_soil(self) :
        raw_moisture_probes = await self._do_measurement(self._probe_count, self._probe_interval)
        self._left_bound = int(average(raw_moisture_probes))

        if self._left_bound < self._right_bound:
            raise Exception("Invalid calibration values. Left bound must be greater than right bound.")

        log.debug(f"Calibration dry soil completed. Left bound: {self._left_bound}, Right bound: {self._right_bound}")
        
    async def calibrate_wet_soil(self) :
        raw_moisture_probes = await self._do_measurement(self._probe_count, self._probe_interval)    
        self._right_bound = int(average(raw_moisture_probes))

        if self._left_bound < self._right_bound:
            raise Exception("Invalid calibration values. Right bound must be less than left bound.")

        log.debug(f"Calibration wet soil completed. Left bound: {self._left_bound}, Right bound: {self._right_bound}")

    async def measure_soil_moisture(self) -> int:
        raw_moisture_probes = await self._do_measurement(self._probe_count, self._probe_interval)    
        moisture_level = int(average(raw_moisture_probes))
        moisture_percentage = int(percentage_in_bounds(moisture_level, self._left_bound, self._right_bound))
        
        log.debug(f"Measured soil moisture: {moisture_level}, Percentage: {moisture_percentage}")
        return moisture_percentage
    
    def reset(self):
        self._left_bound = 65535
        self._right_bound = 0
        log.debug("Calibration reset to default values")
        if self._settings_file.delete() is True:
            log.debug("Calibration settings file deleted")
        else:
            log.debug("No calibration settings file to delete")

    def store_calibration_settings(self):
        self._settings_file.rewrite({
            "left": self._left_bound,
            "right": self._right_bound
        })
        log.debug(f"Calibration settings saved. Left bound: {self._left_bound}, Right bound: {self._right_bound}")

    def load_calibration_settings(self) -> bool :
        data = self._settings_file.read()
        if data is None:
            log.debug("No calibration settings file found.")
            return False
        
        self._left_bound = int(data.get("left", self._left_bound))
        self._right_bound = int(data.get("right", self._right_bound))
        log.debug(f"Calibration settings loaded. Left={self._left_bound}, Right={self._right_bound}")
        return True
    