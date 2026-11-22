# Smart Range Hood – ESP32 Controller

**Projekt:** Retrofit einer GUTMANN-Dunstabzugshaube  
**Stand:** 21.11.2026  
**Status:** Planung, Hardwareanalyse, KiCad-Einstieg

## 1. Projektziel

Eine hochwertige GUTMANN-Dunstabzugshaube soll nach Verlust der ursprünglichen Steuerplatine wieder funktionsfähig werden. Die ursprüngliche Bedienung hatte Touch-Steuerung, mehrere Lüfterstufen und Beleuchtung. Statt eines Komplettaustauschs wird eine eigene, dokumentierte und reparierbare Steuerung auf ESP32-Basis geplant.

**Funktionen:** Lüfter ein/aus, mehrere Stufen, später Prozent-Schieberegler, Beleuchtung separat, lokale Bedienung, WLAN/MQTT/Home Assistant, optional Nachlauf und Sensorik. Firmware, Schaltplan und PCB sollen in Git versioniert werden.

## 2. Gesicherte Motorinformationen

**GUTMANN 109942-00**, laut Typenschild:

| Parameter | Wert |
|---|---|
| Nennspannung | 230 V AC, 50 Hz |
| Nennstrom | 1,15 A |
| Nennleistung | 260 W |
| Drehzahl | 2100 U/min |
| Betriebskondensator | 6,5 µF, 450 V AC |
| Isolationsklasse | F |

Das Typenschild zeigt die Leitungen **Blau, Schwarz, Braun und Gelb/Grün (PE)** sowie den Kondensator zwischen Schwarz und Braun.

Bereits erfasste Widerstände (aus der bisherigen Unterhaltung):

| Aderpaar | Widerstand |
|---|---:|
| Schwarz–Braun | ca. 92 Ω |
| Blau–Braun | ca. 49 Ω |
| Blau–Schwarz | ca. 42,4 Ω |

**Der Motor wurde bereits erfolgreich in Betrieb genommen.** Eine erneute Grundprüfung ist nicht der nächste Projektschritt.

### Schlussfolgerung und Unsicherheit

Es handelt sich dem Schaltbild nach um einen einphasigen Kondensatormotor. Drei separate Stufenanschlüsse sind nicht nachgewiesen. Die frühere Idee „drei Relais für drei Wicklungsstufen“ ist daher nicht begründet. Ob eine Triac-Phasenanschnittsteuerung für diesen konkreten Motor geeignet ist, muss vor dem Hardwareentwurf fachlich geklärt werden; Alternativen sind zu prüfen. Eine direkte PWM-Ansteuerung des Netzmotors durch den ESP32 ist nicht möglich.

## 3. Beleuchtung

Die fotografierte Lampe ähnelt einer **Halogen-Stiftsockellampe, möglicherweise G4**. Weder Sockeltyp noch Nennspannung sind anhand des Fotos endgültig bestätigt. Vor Auswahl eines LED-Ersatzes und Netzteils müssen Beschriftung, Fassung und vorhandene Versorgung geprüft werden. Eine LED-Umrüstung ist geplant, aber noch nicht dimensioniert.

## 4. Einbauraum

Verfügbare Aufnahme für eine eventuelle Platine: **140 × 180 mm (Breite × Tiefe)**. Die endgültige Leiterplattengröße hängt von Befestigungspunkten, Bauteilhöhen, Anschlüssen, thermischen Bedingungen und Sicherheitsabständen ab.

## 5. Geplante Architektur

```text
230 V AC
  │
  ├── Fachgerecht ausgelegtes Schutz-/Versorgungskonzept
  │       └── isoliertes Kleinspannungsnetzteil → ESP32
  │                                              ├── lokale Bedienung
  │                                              ├── MQTT / Home Assistant
  │                                              ├── Lichtsteuerung
  │                                              └── Motor-Sollwert
  │
  └── geeignete, noch festzulegende Motor-Leistungsstufe → GUTMANN-Motor
```

Motor- und Kleinspannungsbereich müssen sicher getrennt werden. Die Architektur ist ein Konzept, **kein freigegebener 230-V-Verdrahtungsplan**.

## 6. Lüftersteuerung und Prozentwerte

Geplante Bedienmodi:

| Modus | Beispiel-Bedienwert |
|---|---:|
| Aus | 0 % |
| Stufe 1 | 25 % |
| Stufe 2 | 50 % |
| Stufe 3 | 75 % |
| Boost | 100 % |

Die Prozentwerte sind **nur UI-Sollwerte**, keine gemessenen Drehzahlen, Spannungen oder Leistungen. Für den Motor muss eine geeignete Kennlinie samt Mindestbetriebsbereich ermittelt werden. Eine mögliche Anlaufstrategie ist erst nach Motortests festzulegen.

Die Firmware soll zunächst feste Stufen und später ohne grundlegende Änderung der Bedienlogik einen 0–100-%-Schieberegler unterstützen. Ob dafür dieselbe Leistungshardware verwendet werden kann, hängt von deren späterer Auswahl ab.

## 7. ESP32-Firmware

Geplante Anforderungen:

- Definierter sicherer Startzustand und Fehlerzustand
- Lokale Bedienung ohne WLAN
- Lüfterzustandsmaschine und konfigurierbare Stufen
- Getrennte Lichtsteuerung
- Watchdog und Fehlerbehandlung
- MQTT und Home Assistant
- Optional Nachlauf, Filterstunden, Temperaturüberwachung, OTA

## 8. KiCad und Git

**KiCad** wurde bereits heruntergeladen. Die Software ist kostenlos und Open Source. Geplanter Ablauf: Projekt anlegen → Schaltplan → Bauteilauswahl → elektrische Prüfung → PCB-Layout → Design-Rule-Check → Fertigungsdaten. Eine Spende an KiCad ist freiwillig.

Vorgeschlagene Repository-Struktur:

```text
smart-range-hood-esp32/
├── README.md
├── firmware/
│   ├── platformio.ini
│   ├── src/
│   ├── include/
│   └── test/
├── hardware/
│   ├── kicad/
│   ├── gerber/
│   └── bom/
└── docs/
    ├── motor.md
    ├── lighting.md
    ├── architecture.md
    ├── safety.md
    └── commissioning.md
```

## 9. Sicherheit

Die Haube enthält **230 V AC** und einen **260-W-Induktionsmotor**. Eine lose Lochrasterverdrahtung eignet sich allenfalls für vollständig isolierte Kleinspannungs-Prototypen, nicht für den Netzspannungsteil. Erforderlich sind insbesondere Schutzleiterkonzept, geeignete Absicherung, Isolation, Kriech- und Luftstrecken, Berührungsschutz, Zugentlastung, thermische Auslegung, EMV und Schutz gegen Fett/Feuchtigkeit. Auslegung und Prüfung der Netzspannungsbaugruppe gehören in fachkundige Hände.

## 10. Aufgabenliste

- [x] Motortypenschild und Daten dokumentiert
- [x] Wicklungswiderstände erfasst
- [x] Motor erfolgreich betrieben
- [x] Bauraum 140 × 180 mm erfasst
- [x] KiCad heruntergeladen
- [ ] Beleuchtung eindeutig identifizieren
- [ ] Vorhandene Kabel, Steckverbinder und Befestigungen dokumentieren
- [ ] Motorverträgliches Regelverfahren auswählen und validieren
- [ ] Versorgung und Schutzkonzept entwerfen
- [ ] ESP32- und Bedienkonzept festlegen
- [ ] KiCad-Schaltplan für Kleinspannung erstellen
- [ ] Firmware mit Zustandsmaschine aufbauen
- [ ] Netzspannungs-Leistungsstufe fachgerecht entwickeln und prüfen
- [ ] PCB entwerfen und prüfen
- [ ] Home Assistant/MQTT integrieren
- [ ] Inbetriebnahme und Kalibrierung dokumentieren

## 11. Nächster sinnvoller Schritt

Ein KiCad-Projekt anlegen und zunächst die **Kleinspannungsarchitektur** mit ESP32, Bedienung und Schnittstellen planen. Parallel das geeignete Regelverfahren für den vorhandenen Kondensatormotor klären, bevor eine 230-V-Leistungsplatine ausgelegt wird.

---

**Projektprinzip:** Bestehende hochwertige Mechanik erhalten, fehlende Elektronik sicher und nachvollziehbar ersetzen und die Entwicklung auf GitHub dokumentieren.
