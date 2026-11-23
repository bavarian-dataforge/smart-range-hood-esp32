# Smart Range Hood – ESP32 Controller

**Projekt:** Retrofit einer GUTMANN-Dunstabzugshaube
**Stand:** 21.11.2026
**Status:** Planung, Hardwareanalyse, Auswahl des Regelverfahrens
**Backup der Vorversion:** `Wissen/Backups/KuechenDunstabzugshaube/Smart-Range-Hood-ESP32_2026-11-21.md`

## 1. Projektziel

Die GUTMANN-Inselhaube hat keine funktionierende Steuerung mehr. Das Original-Display an der Front ist defekt, und die Originalplatine wieder in Betrieb zu nehmen wäre zu aufwendig. Die Haube wird deshalb komplett smart gesteuert. Statt eines Komplettaustauschs entsteht eine eigene, dokumentierte und reparierbare Steuerung auf ESP32-Basis.

**Funktionen:**

- Lüfter aus, feste Stufen, Boost; später optional 0–100-%-Regler
- Beleuchtung separat schaltbar (optional dimmbar)
- Bedienung smart über den ESP32: Home Assistant / App / ESPHome-Weboberfläche, kein Display an der Haube
- Home Assistant über ESPHome (native API, MQTT nicht nötig)
- Steuerelektronik **außerhalb der Fettzone** in der Kaminverkleidung
- Optional: Nachlauf, Filterstunden, Temperaturüberwachung

Firmware (ESPHome-YAML), Schaltplan und PCB werden in Git versioniert.

**Entscheidungen (21.11.2026):**

| Thema | Entscheidung |
|---|---|
| Firmware | ESPHome |
| Bauform | Inselhaube, zweiteiliger Edelstahlkamin bis zur abgehängten Decke  |
| Bedienung | Smart über Home Assistant/App. Original-Display defekt und wird nicht mehr genutzt. Der Drehknopf an der Front gehört zum Induktionskochfeld, nicht zur Haube |
| Bedienung ohne WLAN | BLE-Funktaster, den der ESP32 direkt auswertet (Abschnitt 5) |
| Einbauort Elektronik | Im Aufnahmeraum der alten Steuerung auf einer FR4-Trägerplatte, ohne eigenes Gehäuse (Abschnitt 5a, Entscheidung 23.11.2026) |
| Lüfterregelung | Relais/Kondensatorstufen und Triac vergleichen, Entscheidung nach Tests |

## 2. Motor

**GUTMANN 109942-00**, laut Typenschild:

| Parameter | Wert |
|---|---|
| Nennspannung | 230 V AC, 50 Hz |
| Nennstrom | 1,15 A |
| Nennleistung | 260 W |
| Drehzahl | 2100 U/min |
| Betriebskondensator | 6,5 µF, 450 V AC |
| Isolationsklasse | F |

Leitungen laut Typenschild: **Blau, Schwarz, Braun, Gelb/Grün (PE)**. Der Kondensator liegt zwischen Schwarz und Braun.

Gemessene Widerstände:

| Aderpaar | Widerstand |
|---|---:|
| Schwarz–Braun | ca. 92 Ω |
| Blau–Braun | ca. 49 Ω |
| Blau–Schwarz | ca. 42,4 Ω |

**Der Motor wurde bereits erfolgreich betrieben:** mit seinem eigenen Betriebskondensator, über einen einfachen Schalter direkt an 230 V AC (volle Drehzahl).

### Auswertung

- 42,4 Ω + 49 Ω = 91,4 Ω ≈ 92 Ω. Es gibt also genau **zwei Wicklungen** mit **Blau als gemeinsamem Punkt**.
- Damit ist der Motor ein **Kondensatormotor (PSC) ohne Stufenanzapfungen**. Die frühere Idee „drei Relais für drei Wicklungsstufen" entfällt endgültig.
- Laut Schaltbild auf dem Typenschild: **Blau = L** (über den Thermowächter TW), **Schwarz = N**, Gelb/Grün = PE, Betriebskondensator zwischen Schwarz und Braun. Blau ist der gemeinsame Punkt beider Wicklungen.
- **Offen:** Die Verdrahtung, mit der der Motor bereits lief (welche Ader an L, Drehrichtung), muss mit Foto dokumentiert werden. Sie ist die Referenz für alles Weitere.
- Thermoschutz: Das Typenschild zeigt einen Thermowächter (TW) in der blauen Ader, im Motor eingebaut.

Eine direkte PWM-Ansteuerung des Netzmotors durch den ESP32 ist nicht möglich. Ein Frequenzumrichter ist für einen PSC-Motor mit festem Betriebskondensator ungeeignet.

## 3. Lüfterregelung: Verfahren im Vergleich

Beide Hauptkandidaten werden getestet, danach fällt die Entscheidung.

| Kriterium | A: Relais + Vorschaltkondensatoren | B: Triac-Phasenanschnitt | C: Stufentransformator |
|---|---|---|---|
| Prinzip | Kondensator in Reihe vor den Motor senkt die Motorspannung; Relais wählen die Kombination | Triac schneidet einen Teil jeder Halbwelle ab | Spartrafo mit Anzapfungen, Relais wählen die Spannung |
| Stufen | Fest (3–4 + Boost) | Stufenlos | Fest |
| Geräusch | Leise, kein Brummen | Brummen bei niedriger Drehzahl möglich | Leise, Trafo kann summen |
| Wärme | Gering | Triac und Motor werden wärmer, Kühlkörper nötig | Trafoverluste |
| EMV | Unkritisch | Funkstörungen, Netzfilter nötig | Unkritisch |
| Aufwand Hardware | Relais, X2/MKP-Kondensatoren, Entladewiderstände | Nulldurchgangserkennung, Optotriac (nicht nullspannungsschaltend), Triac, Snubber, Filter | Großes, schweres Bauteil |
| ESPHome | `template`-Fan, Relais per Logik | `ac_dimmer` + `speed`-Fan | `template`-Fan |
| Bauraum 140 × 180 mm | Passt | Passt | Kritisch |

**Hinweise zu A:** Die Kondensatorwerte (typisch einige µF) werden empirisch ermittelt. Relais für induktive Last und Einschaltstrom auslegen. Firmware verriegelt die Relais gegeneinander, Wechsel nur über kurzen Aus-Zustand. Boost = Motor direkt am Netz.

### Variante A im Detail (erste Priorität)

**Zwei verschiedene Kondensatoren:** Der vorhandene **Betriebskondensator (6,5 µF)** bleibt unverändert am Motor. Er versorgt die Hilfswicklung und erzeugt das Drehfeld, ohne ihn läuft der Motor nicht. Die **Vorschaltkondensatoren CM1–CM3** sind zusätzlich und liegen in der Zuleitung vor dem Motor. Sie senken die Motorspannung und damit die Drehzahl. Ein Schalter allein kennt nur „aus" und „volle Drehzahl".

```text
L ──[Sicherung]──┬── K1 (Boost) ──────────────┐
                 ├── K2 ──[CM1]────────────────┤
                 ├── K3 ──[CM2]────────────────┼──► Motoranschluss L (wie bisher am Schalter)
                 └── K4 ──[CM3]────────────────┘
N ──────────────────────────────────────────────► Motoranschluss N (Blau)
PE ─────────────────────────────────────────────► Motor/Gehäuse
                     CM1 < CM2 < CM3, jeweils mit Entladewiderstand parallel
```

Konzeptskizze, **kein freigegebener Verdrahtungsplan**. Der Motor bleibt intern so verdrahtet, wie er am Schalter lief; K1–K4 ersetzen nur den Schalter.

**Ausbau in zwei Schritten:**

1. **Nur K1:** Ein Relais ersetzt den bisherigen Schalter. Die Haube ist sofort smart (an/aus, volle Drehzahl).
2. **K2–K4 + CM1–CM3:** Stufen nachrüsten.

**Bauteile (Richtwerte, Auswahl durch Fachkraft):**

| Teil | Anforderung |
|---|---|
| Relais K1–K4 | 230 V AC, ≥ 10 A Kontakt (Einschaltstrom), Spule 5 V oder 12 V mit Treiber/Freilaufdiode; im Testaufbau Relaismodul nur in geschlossenem Gehäuse |
| CM1–CM3 | MKP-Motorkondensatoren oder X2, ≥ 450 V AC. **Startwerte für den Versuch: 4 µF, 6 µF, 8 µF** (nicht berechnet, werden nach Messung angepasst) |
| Entladewiderstände | Je Kondensator ca. 470 kΩ–1 MΩ, spannungsfest (≥ 400 V Bauform bzw. zwei in Reihe) |
| Sicherung | Träge, Wert durch Fachkraft (Motor 1,15 A Nennstrom) |

**Zusätzliche Messung im Testplan:** Motorspannung bei jeder Stufe. Sie muss **unter 230 V** liegen. Ein Reihenkondensator kann zusammen mit der Motorinduktivität eine Spannungsüberhöhung erzeugen; ist das der Fall, Kondensatorwert ändern.

**Firmware:** [`esphome/dunstabzug-motor-test.yaml`](../firmware/esphome/dunstabzug-motor-test.yaml): Template-Fan mit 4 Stufen, interne und gegeneinander verriegelte Relais, Umschaltpause 300 ms, Anlauf aus dem Stillstand 2 s mit Boost, nach Neustart alles aus. Für Schritt 1 in Home Assistant Stufe 4 (Boost) wählen.

**Hinweise zu B:** Mindest-Ansteuerung festlegen, unterhalb der der Motor nicht sicher läuft. Anlaufstrategie: kurz voll anlaufen, dann auf Sollwert. Für Boost ein Bypass-Relais parallel zum Triac vorsehen, das entlastet den Triac thermisch.

**Hybrid denkbar:** Relais für Aus/Boost und Netztrennung, Triac nur für den Teillastbereich.

**C** wird nur weiterverfolgt, wenn A und B scheitern.

### Testplan (Leistungsteil durch Elektrofachkraft aufgebaut)

Pro Stufe bzw. Ansteuerwert messen und tabellarisch festhalten:

| Messgröße | Werkzeug |
|---|---|
| Strom und Leistung | Energiemessgerät (Steckdose) |
| Drehzahl | Optischer Drehzahlmesser oder Smartphone-App |
| Geräusch | Subjektiv + Schallpegel-App |
| Gehäusetemperatur Motor nach 30 min | IR-Thermometer |
| Anlauf aus dem Stillstand | Läuft an: ja/nein, Zeit |

Daraus ergibt sich die Kennlinie „UI-Prozent → Ansteuerwert" und die Mindeststufe.

## 4. Beleuchtung

Stand 22.11.2026:

- **Spots:** Fassung G4, bisher **Halogen 12 V** über einen eigenen Trafo, funktionieren. Sie werden durch **LED-G4 12 V** ersetzt (z. B. 1,8 W, 185 lm, 3000 K, siehe Einkaufsliste) und über J5 und den MOSFET Q1 geschaltet und per PWM gedimmt. Der Halogentrafo entfällt; die 12 V DC kommen von PS1.
- **Milchglas-Beleuchtung:** Typ unbekannt, nicht zugänglich. **Entfällt.**

Zu prüfen beim Anschluss:

- Gesamtleistung der Spots (Aufdruck oder messen). Bis ca. 15 W reicht PS1 (IRM-20-12) zusammen mit Relais und ESP32.
- Flimmern beim Dimmen: Falls die LEDs bei PWM flackern, in ESPHome die PWM-Frequenz erhöhen oder das Licht nur schalten statt dimmen.

## 5. Bedienung

Die Haube wird **smart bedient**. Das defekte Original-Display und seine Platine werden nicht mehr genutzt. Der Drehknopf an der Front gehört zum Induktionskochfeld und bleibt unberührt.

| Ebene | Umsetzung | Funktioniert ohne WLAN/HA |
|---|---|---|
| Hauptbedienung | Home-Assistant-Dashboard / App | Nein |
| Direktzugriff im Heimnetz | ESPHome-Weboberfläche (`web_server`) | Nur WLAN nötig, kein HA |
| Automatik (optional) | HA-Automationen, z. B. Lüfter an, wenn das Kochfeld Leistung zieht (Messung über smarte Steckdose/Zähler, falls vorhanden) | Nein |
| Bedienung vor Ort | BLE-Funktaster an der Haube, direkt vom ESP32 ausgewertet | Ja |

### BLE-Funktaster

**Prinzip:** Ein batteriebetriebener Bluetooth-Low-Energy-Taster sendet bei jedem Druck kurze Funkpakete („Advertisements") an alle Empfänger in Reichweite. Es gibt keine Kopplung und keine Verbindung. Der ESP32 lauscht mit `esp32_ble_tracker`, erkennt den Taster an seiner MAC-Adresse und schaltet direkt. Weder WLAN noch Home Assistant werden gebraucht.

- **Beispielgerät:** Shelly BLU Button1 (CR2032, sendet im offenen BTHome-Format, kennt Einfach-, Doppel-, Dreifach- und Langdruck). Alternativen müssen ihre Pakete unverschlüsselt oder mit bekanntem Schlüssel senden.
- **Auswertung in ESPHome:** `on_ble_service_data_advertise` auf die BTHome-UUID `0xFCD2` und die MAC des Tasters filtern, Tastenereignis aus den Daten lesen. Eine Paketnummer im BTHome-Paket verhindert Doppelauslösung, weil der Taster jedes Ereignis mehrfach sendet.
- **Belegung (Vorschlag):**

  | Druck | Aktion |
  |---|---|
  | 1× | Lüfter an bzw. nächste Stufe |
  | 2× | Licht an/aus |
  | 3× | Nachlauf starten |
  | Lang | Lüfter aus |

- **Montage:** Vorne an der Haubenfront (festgelegt). Die Front ist magnetisch, ein Magnet- oder Klebehalter macht den Taster abnehmbar für Batteriewechsel und Reinigung. Nicht in den Dampfbereich unter der Haube setzen; zulässigen Temperaturbereich des Tasters prüfen.
- **Konfiguration:** [`esphome/dunstabzug-ble-test.yaml`](../firmware/esphome/dunstabzug-ble-test.yaml) – Testkonfiguration für ein Dev-Board ohne Netzspannung, Lüfter und Licht als Platzhalter.
- **Funk:** Bluetooth nutzt dasselbe 2,4-GHz-Band und dieselbe Antenne wie WLAN. Die externe Antenne (Abschnitt 5a) ist damit auch für den Taster wichtig. ESP32 kann WLAN und BLE gleichzeitig, Scan-Parameter (`interval`/`window`) so wählen, dass WLAN stabil bleibt.
- **Batterie:** Batteriestand meldet der Taster mit; in Home Assistant eine Warnung anlegen.
- Der Taster wird zusätzlich auch in Home Assistant sichtbar (z. B. über den ESP32 als Bluetooth-Proxy) und kann dort für Automationen genutzt werden.

**Display-Fenster:** Mit einer Blende verschließen (Kunststoff/Edelstahl, ggf. 3D-Druck). Optional später eine Status-LED dahinter, dann aber nur Kleinspannung an der Front.

## 5a. Einbauort: Aufnahmeraum der alten Steuerung

Die Haube ist eine große **Inselhaube** mit zweiteiligem Edelstahlkamin bis zur abgehängten Decke. Die neue Steuerung kommt **an die Stelle der alten**: in den Aufnahmeraum der Originalsteuerung (145 × 220 mm, Auflageleisten 10 mm, Laschen vorne). Platine und Becherkondensatoren sitzen auf einer isolierenden **Trägerplatte** (FR4 3 mm, 143 × 205 mm), die eingeschoben und an den Laschen verschraubt wird. Maße und Bohrbild: [Bohrschablone](../hardware/traegerplatte/) und [Draufsicht](images/einbau-draufsicht.png).

**Kein eigenes Gehäuse (Entscheidung 23.11.2026).** Die Originalsteuerung saß ebenfalls offen im Aufnahmeraum. Der Raum selbst übernimmt die Aufgaben des Gehäuses, solange diese Bedingungen erfüllt sind:

- **Geschlossen:** Im Betrieb ist die Abdeckung montiert, keine spannungsführenden Teile sind berührbar.
- **Nur mit Werkzeug zu öffnen:** verschraubt, nicht nur gesteckt.
- **Metall und am PE:** Der Raum ist zugleich Brandschutzgehäuse, z. B. für einen ausfallenden Becherkondensator (Sicherheitsklasse S0).
- **Isolierend getragen:** Die Platine sitzt auf Abstandsbolzen auf der FR4-Platte, nicht direkt auf Blech. Randabstände zum Metall trotzdem einhalten, vor allem auf der Netzseite.
- **Zugentlastung:** Alle Leitungen mit Kabelbindern auf der Trägerplatte fixieren (Löcher in der Schablone), keine Adern an Blechkanten.
- **Temperatur:** Die Abluft strömt außerhalb des Raums vorbei (ca. 30–70 °C). Der DS18B20 an J6 überwacht die Temperatur im Raum und warnt ab 60 °C.
- **Fett:** Der Raum liegt geschützt im Haubenkörper. Bei der Wartung auf Fettablagerungen prüfen, ggf. Schutzlack auf die Platine.

Weitere Punkte:

- **WLAN:** Kamin und Front sind aus Edelstahl (Front magnetisch), das schirmt Funk stark ab. ESP32-Modul mit Antennenbuchse (ESP32-WROOM-32**U**) und externer Antenne, Antenne durch eine Tülle nach außen führen. Vorher mit einem Dev-Board im eingebauten Zustand den Empfang testen.
- **Leitungen:** Netz, Motor und Licht liegen bereits im Aufnahmeraum (Tabelle unten). Der Betriebskondensator bleibt am Motor. Querschnitte und Leitungsart (Temperaturbeständigkeit) durch die Fachkraft bestätigen.
- **Offen:** nutzbare Höhe ≥ 100 mm (stehender Becherkondensator mit M8-Bolzen ≈ 95 mm).
- **Testaufbau:** Für den Versuch auf dem Tisch liegen 230 V und geladene Becherkondensatoren offen. Dafür ist ein geschlossenes Testgehäuse sinnvoll (Einkaufsliste, optional). Wird direkt in der Haube getestet, nur spannungsfrei umstecken und im Betrieb abdecken.

### Vorhandene Leitungen im Anschlussraum (Stand 23.11.2026)

Aufgenommen nach Fotos (die Fotos bleiben privat und liegen nicht im Repo). Zuordnung vor dem Anschluss **spannungsfrei durchmessen** (Durchgang, Isolation).

| Leitung | Adern / Farbe | Anschluss heute | Bedeutung |
|---|---|---|---|
| Netzzuleitung 230 V AC | Braun (graue Mantelleitung), dazu N | rote isolierte Flachsteckhülse 6,3 mm | Braun = L (zu bestätigen); N-Ader durchmessen |
| Schutzleiter | Gelb/Grün | roter Ringkabelschuh | PE an Gehäuse/Masse |
| Motor | Blau, Schwarz (Braun nur zum Betriebskondensator) | 3-polige Lüsterklemme | Laut Typenschild Blau = L (über TW), Schwarz = N |
| Abgang Lüsterklemme | Grau, Schwarz, dünne weiße Ader | eine Ader mit WAGO-Klemme, Grau mit offenem Litzenende | ging zur alten Steuerung; Zuordnung zu den Motoradern durchmessen |
| Licht „Spot“ | kurze weiße Mantelleitung, Braun + Blau, beschriftet „Spot“ | lose | **12 V DC**, mit Labornetzteil erfolgreich getestet (23.11.2026) → J5 / MOSFET Q1 |
| Beleuchtung (lange weiße Leitung) | Braun + Blau | Blau über roten Stoßverbinder verlängert, endet in roter Flachsteckhülse | geht links durch die Wand zur Beleuchtung; Spannung und Art (AC/DC, Trafo/Treiber in der Leuchte?) **unbekannt** – zuletzt klären |

Hinweise:

- Offene Litzenenden isolieren (Klemme/Aderendhülse), solange die Haube am Netz hängt.
- Zum Licht: Abschnitt 4 geht von 12-V-Halogen-G4 mit eigenem Trafo aus. Es gibt zwei Lichtleitungen: Die kurze „Spot“-Leitung läuft nachweislich mit 12 V DC und passt zu J5. Bei der langen Beleuchtung ist offen, ob ein Trafo/Treiber in der Leuchte steckt. Davon hängt ab, ob der Lichtausgang J5 (12 V DC, MOSFET) passt. Erste Prüfung spannungsfrei: Widerstand der langen Beleuchtungsleitung messen (wenige Ω = Halogen/12-V-Last direkt; hoher Wert oder offen = Treiber/Trafo in der Leuchte).

## 6. Architektur

```text
230 V AC (L, N, PE)
  │
  ├── Sicherung ── Varistor/X2-Filter
  │       │
  │       ├── zertifiziertes Netzteil 230 V → 12 V DC (isoliert, z. B. Printmodul)
  │       │       ├── 12 V → MOSFET → LED-Beleuchtung
  │       │       └── 12 V → Step-down 3,3 V → ESP32
  │       │                                   ├── Service-Taster, Status-LED, ext. Antenne, BLE
  │       │                                   ├── Temperatursensor (optional)
  │       │                                   ├── WLAN → Home Assistant (ESPHome-API)
  │       │                                   └── Steuersignale ──┐
  │       │                                                       │ galvanische Trennung
  │       │                                                       │ (Relaisspule / Optotriac)
  │       └── Motor-Leistungsteil (Variante A oder B) ◄───────────┘
  │                   └── GUTMANN-Motor + 6,5-µF-Betriebskondensator
  └── PE → Gehäuse, Motor
```

Alles sitzt auf der Trägerplatte im Aufnahmeraum der alten Steuerung (Abschnitt 5a).

**Eine Platine mit zwei getrennten Zonen** (Netzzone und Kleinspannungszone), Details in Abschnitt 6b.

## 6b. Steuerplatine: Layout-Konzept

Bestückungsskizze im Maßstab 1 : 1: [`hardware/platine-layout-konzept.svg`](../hardware/platine-layout-konzept.svg). Konzept für Variante A (Relais + Kondensatoren) und LED-Licht 12 V, **kein freigegebenes Layout**.

### Grundaufbau

- **Format:** 160 × 100 mm (Europakarte), passt in gängige Normgehäuse. Vier Befestigungslöcher M3.
- **Netzzone links, Kleinspannung rechts.** Dazwischen eine Isolationsbarriere mit Frässchlitz. Nur zwei Bauteilarten überbrücken die Barriere, beide mit eigener verstärkter Isolation: das **Netzteilmodul PS1** und die **Relais K1–K4** (Kontakte links, Spule rechts).
- **ESP32 gesteckt** auf Buchsenleisten: tauschbar, und das Board mit Antennenbuchse (DevKitC-32U) kann am Platinenrand die externe Antenne aufnehmen.

### Absicherung

| Stufe | Bauteil | Zweck |
|---|---|---|
| Hausinstallation | Leitungsschutzschalter des Küchenstromkreises (vorhanden, z. B. B16) | Schutz der Zuleitung |
| Platine gesamt | **F1** Feinsicherung 5 × 20 mm, träge, Richtwert **T 2,5 A** (Motor 1,15 A + Anlaufstrom + Netzteil) | Kurzschluss auf der Platine/im Motor |
| Netzteilzweig | **F2** Feinsicherung, Richtwert **T 1 A** | Netzteilfehler, ohne dass der Motorzweig betroffen ist |
| Überspannung | **RV1** Varistor 275 V AC (z. B. S14K275) **hinter** F1 | Netzspitzen; fällt der Varistor aus, löst F1 aus |
| Funkentstörung | **CX** X2-Kondensator 100 nF hinter F1 | EMV |
| Schaltkontakte (optional) | RC-Snubber über dem Motorausgang (100 nF X2 + 100 Ω) | Weniger Kontaktabbrand und Störungen beim Abschalten |

Sicherungswerte sind Richtwerte und werden von der Elektrofachkraft festgelegt. Sicherungshalter mit Berührungsschutzkappe verwenden.

### Netzzone (230 V)

| Ref | Bauteil | Hinweis |
|---|---|---|
| J1 | Netzanschluss L, N | Schraubklemme Rastermaß 7,5 mm, 300 V (Footprint MetzConnect RT137, 2-polig) |
| F1, F2 | Sicherungshalter 5 × 20 mm, Schurter OGN (0031.8201), Raster 22,5 mm, mit Abdeckhaube | siehe Absicherung |
| RV1, CX | Varistor, X2-Kondensator | direkt hinter F1 |
| K1–K4 | Printrelais 12-V-Spule, 10 A / 250 V AC, verstärkte Isolation Spule–Kontakt (z. B. Finder 40.31) | Kontaktseite zur Netzzone |
| J4 | Anschluss für CM1–CM3 (je 2 Pole), 6-polig, Raster 7,5 mm | Becherkondensatoren neben der Platine auf der Trägerplatte, so lassen sich Werte im Versuch tauschen |
| R-Entl. | je Kondensator 2 × 470 kΩ in Reihe (0207, 0,6 W) | entlädt CM1–CM3 nach dem Abschalten |
| J3 | Motorausgang M-L, M-N | Schraubklemme 7,5 mm (wie J1) |

**PE** wird nicht über die Platine geführt, sondern mit einer Verbindungsklemme (z. B. Wago 221) im Aufnahmeraum: Zuleitung, Motor, Haubengehäuse.

**Leiterbahnen Netz:** mindestens 2,5 mm breit (bei 35 µm Kupfer reichlich für 2–3 A), Abstand L–N mindestens 3 mm, keine Vias im Lastpfad nötig.

### Kleinspannungszone (SELV)

| Ref | Bauteil | Hinweis |
|---|---|---|
| PS1 | AC/DC-Modul 12 V, 20 W (z. B. Mean Well IRM-20-12) | versorgt Relais, LED-Licht und über U2 den ESP32 |
| U2 | Schaltregler 12 V → 5 V (z. B. Recom R-78E5.0-0.5) | 5 V an den ESP32-DevKit |
| U1 | ULN2003A | treibt die 12-V-Relaisspulen, Freilaufdioden integriert |
| Q1 | Logic-Level-MOSFET (z. B. AO3400 oder IRLZ44N), 100 Ω Gate, 10 kΩ Pull-down | PWM für LED-Licht |
| J5 | Lichtausgang +12 V / LED− | zweiadrige Leitung zu den G4-LEDs |
| J6 | Sensoranschluss DS18B20 (Reichelt DS 18B20) | Temperatur im Aufnahmeraum, Warnung ab 60 °C in Home Assistant (Firmware ergänzt 23.11.2026) |
| ESP32 | DevKitC-32U auf Buchsenleisten (J7, J8) | IO16–19 → U1 (K1–K4), IO25 → Q1 (Licht-PWM), IO4 → 1-Wire |

Leistungsbudget PS1: Relais (nur eins gleichzeitig an, ca. 0,4 W) + ESP32 (ca. 1 W) + LED-Licht. Bei mehr als ca. 15 W Licht ein stärkeres Netzteil wählen.

### Layoutregeln

- **Kriechstrecke Netz ↔ Kleinspannung ≥ 8 mm**, Frässchlitz 2 mm unter den Relais zwischen Spulen- und Kontaktpins, wo das Footprint es zulässt. Küche gilt als verschmutzte Umgebung, deshalb mehr als die oft genannten 6 mm.
- Netzzone ohne Kupferflächen in Richtung Barriere; keine Leiterbahn kreuzt die Barriere außer über PS1 und die Relais.
- In KiCad zwei Netzklassen anlegen („Netz": Abstand 3 mm, Breite 2,5 mm; „SELV": Standard) und eine Sperrfläche (Rule Area) über der Barriere ohne Kupfer.
- Lastpfad: K1-Ausgang → M-L direkt; K2/K3/K4-Ausgang → CM1a/CM2a/CM3a → Kondensator → CM1b/CM2b/CM3b → M-L → J3.
- Bestückungsdruck: Warnsymbol und „230 V" auf der Netzzone, Sicherungswerte neben die Halter.
- Platine im geschlossenen, nur mit Werkzeug zu öffnenden Aufnahmeraum; Netzzone zusätzlich abdecken, wenn der Raum im Betrieb geöffnet wird.

### KiCad-Projekt

Ordner `hardware/kicad/` (KiCad 10):

| Datei | Inhalt |
|---|---|
| `generate_schematic.py` | Python-Skript, das den Schaltplan erzeugt. **Änderungen am Schaltplan hier machen** und neu erzeugen: `python3 generate_schematic.py` |
| `dunstabzug-steuerplatine/dunstabzug-steuerplatine.kicad_pro` | Projekt, in KiCad öffnen |
| `…/dunstabzug-steuerplatine.kicad_sch` | Schaltplan (A3, Netzzone und Kleinspannung als getrennte Rahmen) |
| `…/dunstabzug-steuerplatine.pdf` / `.svg` | Schaltplan zum Ansehen |
| `…/stueckliste.csv` | Stückliste mit Footprints |
| `…/erc.rpt` | Ergebnis der elektrischen Regelprüfung (Stand 21.11.2026: 0 Fehler, 0 Warnungen) |

**Aufbau des Schaltplans:** Verbindungen laufen über **Netz-Labels**: Gleicher Name = verbunden (z. B. `L_F` = Phase hinter F1, `M_L` = geschaltete Motorphase, `CM1_A` = Relais K2 zu Kondensator CM1). Unbenutzte Pins tragen ein No-Connect-Kreuz. Jedes Bauteil hat einen Footprint, die Platine kann also direkt aus dem Schaltplan entstehen.

**Prüfen und exportieren** (Terminal):

```bash
cd hardware/kicad/dunstabzug-steuerplatine
/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli sch erc dunstabzug-steuerplatine.kicad_sch
```

### Platine (PCB)

Erzeugt und verlegt per Skript (Pipeline aus `hardware/kicad/`, überschreibt die `.kicad_pcb`):

```bash
KP=/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3
$KP generate_pcb.py                 # Bauteile platzieren, Netze, Regeln, Umriss
python3 route_pcb.py                # Leiterbahnen verlegen (eigener A*-Router, braucht numpy)
$KP generate_pcb.py --apply-routes  # Bahnen, Vias und GND-Fläche eintragen
```

- `generate_pcb.py`: Platzierung (Tabelle `PLACEMENT`), Netzklassen, `.kicad_dru`, schreibt `routing_pads.json`
- `route_pcb.py`: Raster 0,5 mm, 2 Lagen, berücksichtigt die Abstände je Netzklasse, Rand- und Lochabstände sowie die Sperrfläche; schreibt `routing_result.json`. Freerouting scheidet aus, weil Java fehlt.

Stand 22.11.2026:

- Umriss 160 × 100 mm, vier M3-Löcher in den Ecken, **Frässchlitz 2 × 64 mm** bei x = 100 mm unter den Relais (zwischen Spulen- und Kontaktpins)
- Alle 36 Bauteile nach dem Layout-Konzept platziert, Netze aus dem Schaltplan zugeordnet
- **Netzklassen** (in `.kicad_pro`): `Netz` (230-V-Netze, Abstand **3 mm**, Bahn 2,5 mm), `SELV` (Kleinspannung, Bahn 0,4 mm, Versorgung 0,8 mm)
- **Eigene Regeln** (`.kicad_dru`): Netz ↔ SELV mindestens **8 mm Luft- und Kriechstrecke**, Netz ↔ Netz mindestens **3 mm Kriechstrecke**, Netzbahnen mindestens 2 mm breit, Netzkupfer 2 mm vom Rand und 3,5 mm von den Befestigungslöchern
- **Sperrfläche** „Isolationsbarriere" (x 95–105 mm): keine Leiterbahnen, Vias oder Kupferflächen
- **Leiterbahnen verlegt:** 261 Segmente, 9 Vias; GND-Fläche auf der Unterseite der SELV-Zone
- Netzklemmen J1, J3, J4 mit **7,5 mm Raster** (bei 5,08 mm blieben zwischen den Pads nur 2,5 mm). Entladewiderstände R1–R6 als drei Reihen mitten in der Netzzone, nicht mehr direkt an J4
- Bestückungsdruck: „! 230 V AC !", Sicherungswerte, Klemmenbelegung
- **DRC:** 0 offene Verbindungen, keine Abstands- oder Regelverstöße. Übrig sind 8 Hinweise, dass der Relais-Bestückungsdruck über den Schlitz läuft (unkritisch, wird beim Fertigen abgeschnitten)
- Ansichten: `platine-kupfer.png` (Kupfer oben rot, unten blau), `platine-3d-oben.png`, `platine-3d-schraeg.png`, `platine-3d-klemmenseite.png`
- 3D-Modelle der Netz-Schraubklemmen J1/J3/J4 (7,5 mm): KiCad liefert keine mit, daher Platzhalter aus `make_3d_terminals.py` (`hardware/kicad/3d/*.wrl`), von `generate_pcb.py` automatisch zugeordnet. Nur für die 3D-Ansicht, Gerber unverändert

**Fertigungsdaten** (22.11.2026) in `hardware/gerber/`, gepackt als `hardware/dunstabzug-steuerplatine-gerber.zip` (12 Dateien, ohne Bohrpläne):

- Gerber: Kupfer, Lötstopp, Paste, Bestückungsdruck je oben/unten, `Edge_Cuts` (Umriss + Schlitz)
- Bohrungen Excellon, getrennt: `PTH.drl` (139 Löcher, 0,4–1,5 mm) und `NPTH.drl` (4 × 3,2 mm Befestigung, 2 × 2,7 mm Haltezapfen der Sicherungshalter)
- Bestellangaben: 2 Lagen, 1,6 mm FR-4, **Kupfer 35 µm (1 oz)**, Fräskontur inklusive Innenschlitz (beim Hersteller „Slot/Cutout“ prüfen)

```bash
cd hardware/kicad/dunstabzug-steuerplatine
kicad-cli pcb export gerbers --layers F.Cu,B.Cu,F.Paste,B.Paste,F.Silkscreen,B.Silkscreen,F.Mask,B.Mask,Edge.Cuts --subtract-soldermask --no-protel-ext -o ../../gerber/ dunstabzug-steuerplatine.kicad_pcb
kicad-cli pcb export drill --format excellon --excellon-separate-th --generate-map --map-format gerberx2 -o ../../gerber/ dunstabzug-steuerplatine.kicad_pcb
```

**Noch offen:** Layout im PCB-Editor durchsehen, Netzseite durch die Elektrofachkraft prüfen lassen, ZIP im Gerber-Viewer des Herstellers kontrollieren, erst dann bestellen. DevKitC-Reihenabstand (25,4 mm) am echten Board nachmessen.

Die Architektur ist ein Konzept, **kein freigegebener 230-V-Verdrahtungsplan**.

## 7. Firmware (ESPHome)

### Anforderungen

- Sicherer Startzustand: Lüfter und Licht aus (`restore_mode: ALWAYS_OFF`)
- Bedienung per BLE-Taster funktioniert ohne WLAN und ohne Home Assistant
- **Kein Neustart bei fehlendem WLAN/HA:** `reboot_timeout: 0s` bei `wifi` und `api` setzen (Standard ist ein Reboot nach 15 min ohne Verbindung)
- Relaisverriegelung bzw. Triac-Mindestwert in der Firmware
- Watchdog ist in ESPHome eingebaut
- OTA-Updates
- Optional: Nachlauf (z. B. 10 min Stufe 1, dann aus), Filterstunden-Zähler, Übertemperatur-Abschaltung

### Stufen und Prozentwerte

| Modus | UI-Wert |
|---|---:|
| Aus | 0 % |
| Stufe 1 | 25 % |
| Stufe 2 | 50 % |
| Stufe 3 | 75 % |
| Boost | 100 % |

Die Prozentwerte sind **UI-Sollwerte**, keine gemessenen Drehzahlen. Bei Variante A rastet ein späterer Slider auf die nächste Stufe ein; bei Variante B werden sie über die gemessene Kennlinie auf Ansteuerwerte abgebildet.

### Skizze (ungetestet, nur zur Orientierung)

```yaml
esphome:
  name: dunstabzug

esp32:
  board: esp32dev

wifi:
  ssid: !secret wifi_ssid
  password: !secret wifi_password
  reboot_timeout: 0s

api:
  reboot_timeout: 0s

ota:
  - platform: esphome

fan:
  - platform: template        # Variante A: Relaisstufen
    name: "Lüfter"
    speed_count: 4            # 3 Stufen + Boost
    restore_mode: ALWAYS_OFF
    # on_speed_set / on_turn_off: Relais verriegelt umschalten

light:
  - platform: monochromatic   # LED 12 V über MOSFET
    name: "Licht"
    output: led_pwm
    restore_mode: ALWAYS_OFF
```

## 8. KiCad und Git

KiCad ist installiert (kostenlos, Open Source). Ablauf: Projekt anlegen → Schaltplan → Bauteilauswahl → ERC → PCB-Layout → DRC → Fertigungsdaten. Logik- und Leistungsplatine als getrennte KiCad-Projekte.

Repository-Struktur:

```text
smart-range-hood-esp32/
├── README.md
├── .gitignore              # secrets.yaml, .esphome/, KiCad-Backups
├── esphome/
│   ├── dunstabzug.yaml
│   └── packages/           # Variante A/B getrennt
├── hardware/
│   ├── logic-board/        # KiCad, Kleinspannung
│   ├── power-board/        # KiCad, 230 V
│   ├── gerber/
│   └── bom/
└── docs/
    ├── motor.md
    ├── regelverfahren-tests.md
    ├── lighting.md
    ├── architecture.md
    ├── safety.md
    └── commissioning.md
```

**Zugangsdaten:** `secrets.yaml` (WLAN-Passwort, API-Schlüssel) gehört weder ins Repo noch in den Nextcloud-Ordner. Am einfachsten über das ESPHome-Add-on in Home Assistant kompilieren, dort liegen die Secrets.

## 9. Sicherheit

Die Haube enthält **230 V AC** und einen **260-W-Induktionsmotor**. Maßgebliche Norm für Dunstabzugshauben: **EN 60335-1 und EN 60335-2-31**.

- Netzspannungsteil nicht auf Lochraster; Lochraster allenfalls für die isolierte Kleinspannungs-Logik
- Schutzleiter an Gehäuse und Motor
- Absicherung (Feinsicherung auf der Leistungsplatine), Varistor, X2-Filter
- **Kriech- und Luftstrecken** zwischen 230 V und Kleinspannung: verstärkte Isolierung, Richtwert mindestens 6 mm, in fettiger Küchenumgebung eher mehr; ggf. Schlitz in der Platine. Verbindlich ist die Norm.
- Berührungsschutz, Zugentlastung, Schutz gegen Fett und Feuchte: geschlossener Aufnahmeraum aus Metall am PE (Abschnitt 5a), ggf. Schutzlack
- Leitungen im Aufnahmeraum geschützt verlegen, nicht scheuernd an Blechkanten, nicht am heißen Abluftkanal
- Thermische Auslegung (Triac-Kühlkörper, Kondensatoren für 85 °C+)
- Entladewiderstände an allen Kondensatoren im Netzteil
- Auslegung, Aufbau und Prüfung (Isolationsmessung, Schutzleiterprüfung) der Netzspannungsbaugruppe **durch eine Elektrofachkraft**

**Wer prüft:** Eine Elektrofachkraft für festgelegte Tätigkeiten prüft Layout und Aufbau. Ein Elektriker macht den Gegencheck und die Prüfung nach DIN VDE 0701-0702 vor der Inbetriebnahme. Der Selbstbau einer 230-V-Baugruppe geht über typische festgelegte Tätigkeiten hinaus, deshalb ist der Gegencheck durch den Elektriker fest eingeplant.

### Kaminofen und Abluftbetrieb (Stand 23.11.2026)

Im Haus steht ein Kaminofen mit Außenluftzufuhr. Die Haube arbeitet im Abluftbetrieb und erzeugt Unterdruck im Raum.

- **Regel (Feuerungsverordnung § 4 Abs. 2, je Bundesland leicht unterschiedlich):** Raumluftabhängige Feuerstätten dürfen durch Dunstabzugshauben nicht beeinträchtigt werden. Zulässig ist der gemeinsame Betrieb nur, wenn z. B. eine Sicherheitseinrichtung den gleichzeitigen Betrieb verhindert, die Abgasführung überwacht wird oder anlagentechnisch kein gefährlicher Unterdruck entstehen kann. Als Richtwert gelten max. 4 Pa Unterdruck, bei zugelassenen raumluftunabhängigen Öfen bis 8 Pa.
- **Außenluftanschluss ≠ raumluftunabhängig:** Ein Ofen gilt nur als raumluftunabhängig, wenn er dafür geprüft und zugelassen ist (DIBt-Zulassung, Dichtheitsprüfung). Ein Ofen mit Verbrennungsluftstutzen ohne diese Zulassung zählt rechtlich als raumluftabhängig.
- **Ofen laut Ofenpass:** LEDA VIDA 55 F (Kamineinsatz, EN 13229, 9 kW, selbstschließende Tür, für Mehrfachbelegung geeignet). Auf dem Typenschild steht **keine** Angabe „raumluftunabhängig“ und keine DIBt-Zulassung → vorerst als **raumluftabhängig** behandeln.
- **Passende Sicherheitseinrichtung:** LEDA bietet selbst den Unterdruckwächter **LUC2** an (DIBt-Zulassung Z-85.1-16). Er misst den Unterdruck und schaltet die Haube ab. Alternative: Fensterkontaktschalter mit Zulassung. Beides sitzt in der Zuleitung vor der Steuerplatine.
- **Zu klären:** Typenschild/Zulassung des Ofens und Feuerstättenbescheid prüfen bzw. den Bezirksschornsteinfeger fragen, ob und mit welcher Auflage (Fensterkontaktschalter, Unterdruckwächter) die Abluft-Haube abgenommen wurde.
- **Folge für die Steuerung:** Eine ESP-Logik ist **keine** zugelassene Sicherheitseinrichtung. Falls eine Sicherung nötig ist oder schon existiert (z. B. Fensterkontaktschalter), bleibt sie als zugelassenes Gerät in der Netzzuleitung **vor** der Steuerplatine. Zusätzlich darf die Firmware informieren, z. B. eine Warnung, wenn Ofen und Haube gleichzeitig laufen.

### Prüfliste Netzseite (Stand 22.11.2026)

Normwerte aus EN 60335-1 bzw. IEC 60664-1 sind aus dem Gedächtnis eingetragen und **in der Norm nachzuschlagen**. Annahme: Verschmutzungsgrad 2 (geschlossener Metall-Aufnahmeraum im Haubenkörper; Fettnebel nicht ganz auszuschließen, deshalb 8 mm statt 6 mm Kriechstrecke), Überspannungskategorie II, Isolierstoffgruppe IIIa (FR-4).

**A. Isolation Netz ↔ Kleinspannung (verstärkt)**

| Punkt | Soll (prüfen) | Ist auf der Platine |
|---|---|---|
| Luftstrecke verstärkt, 230 V | ca. 3 mm | ≥ 8 mm (DRC-Regel) |
| Kriechstrecke verstärkt, 230 V, VG 2 | ca. 5 mm | ≥ 8 mm, zusätzlich Schlitz 2 × 64 mm |
| Relais K1–K4 Spule ↔ Kontakt | verstärkt, 6 kV Stoß | Datenblatt Finder 40.31 prüfen |
| Netzteil PS1 Eingang ↔ Ausgang | verstärkt, Schutzklasse II | IRM-20-12: 3 kV AC, Datenblatt prüfen |
| Kupfer Netz ↔ Befestigungsloch | Schraube ggf. am Metallgehäuse (PE) | ≥ 3,5 mm |

**B. Abstände innerhalb der Netzseite (Funktionsisolierung)**

Erste Fassung (22.11.2026, Regel 2 mm): L–N mindestens 2,45 mm, über CM3 nur 2,0 mm. Das widersprach der eigenen Vorgabe „L–N mindestens 3 mm“ (Abschnitt 6b).

**Umgesetzt (22.11.2026):** Netz ↔ Netz jetzt **3 mm Luft- und Kriechstrecke** als DRC-Regel, Platine neu verlegt, DRC ohne Verstöße. Dafür Netzklemmen auf 7,5 mm Raster umgestellt und R1–R6 versetzt.

- Soll für Funktionsisolierung bei 250 V, VG 2, gedruckte Schaltung: je nach Norm ca. 1,25 mm (IEC 60664-1, Leiterplatte) bis 2,5 mm (EN 60335-1). 3 mm liegt über beiden. Normwert trotzdem nachschlagen
- Selbst prüfen: Abstände innerhalb der Bauteile (Relais-Kontakte, Sicherungshalter) laut Datenblatt, die prüft die DRC nicht gegen 3 mm

**C. Absicherung und Strombelastbarkeit**

- Motor 260 W → ca. 1,13 A; Netzteil 20 W → ca. 0,15 A (Einschaltstrom IRM-20-12 laut Datenblatt prüfen)
- F1 T2,5A: Faktor ca. 2 über Nennstrom, träge für Motoranlauf. Passt der Wert zur Leitung und zum Vorschalt-LS?
- F2 T1A vor PS1
- Netzbahnen 2,5 mm bei 35 µm: ca. 5–6 A bei 10 K Erwärmung → reichlich
- Relais 10 A / 250 V AC, Spitzenstrom laut Datenblatt (ca. 20 A)
- Klemmen J1/J3/J4: 7,5 mm Raster, 300 V; Klemmbereich laut Datenblatt (typisch bis 2,5 mm²)
- Leitungsquerschnitte (Strom ist klein, Querschnitt folgt aus mechanischer Festigkeit und Vorsicherung):

| Leitung | Strom | Vorschlag | Bemerkung |
|---|---|---|---|
| Zuleitung Haube → J1 | ca. 1,3 A | wie vorhanden, meist 1,5 mm² | Querschnitt passend zum LS (B16 → 1,5 mm²) |
| J3 → Motor | ca. 1,13 A | 0,75–1,0 mm² H05V-K bzw. H05VV-F | wie die originale Motorleitung |
| J4 → CM1–CM3 | < 1 A | 0,75 mm² H05V-K | kurz, auf der Trägerplatte |
| J5 → LED 12 V | < 2 A | 0,75 mm² | SELV, getrennt von 230 V verlegen |

  Hinter F1 (T2,5A) ist jede Leitung ab 0,75 mm² sicher geschützt. Die Zuleitung **vor** F1 hängt am LS des Küchenstromkreises und braucht dessen Querschnitt. Feindrähtige Leiter mit Aderendhülsen

**D. Kondensatoren CM1–CM3 und Entladung**

- Bauart MKP, Nennspannung ≥ 450 V AC, für Motorbetrieb (Klasse S2/S3 nach EN 60252-1 o. ä.)
- Entladewiderstand 2 × 470 kΩ = 940 kΩ. Bei 8 µF: τ = 7,5 s, von 325 V auf 60 V in ca. 13 s, auf 34 V in ca. 17 s
  → Hinweis „Vor dem Öffnen 30 s warten“ an der Abdeckung des Aufnahmeraums, oder kleinere Widerstände (z. B. 2 × 220 kΩ: ca. 6 s auf 60 V, bei 200 V über CM nur ca. 0,05 W je Widerstand)
- Spannung über CM im Betrieb messen (Abschnitt 3); zwei Widerstände in Reihe teilen sie sich. 0207-Widerstand mit ≥ 250 V Grenzspannung reicht dann sicher
- Umschalten mit geladenem CM: Spannung über dem schließenden Kontakt bis ca. 650 V Spitze, Strom nur durch die Motorwicklung begrenzt (ca. 42 Ω Gleichstromwiderstand → bis ca. 15 A Spitze). Unter dem Spitzenstrom des Relais, aber im Versuch beobachten (Kontaktabbrand)

**E. Fehlerfälle**

| Fehler | Folge | Bewertung |
|---|---|---|
| K1 und K2–K4 gleichzeitig zu (Kontakt verschweißt) | CM liegt beidseitig an L, Motor läuft auf Vollgas | ungefährlich |
| Relais verschweißt | Motor lässt sich per ESP nicht abschalten | Abschalten über LS oder vorgelagerten Schalter, ungefährlich |
| CM kurzgeschlossen | Motor läuft auf Vollgas | ungefährlich |
| Motor blockiert | Strom steigt, Thermoschutz im Motor? | **offene Frage 10** |
| Varistor verschleißt / Kurzschluss | F1 löst aus | ok, Varistor hinter F1 |
| ESP32 hängt oder startet neu | Relais fallen ab (`ALWAYS_OFF`) | ok |

**F. Schutzleiter und Gehäuse**

- PE von der Zuleitung zu Haubengehäuse, Motor über Verbindungsklemme, nicht über die Platine
- Antennenkabel (Kleinspannung) mit Abstand zu Netzleitungen aus dem Aufnahmeraum führen
- Zugentlastung für alle 230-V-Leitungen auf der Trägerplatte (Kabelbinder)

**G. Messungen nach dem Aufbau**

1. Sichtprüfung: Lötstellen Netzseite, keine Lotbrücken, Schlitz frei, Abdeckung Netzzone
2. Isolationswiderstand L+N (gebrückt) gegen Kleinspannung (GND) mit 500 V DC: Soll ≥ 7 MΩ für verstärkt (Norm prüfen). Varistor und X2 liegen zwischen L und N, stören also nicht
3. Isolationswiderstand L+N gegen PE
4. Schutzleiterwiderstand Gehäuse ↔ PE der Zuleitung
5. Erst Kleinspannung allein (12 V aus Labornetzteil): Relais klicken, ESP läuft
6. Dann 230 V über Trenntrafo oder FI-geschützt, mit Glühlampe als Last statt Motor
7. Motor anschließen, Spannung am Motor je Stufe messen (Abschnitt 3), Temperatur von CM und Relais nach 30 min
8. Abschluss: Prüfung nach DIN VDE 0701-0702 durch den Elektriker, Protokoll ablegen

## 10. Offene Fragen

- [ ] Funktionierende Motorverdrahtung (L/N/Kondensator, Drehrichtung) mit Foto dokumentieren
- [x] Thermoschutz im Motor vorhanden? Ja, Thermowächter TW in Blau (Typenschild)
- [x] Licht: Spots G4 12 V (Halogen) funktionieren, werden auf LED-G4 umgestellt; Milchglas-Beleuchtung entfällt (22.11.2026)
- [ ] Anzahl der Spots zählen (Menge LED-G4, Budget PS1)
- [ ] Display-Fenster ausmessen und Blende planen
- [ ] Platz im Kamin messen (Breite/Tiefe/Höhe neben dem Abluftkanal), Befestigungsmöglichkeit, lässt sich das untere Kaminteil verschieben?
- [x] Netzanschluss liegt im Aufnahmeraum (Abschnitt 5a)
- [ ] WLAN-Empfangstest mit Dev-Board im geschlossenen Aufnahmeraum
- [x] Kabelweg: Netz, Motor und Licht liegen bereits im Aufnahmeraum (Abschnitt 5a)
- [ ] Leitungen im Anschlussraum durchmessen (Abschnitt 5a, Tabelle „Vorhandene Leitungen“)
- [x] Spot-Leitung: 12 V DC, getestet (23.11.2026)
- [ ] Lange Beleuchtungsleitung: AC oder DC, Trafo/Treiber in der Leuchte? (zuletzt klären)
- [ ] Kaminofen: raumluftunabhängig zugelassen (DIBt)? Auflage für die Abluft-Haube beim Bezirksschornsteinfeger klären

## 11. Aufgabenliste

- [x] Motortypenschild und Daten dokumentiert
- [x] Wicklungswiderstände erfasst und ausgewertet (2 Wicklungen, Blau gemeinsam)
- [x] Motor erfolgreich betrieben
- [x] Bauraum 140 × 180 mm erfasst
- [x] KiCad heruntergeladen
- [x] Firmware-Plattform festgelegt: ESPHome
- [x] Einbauort festgelegt: Aufnahmeraum der alten Steuerung, Trägerplatte, kein eigenes Gehäuse (23.11.2026)
- [x] Bauform dokumentiert (Inselhaube, Foto)
- [x] Bedienkonzept: smart über HA, Original-Display entfällt
- [x] Bedienung ohne WLAN: BLE-Funktaster
- [x] ESPHome-Testkonfiguration BLE-Taster erstellt (`esphome/dunstabzug-ble-test.yaml`)
- [ ] BLE-Taster beschaffen, Testkonfiguration auf Dev-Board flashen (Ereignisse, Reichweite von der Front in den Edelstahlkamin)
- [ ] Offene Fragen aus Abschnitt 10 klären
- [x] ESPHome-Testkonfiguration Motor Variante A erstellt (`esphome/dunstabzug-motor-test.yaml`)
- [ ] Motor Schritt 1: K1 ersetzt den Schalter (Fachkraft), ESP32 flashen, an/aus über HA testen
- [ ] Motor Schritt 2: CM1–CM3 + K2–K4, Messungen nach Testplan inkl. Motorspannung
- [ ] Variante B als Vergleich (optional, falls Stufen mit A nicht zufriedenstellen)
- [ ] Regelverfahren festlegen
- [ ] Bedienkonzept und ESP32-Variante festlegen
- [x] Layout-Konzept Steuerplatine inkl. Absicherung (`hardware/platine-layout-konzept.svg`, Abschnitt 6b)
- [ ] Konzept mit Elektrofachkraft durchsprechen (Sicherungswerte, Abstände, Bauteile)
- [x] KiCad: Schaltplan der Steuerplatine (erzeugt per Skript, ERC ohne Fehler)
- [x] KiCad: Platine angelegt, Bauteile platziert, Netzklassen und 8-mm-Regel Netz/SELV (DRC ohne Regelverstoß)
- [x] KiCad: Leiterbahnen verlegen, GND-Fläche (per Skript, 22.11.2026)
- [x] KiCad: Gerber- und Bohrdaten exportieren (22.11.2026)
- [x] Netzabstand auf 3 mm erhöht, Klemmen 7,5 mm, neu verlegt, Gerber neu (22.11.2026)
- [x] Einkaufsliste Reichelt: [`hardware/einkaufsliste-reichelt.md`](../hardware/einkaufsliste-reichelt.md); Sicherungshalter dafür auf Schurter OGN umgestellt (22.11.2026)
- [x] ESP32-DevKitC-32U (2 Stück mit Antenne) bestellt
- [ ] **Vor der Bestellung besprechen:** Q1 (AO3400A, SOT-23) ist das einzige SMD-Teil. Entweder selbst löten (Lötkolben mit feiner Spitze oder Heißluft, Flussmittel) oder Teilbestückung beim Hersteller (JLCPCB, LCSC C20917; dafür BOM + Bestückungsdatei erzeugen)
- [ ] Platine bestellen (nach Prüfung durch die EFKffT und Gegencheck durch den Elektriker)
- [ ] DevKitC-Reihenabstand am echten Board nachmessen
- [ ] ESPHome-Konfiguration mit Zustandslogik, auf Dev-Board ohne Netzspannung testen
- [ ] Leistungsplatine fachgerecht entwickeln und prüfen lassen
- [ ] Home-Assistant-Integration
- [ ] Inbetriebnahme und Kalibrierung dokumentieren

## 12. Nächste Schritte

1. **Dokumentieren:** Motorverdrahtung, Lampe, Platz in der Kaminverkleidung (Abschnitt 10). Kostet wenig und blockiert alles andere.
2. **Firmware ohne Netzspannung starten:** ESP32-Dev-Board, ESPHome-Grundkonfiguration, Relais/LEDs als Platzhalter, HA-Dashboard und ggf. BLE-Taster ausprobieren. Dabei gleich den WLAN-Empfang an der Einbaustelle in der Verkleidung testen. Ungefährlich und unabhängig vom Regelverfahren.
3. **Parallel:** Testaufbau für Variante A und B mit Fachkraft planen.
4. **Danach:** KiCad-Logikplatine, wenn ESP32-Variante und Bedienung feststehen.

---

**Projektprinzip:** Bestehende hochwertige Mechanik erhalten, fehlende Elektronik sicher und nachvollziehbar ersetzen und die Entwicklung auf GitHub dokumentieren.
