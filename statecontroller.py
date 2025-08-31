import asyncio  
import array

from logger import log
from homeassistantclient import HomeAssistantClient
from controlbutton import ControlButton
from statusled import StatusLed
from soilmoisturesensor import SoilMoistureSensor


class StateController:
    def __init__(self, ha_client : HomeAssistantClient, button : ControlButton, led : StatusLed, soilSensor : SoilMoistureSensor, wakeup_interval : float = 100) -> None:
        self._in_progress = False
        self._is_calibrated = False
        self._last_measurement = -1

        self._ha_client = ha_client
        self._button = button
        self._led = led
        self._soilSensor = soilSensor
        self._wakeup_interval = wakeup_interval

    async def run(self):
        try:
            self._in_progress = True
            log.info("Device initialization")

            self._led.connecting_to_network()
            await self._ha_client.connect()

            self._button.subscribe_long_press(self.calibrate_device)
            self._button.subscribe_double_press(self.last_measurement)

            self._is_calibrated = self._soilSensor.load_calibration_settings()
            if self._is_calibrated is False:
                log.info("Device is not calibrated, starting calibration")
                self._in_progress = False
                await self.calibrate_device()
                self._in_progress = True

            log.info("Device is ready, running main loop")
            self._led.device_ready()
            await asyncio.sleep(5)
            self._led.idle()
            self._in_progress = False

            while True:
                await asyncio.sleep(self._wakeup_interval)
                await self.measure_soil_moisture()
            
        except Exception as e:
            log.error(e)
            self._led.fatal_error()
            await asyncio.sleep(5)
            raise

        finally:
            self._led.idle()
            self._in_progress = False

    async def last_measurement(self) :
        if self._in_progress is True:
            log.warning("Reject, anther operation is in progress")
            return
        
        if self._last_measurement < 0 :
            await self.measure_soil_moisture()
        else:
            try:
                self._in_progress = True
                log.info("Displaying last measurement")
                if self._is_calibrated is False:
                    raise Exception("Device is not calibrated")
                self._led.soil_moisture(self._last_measurement, 0, 100)
                await asyncio.sleep(5)
    
            except Exception as e:
                log.error(e)
                self._led.user_error()
                await asyncio.sleep(5)

            finally:
                self._led.idle()
                self._in_progress = False

    async def calibrate_device(self):
        if self._in_progress is True:
            log.warning("Reject, anther operation is in progress")
            return

        try:
            self._in_progress = True
            log.info("Calibrating soil moisture sensor")

            self._is_calibrated = False
            self._soilSensor.reset()

            self._led.start_calibration_soil_moisture_when_dry()
            await self._button.wait_press()

            self._led.calibrating_soil_moisture_when_dry()
            await self._soilSensor.calibrate_dry_soil()
            self._last_measurement = 0

            self._led.start_calibration_soil_moisture_when_wet()
            await self._button.wait_press()

            self._led.calibrating_soil_moisture_when_wet()
            await self._soilSensor.calibrate_wet_soil()
            self._last_measurement = 100

            self._soilSensor.store_calibration_settings()
            self._is_calibrated = True

        except Exception as e:
            log.error(e)
            self._led.user_error()
            await asyncio.sleep(5)

        finally:
            self._led.idle()
            self._in_progress = False

    async def measure_soil_moisture(self):
        if self._in_progress is True:
            log.warning("Reject, anther operation is in progress or device is not calibrated")
            return

        try:
            self._in_progress = True
            log.info("Measuring soil moisture")
            if self._is_calibrated is False:
                raise Exception("Device is not calibrated")

            self._led.measuring_soil_moisture()
            self._last_measurement = await self._soilSensor.measure_soil_moisture()
            
            self._led.soil_moisture(self._last_measurement, 0, 100)
            self._ha_client.publish_soil_moisture(self._last_measurement)
            await asyncio.sleep(5)

        except Exception as e:
            log.error(e)
            self._led.user_error()
            await asyncio.sleep(5)

        finally:
            self._led.idle()
            self._in_progress = False
            