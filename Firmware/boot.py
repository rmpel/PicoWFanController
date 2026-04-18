import machine

try:
    _pwm_pin = machine.Pin(16, machine.Pin.OUT, value=0)
except Exception:
    pass

try:
    _fan_enable_pin = machine.Pin(17, machine.Pin.OUT, value=0)
except Exception:
    pass
