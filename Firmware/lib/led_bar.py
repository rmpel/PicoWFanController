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
        self._last_state = None
        self._status_active = False
        self.update()

    def _base_brightness_pct(self):
        b = self._storage.get("led_brightness")
        if b < MIN_LED_BRIGHTNESS_PCT:
            b = MIN_LED_BRIGHTNESS_PCT
        if b > 100:
            b = 100
        return b

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

    def _pin_duty_u16(self, lit_on, correction_pct, base_pct):
        if not lit_on:
            return 65535
        pct = base_pct * correction_pct / 100
        if pct < 0:
            pct = 0
        if pct > 100:
            pct = 100
        duty = int(pct * 65535 / 100)
        return 65535 - duty

    def set_status(self, on):
        # Drive the first logical LED of the bar directly for boot/WiFi status.
        # Blocks normal fan-duty rendering until release_status() is called.
        self._status_active = True
        invert = bool(self._storage.get("led_invert"))
        physical_i = (self._led_count - 1) if invert else 0
        correction = self._storage.get("led_correction") or []
        corr = correction[physical_i] if physical_i < len(correction) else 100
        base = self._base_brightness_pct()
        duty = self._pin_duty_u16(bool(on), corr, base)
        for i, pwm in enumerate(self._pwms):
            pwm.duty_u16(duty if i == physical_i else 65535)
        self._last_state = None

    def release_status(self):
        self._status_active = False
        self._last_state = None

    def update(self):
        if self._status_active:
            return
        lit = self._lit_count()
        base = self._base_brightness_pct()
        invert = bool(self._storage.get("led_invert"))
        correction = self._storage.get("led_correction") or []

        state = (lit, base, invert, tuple(correction))
        if state == self._last_state:
            return

        for physical_i, pwm in enumerate(self._pwms):
            # Logical index 0 is the "first" LED of the bar. Invert reverses
            # the mapping so the bar grows from the other end.
            logical_i = (self._led_count - 1 - physical_i) if invert else physical_i
            lit_on = logical_i < lit
            corr = correction[physical_i] if physical_i < len(correction) else 100
            pwm.duty_u16(self._pin_duty_u16(lit_on, corr, base))

        self._last_state = state
