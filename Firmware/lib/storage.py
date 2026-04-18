import json

from config import (
    DEFAULT_STEP,
    DEFAULT_CURRENT_SPEED,
    DEFAULT_PREDEFINED_SPEED,
    DEFAULT_PREVIOUS_SPEED,
    DEFAULT_BOOST_SPEED,
    DEFAULT_MIN_SPEED,
    DEFAULT_PWM_POLARITY,
    DEFAULT_TACH_PULSES_PER_REV,
    DEFAULT_HOLD_THRESHOLD_MS,
    DEFAULT_DEVICE_NAME,
    DEFAULT_ENCODER_INVERT,
    DEFAULT_FAN_ENABLED,
    DEFAULT_PREDEFINED_ACTIVE,
    DEFAULT_LED_BRIGHTNESS,
    MIN_LED_BRIGHTNESS_PCT,
)


SETTINGS_PATH = "/settings.json"

DEFAULTS = {
    "wifi_ssid": "",
    "wifi_password": "",
    "current_speed": DEFAULT_CURRENT_SPEED,
    "previous_speed": DEFAULT_PREVIOUS_SPEED,
    "predefined_speed": DEFAULT_PREDEFINED_SPEED,
    "boost_speed": DEFAULT_BOOST_SPEED,
    "min_speed": DEFAULT_MIN_SPEED,
    "step": DEFAULT_STEP,
    "pwm_polarity": DEFAULT_PWM_POLARITY,
    "tach_pulses_per_rev": DEFAULT_TACH_PULSES_PER_REV,
    "hold_threshold_ms": DEFAULT_HOLD_THRESHOLD_MS,
    "device_name": DEFAULT_DEVICE_NAME,
    "encoder_invert": DEFAULT_ENCODER_INVERT,
    "fan_enabled": DEFAULT_FAN_ENABLED,
    "predefined_active": DEFAULT_PREDEFINED_ACTIVE,
    "led_brightness": DEFAULT_LED_BRIGHTNESS,
}

BOOL_KEYS = {"encoder_invert", "fan_enabled", "predefined_active"}

INT_KEYS = {
    "current_speed",
    "previous_speed",
    "predefined_speed",
    "boost_speed",
    "min_speed",
    "step",
    "tach_pulses_per_rev",
    "hold_threshold_ms",
    "led_brightness",
}


def _coerce(key, value):
    if key in INT_KEYS:
        try:
            v = int(value)
        except (TypeError, ValueError):
            v = DEFAULTS.get(key, 0)
        if key == "led_brightness":
            v = max(MIN_LED_BRIGHTNESS_PCT, min(100, v))
        return v
    if key in BOOL_KEYS:
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        if isinstance(value, str):
            return value.strip().lower() in ("1", "true", "yes", "on")
        return DEFAULTS.get(key, False)
    if value is None:
        return DEFAULTS.get(key, "")
    return str(value)


class Storage:
    def __init__(self):
        self._data = dict(DEFAULTS)
        self._load()

    def _load(self):
        try:
            with open(SETTINGS_PATH, "r") as f:
                disk = json.load(f)
        except (OSError, ValueError):
            disk = {}
        for k in DEFAULTS:
            if k in disk:
                self._data[k] = _coerce(k, disk[k])
        self._save()

    def _save(self):
        try:
            with open(SETTINGS_PATH, "w") as f:
                json.dump(self._data, f)
        except OSError as e:
            print(f"storage: FAILED to save: {e}")
            import sys
            sys.print_exception(e)

    def get(self, key):
        return self._data.get(key, DEFAULTS.get(key))

    def set(self, key, value):
        if key not in DEFAULTS:
            return
        self._data[key] = _coerce(key, value)
        self._save()

    def set_many(self, updates):
        changed = False
        applied = {}
        for k, v in updates.items():
            if k in DEFAULTS:
                self._data[k] = _coerce(k, v)
                applied[k] = self._data[k]
                changed = True
        if changed:
            print(f"storage: saving {applied}")
            self._save()

    def all(self):
        return dict(self._data)

    def public(self):
        d = self.all()
        d.pop("wifi_password", None)
        return d

    def has_wifi_config(self):
        return bool(self.get("wifi_ssid"))

    def close(self):
        pass
