# PicoFanController

A small, quiet controller for a standard 4-wire PC fan, built around a
Raspberry Pi Pico W. Designed for dual duty: solder-fume extractor on the
bench, bedroom fan at night.

Control is by rotary encoder + push-button on the device itself, or over
WiFi via a built-in web UI and REST API. A 10-segment LED bar shows the
current speed at a glance.

## Features

- 25 kHz PWM drive, tachometer read-back, configurable PWM polarity
- Rotary encoder with short-press, double-click and press-and-hold gestures
- Predefined / boost / min speeds, configurable step size
- 10-LED bar graph for speed, also used as WiFi-status indicator at boot
- WiFi client with AP fallback and captive-portal-style setup page
- REST API + responsive web UI (main + advanced settings pages)
- Settings persisted in on-device json storage

## Repository layout

- [`Firmware/`](Firmware/README.md) — MicroPython firmware, web UI, install/deploy scripts
- [`HARDWARE.md`](HARDWARE.md) — schematic, PCB and bill of materials
- `PicoFanController.kicad_*` — KiCad 9 project files

## Getting started

1. Build or assemble the hardware — see [HARDWARE.md](HARDWARE.md).
2. Flash and configure the firmware — see [Firmware/README.md](Firmware/README.md).

## License

The repo is split into two licenses, both noncommercial, both requiring
attribution:

- **Firmware and web UI** (`Firmware/`) — [PolyForm Noncommercial 1.0.0](Firmware/LICENSE).
  A software-specific noncommercial license.
- **Hardware design** (schematic, PCB, `HARDWARE.md`) —
  [CC BY-NC-SA 4.0](LICENSE-HARDWARE). Attribution, noncommercial, share-alike.

In short: do what you like with it for personal, educational or hobby use,
credit the author, and share improvements under the same terms. For
commercial use or anything that would involve claiming ownership, contact
me first.
