import machine
import time

from config import PIN_PWM, PIN_FAN_ENABLE, PIN_TACH, PWM_FREQ_HZ, TACH_SAMPLE_WINDOW_MS


class FanController:
    def __init__(self, storage):
        self._storage = storage
        self._pwm = machine.PWM(machine.Pin(PIN_PWM))
        self._pwm.freq(PWM_FREQ_HZ)

        self._enable_pin = machine.Pin(PIN_FAN_ENABLE, machine.Pin.OUT, value=0)

        self._tach_pin = machine.Pin(PIN_TACH, machine.Pin.IN, machine.Pin.PULL_UP)
        self._pulses = 0
        self._rpm = 0
        self._last_sample_ms = time.ticks_ms()
        self._last_sample_pulses = 0
        self._last_tach_us = time.ticks_us()
        self._tach_pin.irq(trigger=machine.Pin.IRQ_FALLING, handler=self._on_tach)

        min_speed = storage.get("min_speed")
        stored = storage.get("current_speed")
        if stored < min_speed:
            stored = min_speed
            storage.set("current_speed", stored)
        self._current_duty = stored
        self.apply_duty(self._current_duty, persist=False)

        if storage.get("fan_enabled"):
            self._enable_pin.value(1)

    # Debounce: accept one pulse per >=6 ms. Max countable rate = ~166 Hz,
    # = 5000 RPM @ 2 pulses/rev. This fan's spec max is 4500 RPM, so 6 ms
    # stays safely below the shortest real pulse interval (~6.7 ms at max
    # RPM) while rejecting the ringing that caused 3× over-count at 32%.
    _TACH_MIN_GAP_US = 6000

    def _on_tach(self, pin):
        now = time.ticks_us()
        if time.ticks_diff(now, self._last_tach_us) < self._TACH_MIN_GAP_US:
            return
        self._last_tach_us = now
        self._pulses += 1

    def _polarity_high(self):
        return self._storage.get("pwm_polarity") == "high"

    def apply_duty(self, pct, persist=True):
        min_speed = self._storage.get("min_speed")
        pct = max(min_speed, min(100, int(pct)))
        self._current_duty = pct
        if self._polarity_high():
            raw = int(pct * 65535 / 100)
        else:
            raw = int((100 - pct) * 65535 / 100)
        self._pwm.duty_u16(raw)
        if persist:
            self._storage.set("current_speed", pct)

    def get_duty(self):
        return self._current_duty

    def snap_to_step(self, pct, step):
        step = max(1, int(step))
        pct = max(0, min(100, int(pct)))
        return int(round(pct / step) * step)

    def step_up(self):
        step = self._storage.get("step")
        new = self.snap_to_step(self._current_duty + step, step)
        if new == self._current_duty:
            new = min(100, self._current_duty + step)
        self._storage.set("predefined_active", False)
        self.apply_duty(new)
        return new

    def step_down(self):
        min_speed = self._storage.get("min_speed")
        step = self._storage.get("step")
        new = self.snap_to_step(self._current_duty - step, step)
        if new == self._current_duty:
            new = max(min_speed, self._current_duty - step)
        self._storage.set("predefined_active", False)
        self.apply_duty(new)
        return new

    def set_speed(self, pct):
        self._storage.set("predefined_active", False)
        self.apply_duty(pct)
        return self._current_duty

    def toggle_predefined(self):
        predefined = self._storage.get("predefined_speed")
        if self._storage.get("predefined_active"):
            prev = self._storage.get("previous_speed")
            self._storage.set("predefined_active", False)
            self.apply_duty(prev)
        else:
            self._storage.set("previous_speed", self._current_duty)
            self._storage.set("predefined_active", True)
            self.apply_duty(predefined)
        return self._current_duty

    def is_enabled(self):
        return bool(self._storage.get("fan_enabled"))

    def enable(self):
        self._enable_pin.value(1)
        self._storage.set("fan_enabled", True)

    def disable(self):
        self._enable_pin.value(0)
        self._storage.set("fan_enabled", False)

    def toggle_on_off(self):
        if self.is_enabled():
            self.disable()
        else:
            self.enable()
        return self.is_enabled()

    def boost_start(self):
        self._storage.set("previous_speed", self._current_duty)
        self.apply_duty(self._storage.get("boost_speed"))
        return self._current_duty

    def boost_end(self):
        self.apply_duty(self._storage.get("previous_speed"))
        return self._current_duty

    def update_rpm(self):
        now = time.ticks_ms()
        elapsed = time.ticks_diff(now, self._last_sample_ms)
        if elapsed < TACH_SAMPLE_WINDOW_MS:
            return self._rpm
        pulses_now = self._pulses
        delta = pulses_now - self._last_sample_pulses
        self._last_sample_pulses = pulses_now
        self._last_sample_ms = now
        ppr = max(1, self._storage.get("tach_pulses_per_rev"))
        self._rpm = int((delta * 60000) / (elapsed * ppr))
        return self._rpm

    def get_rpm(self):
        return self._rpm
