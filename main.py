import asyncio
from machine import Pin, ADC
from primitives.aadc import AADC
from primitives.pushbutton import Pushbutton
from picozero.picozero import RGBLED

from logger import log, Logger
from homeassistantclient import HomeAssistantClient
from controlbutton import ControlButton
from statusled import StatusLed
from soilmoisturesensor import SoilMoistureSensor
from statecontroller import StateController

async def main():
    log.set_level(Logger.DEBUG)

    ha_client = HomeAssistantClient("ZEYA", "pool-side-X", "192.168.1.34")
    button = ControlButton(Pushbutton(Pin(17, Pin.IN, Pin.PULL_UP)))
    led = StatusLed(RGBLED(red=12, green=11, blue=10, active_high=False))
    soilSensor = SoilMoistureSensor(AADC(ADC(27)), Pin(26, Pin.OUT, value=0), probe_count=100, probe_interval=0.2)

    controller = StateController(ha_client, button, led, soilSensor, wakeup_interval=400)
    await controller.run()

try:
    asyncio.run(main())
finally:
    _ = asyncio.new_event_loop()
    