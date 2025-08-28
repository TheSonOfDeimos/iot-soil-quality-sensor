import asyncio
from asyncio import Event
from primitives.pushbutton import Pushbutton

class ControlButton:
    def __init__(self, button: Pushbutton):
        self._button = button

    async def wait_press(self):
        def _on_button_pressed(e: Event):
            e.set()
        event = Event()
        self._button.press_func(_on_button_pressed, (event,))
        await event.wait()
        event.clear()

    def subscribe_long_press(self, func, args=()):
        self._button.long_func(func, args)

    def subscribe_double_press(self, func, args=()):
        self._button.double_func(func, args)
