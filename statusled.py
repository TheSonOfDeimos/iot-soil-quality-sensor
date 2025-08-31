from picozero.picozero import RGBLED

class StatusLed :
    def __init__(self, led : RGBLED) -> None:
        self._led = led
        self._led.off()

    def idle(self):
        self._led.off()

    def soil_moisture(self, moisture_level : int, left_bound : int = 0, right_bound : int = 100):
        if moisture_level < left_bound or moisture_level > right_bound :
            raise Exception("Out of bounds")
        
        green = (255 / 100) * moisture_level
        red = 255 - green
        self._led.color = (red, green, 0)

    def start_calibration_soil_moisture_when_dry(self):
        self._led.blink(on_times=0.2, colors=((1,0,0), (0,0,0)))
        
    def calibrating_soil_moisture_when_dry(self):
        self._led.pulse(colors=((0, 0, 0), (1, 0, 0)))
    
    def start_calibration_soil_moisture_when_wet(self):
        self._led.blink(on_times=0.2, colors=((0,1,0), (0,0,0)))

    def calibrating_soil_moisture_when_wet(self):
        self._led.pulse(colors=((0, 0, 0), (0, 1, 0)))

    def measuring_soil_moisture(self):
        self._led.cycle(fade_times=0.7, colors=((1,0,0), (0,1,0)), fps=100)

    def connecting_to_network(self):
        self._led.pulse(colors=((0, 0, 0), (0, 0, 1)))

    def device_ready(self):
        self._led.blink(on_times=0.2, colors=((0, 1, 0), (0, 0, 0)))

    def user_error(self):
        self._led.blink(on_times=0.1, colors=((1,0,0), (0,0,1)))

    def internal_error(self):
        self._led.blink(on_times=0.1, colors=((0,0,1), (1,0,0)))

    def fatal_error(self):
        self._led.blink(on_times=0.1, colors=((1,0,0), (0,0,0)))
