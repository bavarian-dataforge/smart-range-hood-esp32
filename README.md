# Smart Range Hood ESP32

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
| Controller | ESP32 (planned) |

The motor has been successfully tested at full speed.

**Important:** The motor speed-control method has not yet been validated. Compatibility with phase-angle control or other regulation methods must be established before implementation.

The lighting voltage and driver requirements also remain to be verified.

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
Isolated Control Interface
         |
         v
Certified / Suitable Power Stage
         |
         +---- Fan Motor
         |
         +---- Lighting
```

## Repository Structure (Planned)

```text
smart-range-hood-esp32/
├── README.md
├── docs/
│   ├── requirements.md
│   ├── hardware.md
│   └── safety.md
├── hardware/
│   └── kicad/
├── firmware/
│   └── esp32/
└── tests/
```

## Development Roadmap

- [x] Identify motor specifications
- [x] Verify motor operation at full speed
- [ ] Confirm suitable motor speed-control method
- [ ] Identify lighting supply and control requirements
- [ ] Define ESP32 hardware architecture
- [ ] Create KiCad schematic
- [ ] Design PCB
- [ ] Implement ESP32 firmware
- [ ] Integrate MQTT and Home Assistant
- [ ] Perform electrical safety and functional testing

## Electrical Safety

This project involves **230 V AC mains voltage** and a motor with a run capacitor.

The ESP32 low-voltage circuitry must be galvanically isolated from hazardous mains circuits. Appropriate protection, creepage and clearance distances, thermal design, enclosure requirements and EMC considerations must be addressed.

Motor control must not be implemented using an unverified dimmer or PWM circuit. Any mains-powered hardware requires appropriate professional review and testing before operation.

## Project Status

**Early development — requirements and hardware investigation.**

No finished PCB, validated motor regulator or production-ready firmware is available yet.

## License

To be determined.

---

Developed by **Bavarian Data Forge**.
