import machine
import time

from config import (
    PIN_ENC_CLK,
    PIN_ENC_DT,
    PIN_ENC_SW,
    BTN_DEBOUNCE_MS,
    BTN_DOUBLECLICK_MS,
)


class RotaryEncoder:
    # Classic "read DT on CLK falling edge" decoder with a hard ignore-window
    # to swallow contact bounce. One tick per detent.
    _LOCKOUT_MS = 3

    def __init__(self, invert_provider=None):
        self._clk = machine.Pin(PIN_ENC_CLK, machine.Pin.IN, machine.Pin.PULL_UP)
        self._dt = machine.Pin(PIN_ENC_DT, machine.Pin.IN, machine.Pin.PULL_UP)
        self._invert_provider = invert_provider or (lambda: False)
        self._delta = 0
        self._last_ms = time.ticks_ms()
        self._clk.irq(trigger=machine.Pin.IRQ_FALLING, handler=self._on_falling)

    def _on_falling(self, pin):
        now = time.ticks_ms()
        if time.ticks_diff(now, self._last_ms) < self._LOCKOUT_MS:
            return
        self._last_ms = now
        if self._clk.value() != 0:
            return
        if self._dt.value():
            self._delta += 1
        else:
            self._delta -= 1

    def take_ticks(self):
        d = self._delta
        self._delta = 0
        if self._invert_provider():
            d = -d
        return d


class Button:
    EVT_NONE = 0
    EVT_SHORT = 1
    EVT_DOUBLE = 2
    EVT_HOLD_START = 3
    EVT_HOLD_END = 4

    def __init__(self, hold_threshold_ms_provider):
        self._pin = machine.Pin(PIN_ENC_SW, machine.Pin.IN, machine.Pin.PULL_UP)
        self._get_hold_ms = hold_threshold_ms_provider

        self._raw = 1
        self._debounced = 1
        self._last_change_ms = time.ticks_ms()

        self._press_ms = 0
        self._holding = False

        # After a short-release, we wait one doubleclick window before
        # emitting EVT_SHORT. If a new press arrives inside that window,
        # that counts as the start of a double-click.
        self._last_release_ms = 0
        self._awaiting_double = False
        self._this_is_double = False

    def pressed_at_boot(self):
        return self._pin.value() == 0

    def update(self):
        now = time.ticks_ms()
        raw = self._pin.value()

        if raw != self._raw:
            self._raw = raw
            self._last_change_ms = now

        if raw != self._debounced and time.ticks_diff(now, self._last_change_ms) >= BTN_DEBOUNCE_MS:
            self._debounced = raw
            if raw == 0:
                return self._on_press_edge(now)
            return self._on_release_edge(now)

        # Hold detection while pressed.
        if self._debounced == 0 and not self._holding:
            if time.ticks_diff(now, self._press_ms) >= self._get_hold_ms():
                self._holding = True
                self._awaiting_double = False
                self._this_is_double = False
                return self.EVT_HOLD_START

        # Single-click confirmation: released, timer expired, no second press.
        if self._awaiting_double and self._debounced == 1:
            if time.ticks_diff(now, self._last_release_ms) >= BTN_DOUBLECLICK_MS:
                self._awaiting_double = False
                return self.EVT_SHORT

        return self.EVT_NONE

    def _on_press_edge(self, now):
        self._press_ms = now
        if self._awaiting_double and time.ticks_diff(now, self._last_release_ms) < BTN_DOUBLECLICK_MS:
            self._this_is_double = True
            self._awaiting_double = False
        else:
            self._this_is_double = False
        return self.EVT_NONE

    def _on_release_edge(self, now):
        if self._holding:
            self._holding = False
            return self.EVT_HOLD_END
        press_duration = time.ticks_diff(now, self._press_ms)
        if press_duration >= self._get_hold_ms():
            return self.EVT_NONE
        if self._this_is_double:
            self._this_is_double = False
            return self.EVT_DOUBLE
        self._last_release_ms = now
        self._awaiting_double = True
        return self.EVT_NONE
