import machine

from config import LED_PWM_FREQ_HZ, LED_ARRAY, MIN_LED_BRIGHTNESS_PCT


class LedBar:
    def __init__(self, storage, fan):
        self._storage = storage
        self._fan = fan
        self._led_count = len(LED_ARRAY)
        self._pwms = [machine.PWM(machine.Pin(p)) for p in LED_ARRAY]
        for pwm in self._pwms:
            pwm.freq(LED_PWM_FREQ_HZ)
        self._last_lit = -1
        self._last_brightness = -1
        self.update()

    def _brightness_duty_u16(self):
        b = self._storage.get("led_brightness")
        if b < MIN_LED_BRIGHTNESS_PCT:
            b = MIN_LED_BRIGHTNESS_PCT
        if b > 100:
            b = 100
        return int(b * 65535 / 100)

    def _lit_count(self):
        if not self._fan.is_enabled():
            return 1
        duty = self._fan.get_duty()
        min_speed = self._storage.get("min_speed")
        span = 100 - min_speed
        bar = self._led_count - 1
        if span <= 0 or duty <= min_speed:
            return 1
        extra = int(round((duty - min_speed) / span * bar))
        if extra < 0:
            extra = 0
        if extra > bar:
            extra = bar
        return 1 + extra

    def update(self):
        lit = self._lit_count()
        brightness = self._brightness_duty_u16()
        if lit == self._last_lit and brightness == self._last_brightness:
            return
        for i, pwm in enumerate(self._pwms):
            pwm.duty_u16(brightness if i < lit else 0)
        self._last_lit = lit
        self._last_brightness = brightness
