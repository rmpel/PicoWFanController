# PicoFanController — Hardware

KiCad 9 project for a small carrier board around a Raspberry Pi Pico W that
drives a 4-wire PC fan and a 10-segment LED bar.

## Files

- `PicoFanController.kicad_sch` — schematic
- `PicoFanController.kicad_pcb` — PCB layout
- `PicoFanController.kicad_pro` / `.kicad_prl` — KiCad project

Open `PicoFanController.kicad_pro` in KiCad 9 or later.

## Main components

- **Raspberry Pi Pico W** — MCU + WiFi, Pico2W should be compatible as well, maybe use a different MicroPython UF2? (untested)
- **IP2721_MAX12** — USB-C PD sink, negotiates 12 V from a PD-capable supply.
  This IC is somewhat hard to source; AliExpress has them but we all know how that goes. 
  CH224K is a relatively easy swap but will require different wiring. Is being researched for future version.
- **Si2302 N-channel MOSFET** — fan enable / hard cut-off - you can do without if you don't need a sof-power-off, short the Source and Drain on the pads.
- **HDSP-4832** — 10-segment LED bar for speed / status
- **Rotary encoder with push-button** — primary user input
- **USB-C receptacles** for power in (via PD), your choice to implement a flat or perpendicular port.
  A 2-pin screw terminal/solder connection is an alternative 12 V input
- Schottky diode, decoupling caps, pull-ups, current-limit resistors for
  the LED bar. Resistor values sub-optimal, software handles relative brightness to compensate

## Power

- 12 V in, either via USB-C PD (through the IP2721_MAX12) or directly on the
  screw terminal.
- 5 V is provided by a tiny buck converter, these are fragile as ... so I am planning my own buck circuit.
- Fan and Pico share GND (MosFet might be in between.

## Links

- [Tiny Buck Converter](https://nl.aliexpress.com/item/1005006366265832.html)
- [IP2721_MAX12](https://nl.aliexpress.com/item/1005009700524003.html)
- [Si2302](https://nl.aliexpress.com/item/1005011884423404.html)
- [LED Bar 10bit 4-color](https://nl.aliexpress.com/item/1005010480139258.html)
- [Rotary Encoder KY040 without PCB](https://nl.aliexpress.com/item/1005005983134515.html)
