import machine
import time

from config import PIN_STATUS_LED


def _init_onboard_led():
    # Pico W: on-board LED is on the CYW43 WiFi chip, exposed as Pin("LED")
    # only after the WLAN driver has initialized. Bring it up once.
    try:
        import network
        network.WLAN(network.STA_IF)
    except Exception:
        pass
    try:
        return machine.Pin(PIN_STATUS_LED, machine.Pin.OUT)
    except Exception:
        pass
    # Fallback for non-W Picos
    try:
        return machine.Pin(25, machine.Pin.OUT)
    except Exception:
        return None


# Pattern = list of (on_bool, duration_ms). The pattern repeats unless once=True.
PATTERNS = {
    "off":        [(False, 1000)],
    "on":         [(True,  1000)],
    "connecting": [(True,  500), (False, 500)],
    "ap_mode":    [(True,  150), (False, 150),
                   (True,  150), (False, 150),
                   (True,  800), (False, 400)],
    "sos":        [(True,  150), (False, 150)] * 3
                 + [(True,  450), (False, 150)] * 3
                 + [(True,  150), (False, 150)] * 3
                 + [(False, 800)],
    "success":    [(True, 5000), (False, 0)],
    "tick":       [(True,   60), (False, 60)],
}


class LedStatus:
    def __init__(self, mirror=None):
        self._led = _init_onboard_led()
        self._mirror = mirror
        self._pattern = []
        self._idx = 0
        self._next_at = 0
        self._once = False
        self._done = True
        self.set_pattern("off")

    def set_mirror(self, mirror):
        self._mirror = mirror

    def _apply(self, on):
        if self._led is not None:
            try:
                self._led.value(1 if on else 0)
            except Exception:
                pass
        if self._mirror is not None:
            try:
                self._mirror(on)
            except Exception:
                pass

    def set_pattern(self, name, once=False):
        p = PATTERNS.get(name)
        if not p:
            return
        self._pattern = p
        self._idx = 0
        self._once = once
        self._done = False
        self._next_at = time.ticks_ms()
        self.update()

    def flash_tick(self):
        self.set_pattern("tick", once=True)

    def is_done(self):
        return self._done

    def update(self):
        if self._done or not self._pattern:
            return
        now = time.ticks_ms()
        if time.ticks_diff(now, self._next_at) < 0:
            return
        on, dur = self._pattern[self._idx]
        self._apply(on)
        self._next_at = time.ticks_add(now, dur)
        self._idx += 1
        if self._idx >= len(self._pattern):
            if self._once:
                self._done = True
                self._apply(False)
            else:
                self._idx = 0
