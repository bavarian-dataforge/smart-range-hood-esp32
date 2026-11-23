# Smart Range Hood ESP32

**English** · [Deutsch](README.de.md)

**Open-source ESP32 controller for a GUTMANN kitchen range hood**

An open-source project to replace the unavailable original control electronics of a GUTMANN kitchen extractor hood with a custom ESP32-based controller.

The project combines embedded firmware, PCB design with KiCad, local operation and optional smart-home integration via MQTT and Home Assistant.

## Project Goals

- Replace the original range hood control board
- Control fan operation and lighting
- Provide multiple fan speed levels and a boost mode
- Support local operation without Wi-Fi
- Integrate with Home Assistant via MQTT
- Develop a documented, maintainable hardware and software solution

## Existing Hardware

| Component | Specification |
|---|---|
| Range hood | GUTMANN |
| Motor | 109942-00 |
| Supply | 230 V AC / 50 Hz |
| Rated power | 260 W |
| Rated current | 1.15 A |
| Rated speed | 2100 rpm |
| Run capacitor | 6.5 µF / 450 V AC |
| Available PCB space | 140 × 180 mm |
| EMI filter | Schurter FMW2-52-6/0.5 (5500.2044), 6 A — kept in the supply line |
| Lighting | 12 V G4 spots (to be replaced by G4 LED) |
| Controller | ESP32-WROOM-32U DevKitC V4 |

The motor has been successfully tested at full speed.

The motor is a single-phase permanent-split capacitor (PSC) motor: main winding, auxiliary winding with a 6.5 µF run capacitor, thermal cut-out. It has no speed taps.

## Speed Control

**Capacitive step speed control** (no phase-angle control — PSC motors hum and overheat on triac dimmers):

| Level | Relay | Series capacitor | Note |
|---|---|---|---|
| 3 (full) | K1 | none, direct | identical to the motor on mains |
| 2 | K4 | ~15–20 µF / 450 V AC | estimate, tune in bench test |
| 1 | K3 | ~10–12 µF / 450 V AC | estimate, tune in bench test |
| (reserve) | K2 | — | optional 4th level |

A series capacitor acts as a nearly loss-free reactance (X = 1/(2πfC)) and lowers the motor voltage. Relays are interlocked in firmware; every start from standstill runs 2 s at full speed (kick-start) before dropping to the target level.

Estimate: motor ≈ 200 Ω (230 V / 1.15 A, nearly resistive with its run capacitor); motor voltage = 230 V · R / √(R² + X_C²). The values are validated on the bench before the PCB is ordered — see [test setup](docs/images/testaufbau-kondensatoren.png).

## Planned Architecture

```text
Local User Interface
         |
         v
       ESP32 <---- Wi-Fi / MQTT
         |              |
         |        Home Assistant
         |
         v
ULN2003A relay driver          AO3400A MOSFET
         |                            |
   4 relays (Finder 40.31)      12 V LED lighting (PWM dimming)
         |
   series capacitors  ---->  Fan motor (PSC, 230 V)

Mains: fuse T 2.5 A, varistor, X2 capacitor, Mean Well IRM-20-12 (isolated 12 V)
Fallback control: Shelly BLU button (BLE, works without Wi-Fi)
```

## Repository Structure

```text
smart-range-hood-esp32/
├── README.md                 # English
├── README.de.md              # German
├── docs/
│   ├── konzept.md            # full concept, checklists, test plan (German)
│   └── images/               # nameplates, filter, hood terminal space
├── hardware/
│   ├── kicad/                # Python generators + KiCad project
│   │   ├── generate_schematic.py
│   │   ├── generate_pcb.py   # placement, net classes, design rules
│   │   ├── route_pcb.py      # own router (8 mm mains/SELV, 3 mm mains/mains)
│   │   ├── make_3d_terminals.py
│   │   └── dunstabzug-steuerplatine/
│   ├── gerber/               # fabrication output
│   ├── traegerplatte/        # carrier plate drilling template 1:1 (Python → SVG)
│   └── einkaufsliste-reichelt.md   # BOM with Reichelt links (German)
└── firmware/
    └── esphome/              # ESPHome test configurations
```

## Development Roadmap

- [x] Identify motor specifications
- [x] Verify motor operation at full speed
- [x] Confirm suitable motor speed-control method
- [x] Identify lighting supply and control requirements
- [x] Define ESP32 hardware architecture
- [x] Create KiCad schematic
- [x] Design PCB (160 × 100 mm, 2 layers, THT, DRC clean)
- [ ] Bench-test series capacitor values
- [ ] Electrical review of the mains side, then order PCB
- [ ] Implement ESP32 firmware (ESPHome test configs exist)
- [ ] Integrate MQTT and Home Assistant
- [ ] Perform electrical safety and functional testing

## Build the PCB from source

```bash
KP=/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/3.9/bin/python3   # KiCad's Python (macOS)
cd hardware/kicad
$KP generate_schematic.py
$KP generate_pcb.py && python3 route_pcb.py && $KP generate_pcb.py --apply-routes
```

## Electrical Safety

This project involves **230 V AC mains voltage** and a motor with a run capacitor.

The ESP32 low-voltage circuitry must be galvanically isolated from hazardous mains circuits. Appropriate protection, creepage and clearance distances, thermal design, enclosure requirements and EMC considerations must be addressed.

Motor control must not be implemented using an unverified dimmer or PWM circuit. Any mains-powered hardware requires appropriate professional review and testing before operation.

## Project Status

**PCB designed, awaiting electrical review and bench test.**

Schematic (ERC clean), routed PCB (DRC clean, 8 mm clearance/creepage mains ↔ SELV with milled slot, 3 mm mains ↔ mains) and Gerber files exist. Not yet built or tested — do not use as-is.

## License

To be determined.

---

Developed by **Bavarian Data Forge**.
