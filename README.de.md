# Smart Range Hood ESP32

[English](README.md) · **Deutsch**

**Open-Source-ESP32-Steuerung für eine GUTMANN-Dunstabzugshaube**

Ein Open-Source-Projekt, das die nicht mehr lieferbare Originalsteuerung einer GUTMANN-Dunstabzugshaube durch eine eigene Steuerung auf ESP32-Basis ersetzt.

Das Projekt verbindet Embedded-Firmware, Platinenentwurf mit KiCad, lokale Bedienung und eine optionale Smart-Home-Anbindung über MQTT und Home Assistant.

## Projektziele

- Die Originalsteuerplatine der Haube ersetzen
- Lüfter und Beleuchtung steuern
- Mehrere Lüfterstufen und einen Boost-Modus bieten
- Lokale Bedienung ohne WLAN ermöglichen
- Über MQTT in Home Assistant einbinden
- Eine dokumentierte, wartbare Hardware- und Softwarelösung entwickeln

## Vorhandene Hardware

| Komponente | Daten |
|---|---|
| Dunstabzugshaube | GUTMANN |
| Motor | 109942-00 |
| Versorgung | 230 V AC / 50 Hz |
| Nennleistung | 260 W |
| Nennstrom | 1,15 A |
| Nenndrehzahl | 2100 min⁻¹ |
| Betriebskondensator | 6,5 µF / 450 V AC |
| Verfügbarer Platz für die Platine | 140 × 180 mm |
| Netzfilter | Schurter FMW2-52-6/0.5 (5500.2044), 6 A – bleibt in der Zuleitung |
| Beleuchtung | 12-V-G4-Spots (werden durch G4-LEDs ersetzt) |
| Controller | ESP32-WROOM-32U DevKitC V4 |

Der Motor wurde bei voller Drehzahl erfolgreich getestet.

Der Motor ist ein einphasiger Kondensatormotor (PSC): Hauptwicklung, Hilfswicklung mit 6,5-µF-Betriebskondensator, Thermowächter. Er hat keine Drehzahlanzapfungen.

## Drehzahlsteuerung

**Kapazitive Stufensteuerung** (keine Phasenanschnittsteuerung – PSC-Motoren brummen und überhitzen an Triac-Dimmern):

| Stufe | Relais | Vorschalt-Becherkondensator | Hinweis |
|---|---|---|---|
| 3 (voll) | K1 | keiner, direkt | wie der Motor direkt am Netz |
| 2 | K4 | ca. 15–20 µF / 450 V AC | Schätzung, im Testaufbau abgleichen |
| 1 | K3 | ca. 10–12 µF / 450 V AC | Schätzung, im Testaufbau abgleichen |
| (Reserve) | K2 | – | optionale 4. Stufe |

Ein Vorschalt-Becherkondensator wirkt als nahezu verlustfreier Blindwiderstand (X = 1/(2πfC)) und senkt die Motorspannung. Die Relais sind in der Firmware gegeneinander verriegelt; jeder Start aus dem Stillstand läuft 2 s auf voller Drehzahl (Anlaufhilfe), bevor auf die Zielstufe heruntergeschaltet wird.

Abschätzung: Motor ≈ 200 Ω (230 V / 1,15 A, mit Betriebskondensator nahezu ohmsch); Motorspannung = 230 V · R / √(R² + X_C²). Die Werte werden auf dem Prüfstand bestätigt, bevor die Platine bestellt wird – siehe [Testaufbau](docs/images/testaufbau-kondensatoren.png).

## Geplante Architektur

```text
Lokale Bedienung
         |
         v
       ESP32 <---- WLAN / MQTT
         |              |
         |        Home Assistant
         |
         v
ULN2003A Relaistreiber         AO3400A MOSFET
         |                            |
   4 Relais (Finder 40.31)      12-V-LED-Beleuchtung (PWM-Dimmung)
         |
   Vorschalt-Becherkondensatoren  ---->  Lüftermotor (PSC, 230 V)

Netz: Sicherung T 2,5 A, Varistor, X2-Kondensator, Mean Well IRM-20-12 (galvanisch getrennte 12 V)
Rückfallebene: Shelly BLU Button (BLE, funktioniert ohne WLAN)
```

## Aufbau des Repositorys

```text
smart-range-hood-esp32/
├── README.md                 # englisch
├── README.de.md              # deutsch
├── docs/
│   ├── konzept.md            # vollständiges Konzept, Checklisten, Testplan
│   └── images/               # Typenschilder, Filter, Anschlussraum der Haube
├── hardware/
│   ├── kicad/                # Python-Generatoren + KiCad-Projekt
│   │   ├── generate_schematic.py
│   │   ├── generate_pcb.py   # Platzierung, Netzklassen, Designregeln
│   │   ├── route_pcb.py      # eigener Router (8 mm Netz/SELV, 3 mm Netz/Netz)
│   │   ├── make_3d_terminals.py
│   │   └── dunstabzug-steuerplatine/
│   ├── gerber/               # Fertigungsdaten
│   ├── traegerplatte/        # Bohrschablone der Trägerplatte 1:1 (Python → SVG)
│   └── einkaufsliste-reichelt.md   # Stückliste mit Reichelt-Links
└── firmware/
    └── esphome/              # ESPHome-Testkonfigurationen
```

## Fahrplan

- [x] Motordaten ermitteln
- [x] Motorbetrieb bei voller Drehzahl prüfen
- [x] Geeignetes Verfahren zur Drehzahlsteuerung festlegen
- [x] Versorgung und Ansteuerung der Beleuchtung klären
- [x] ESP32-Hardwarearchitektur festlegen
- [x] KiCad-Schaltplan erstellen
- [x] Platine entwerfen (160 × 100 mm, 2 Lagen, THT, DRC fehlerfrei)
- [ ] Werte der Vorschalt-Becherkondensatoren im Testaufbau ermitteln
- [ ] Netzseite elektrisch prüfen lassen, dann Platine bestellen
- [ ] ESP32-Firmware umsetzen (ESPHome-Testkonfigurationen vorhanden)
- [ ] MQTT und Home Assistant einbinden
- [ ] Elektrische Sicherheits- und Funktionsprüfung durchführen

## Platine aus den Quellen erzeugen

```bash
KP=/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/3.9/bin/python3   # Python von KiCad (macOS)
cd hardware/kicad
$KP generate_schematic.py
$KP generate_pcb.py && python3 route_pcb.py && $KP generate_pcb.py --apply-routes
```

## Elektrische Sicherheit

Dieses Projekt arbeitet mit **230 V AC Netzspannung** und einem Motor mit Betriebskondensator.

Die ESP32-Kleinspannungsseite muss von den gefährlichen Netzstromkreisen galvanisch getrennt sein. Schutzmaßnahmen, Kriech- und Luftstrecken, Wärmeabfuhr, Anforderungen an das Gehäuse und EMV müssen berücksichtigt werden.

Die Motorsteuerung darf nicht mit einem ungeprüften Dimmer oder einer PWM-Schaltung umgesetzt werden. Jede netzbetriebene Hardware muss vor dem Betrieb fachkundig geprüft werden.

## Projektstand

**Platine entworfen, elektrische Prüfung und Testaufbau stehen aus.**

Schaltplan (ERC fehlerfrei), geroutete Platine (DRC fehlerfrei, 8 mm Luft- und Kriechstrecke Netz ↔ SELV mit Frässchlitz, 3 mm Netz ↔ Netz) und Gerber-Dateien liegen vor. Noch nicht aufgebaut oder getestet – nicht unverändert verwenden.

## Lizenz

Noch offen.

---

Entwickelt von **Bavarian Data Forge**.
