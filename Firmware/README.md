# PicoFanController — Firmware

MicroPython firmware for a Raspberry Pi Pico W that drives a 4-wire PC fan
(Foxconn PV123812DSPF01 / Dell, Intel 4-wire spec, 25 kHz PWM) with a
rotary-encoder + push-button UI and a small web interface.

Dual-use: fume extractor for soldering, and a quiet bedroom fan at night.

## Wiring

| Signal          | GPIO | Notes                                              |
|-----------------|------|----------------------------------------------------|
| PWM out         | 16   | 25 kHz to fan pin 4 (blue). Active HIGH default.   |
| Tach in         | 22   | Fan pin 3 (green). Pulled high to 3V3 via 10 kΩ.   |
| Encoder CLK     | 15   | Internal pull-up enabled in firmware.              |
| Encoder DT      | 14   | Internal pull-up enabled in firmware.              |
| Encoder SW      | 12   | Push-button. Internal pull-up enabled.             |
| Status LED      | —    | On-board CYW43 LED ("LED").                        |

Fan power: 12 V externally. Share GND with the Pico.

## First-time setup

```
./install.sh                       # installs mpremote and downloads MicroPython UF2
# flash the UF2 to the Pico W in BOOTSEL mode
./deploy.sh                        # copies firmware to device and resets
```

On first boot there are no WiFi credentials, so the device comes up in
**AP mode**. Connect to the open SSID `PicoFanController-XXXX` and browse to
`http://192.168.4.1`. Enter your WiFi credentials; the device reboots and joins
the network.

To force AP mode later, hold the encoder push-button while the Pico powers on.

## Status LED patterns

| Pattern                         | Meaning                |
|---------------------------------|------------------------|
| 0.5 s on / 0.5 s off            | Connecting to WiFi     |
| SOS (· · · — — — · · ·)         | WiFi connection failed |
| 5 s solid on                    | WiFi connected         |
| short · short · long            | AP (setup) mode        |
| Single brief pulse              | Encoder tick / button  |

## Control — physical

| Gesture                  | Action                                                  |
|--------------------------|---------------------------------------------------------|
| Rotate encoder           | ± *step* % per detent, snapped to a multiple of *step*  |
| Short press              | Toggle between current speed ↔ predefined speed         |
| Double click             | Toggle "off" (= *min_speed*) ↔ previous speed           |
| Press-and-hold (≥1 s)    | Boost to *boost_speed* while held; restore on release   |
| Hold at power-on         | Force AP mode                                           |

## Control — REST API

All endpoints return JSON. `GET` unless noted.

| Endpoint                                      | Description                             |
|-----------------------------------------------|-----------------------------------------|
| `/fancontrol/status`                          | Current speed %, RPM, settings, WiFi.   |
| `/fancontrol/up`                              | Step up by *step* %, snapped.           |
| `/fancontrol/down`                            | Step down by *step* %, snapped.         |
| `/fancontrol/push`                            | Same as short-press button.             |
| `/fancontrol/set-predefined?speed=N`          | Persist predefined-speed value (0–100). |
| `/fancontrol/set-speed?speed=N`               | Directly set fan speed (0–100).         |
| `/fancontrol/settings` (GET)                  | Return all settings (no wifi password). |
| `/fancontrol/settings` (POST JSON)            | Update settings. See keys below.        |
| `/fancontrol/wifi` (POST JSON)                | `{ssid, password}` — test and save.     |

### Settings keys (stored in btree `/settings.db`)

| Key                   | Default  | Description                                    |
|-----------------------|----------|------------------------------------------------|
| `current_speed`       | 40       | Live duty %; written by firmware.              |
| `previous_speed`      | 40       | Last non-predefined speed (for toggles).       |
| `predefined_speed`    | 40       | Target of short-press / `/push`.               |
| `boost_speed`         | 100      | Target while hold-to-boost.                    |
| `min_speed`           | 20       | "Off" level for double-click toggle.           |
| `step`                | 5        | % change per encoder tick / up / down.         |
| `pwm_polarity`        | `high`   | `high` = Intel 4-wire spec; `low` to invert.   |
| `tach_pulses_per_rev` | 2        | Standard PC fans = 2.                          |
| `hold_threshold_ms`   | 1000     | Press-hold threshold for boost.                |
| `device_name`         | `PicoFanController` | Used in web UI + AP SSID.           |
| `wifi_ssid`/`wifi_password` | —  | Set via `/fancontrol/wifi`.                    |

## Web UI

Open the Pico's IP in a browser. One page with:

- Large current-speed display and live RPM
- Up / down buttons and a number input for exact speed
- Predefined-speed, boost-speed, min-speed, step, hold threshold, tach PPR,
  PWM polarity, device name — each with ± buttons and number input
- "Save settings" button

## Safety notes

- `boot.py` pulls GPIO16 LOW before firmware starts → fan stays quiet on boot.
  (This is a comfort device, not a cooling-critical one.)
- If the fan misbehaves (e.g. runs full-blast and never slows), flip
  `pwm_polarity` to `low` in the web UI.

## Project layout

```
firmware/
├── boot.py                 # pulls PWM pin low before main runs
├── main.py                 # entry point
├── install.sh
├── deploy.sh
├── lib/
│   ├── config.py           # pin numbers, timings, defaults
│   ├── storage.py          # btree-backed settings
│   ├── fan_controller.py   # PWM + tach
│   ├── encoder.py          # quadrature decode + button FSM
│   ├── led_status.py       # non-blocking LED pattern player
│   ├── wifi_manager.py     # STA + AP mode
│   └── web_server.py       # HTTP server, core 1
└── web/
    ├── index.html
    ├── setup.html
    ├── script.js
    └── style.css
```
