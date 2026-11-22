#!/usr/bin/env python3
"""
Erzeugt den KiCad-Schaltplan der Dunstabzug-Steuerplatine.

Idee: Jedes Bauteil wird platziert, an jeden benutzten Pin kommt ein kurzes
Drahtstück mit einem Netz-Label. Gleiche Label-Namen = elektrisch verbunden.
Unbenutzte Pins bekommen ein "No-Connect"-Kreuz. So bleibt der Plan lesbar
und das Skript braucht keine Leitungsführung.

Aufruf:   python3 generate_schematic.py
Ergebnis: dunstabzug-steuerplatine/dunstabzug-steuerplatine.kicad_sch (+ .kicad_pro)

Die Bauteilsymbole werden aus der installierten KiCad-Bibliothek gelesen und
in den Schaltplan eingebettet (so wie KiCad es selbst macht).
"""

import copy
import json
import math
import re
import sys
import uuid
from pathlib import Path

KICAD_SHARE = Path("/Applications/KiCad/KiCad.app/Contents/SharedSupport")
SYM_DIR = KICAD_SHARE / "symbols"
FP_DIR = KICAD_SHARE / "footprints"

PROJECT = "dunstabzug-steuerplatine"
OUT_DIR = Path(__file__).resolve().parent / PROJECT
NS = uuid.UUID("6f1b3d6e-0d0a-4c1e-9a55-2b7d2a1c0f11")  # fester Namensraum -> stabile UUIDs


def uid(*key):
    return str(uuid.uuid5(NS, "/".join(str(k) for k in key)))


ROOT_UUID = uid("root")

# ---------------------------------------------------------------------------
# Minimaler S-Expression-Parser / -Writer (KiCad-Dateiformat)
# ---------------------------------------------------------------------------


class Sym(str):
    """Unquotiertes Atom (Schlüsselwort/Zahl)."""


def tokenize(text):
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if c in " \t\r\n":
            i += 1
        elif c in "()":
            yield c
            i += 1
        elif c == '"':
            j, buf = i + 1, []
            while text[j] != '"':
                if text[j] == "\\":
                    buf.append(text[j:j + 2])
                    j += 2
                else:
                    buf.append(text[j])
                    j += 1
            yield ("str", "".join(buf))
            i = j + 1
        else:
            j = i
            while j < n and text[j] not in ' \t\r\n()"':
                j += 1
            yield Sym(text[i:j])
            i = j


def parse(text):
    stack = [[]]
    for tok in tokenize(text):
        if tok == "(":
            stack.append([])
        elif tok == ")":
            done = stack.pop()
            stack[-1].append(done)
        elif isinstance(tok, tuple):
            stack[-1].append(tok[1])  # str = gequoteter String
        else:
            stack[-1].append(tok)
    return stack[0]


def fmt_atom(a):
    if isinstance(a, Sym):
        return str(a)
    if isinstance(a, (int, float)):
        return fmt_num(a)
    return '"' + a.replace('"', '\\"') + '"'


def fmt_num(v):
    v = round(float(v), 4)
    s = ("%.4f" % v).rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def dump(node, indent=0):
    if not isinstance(node, list):
        return fmt_atom(node)
    tab = "\t" * indent
    if all(not isinstance(x, list) for x in node):
        return "(" + " ".join(fmt_atom(x) for x in node) + ")"
    head = [fmt_atom(x) for x in node if not isinstance(x, list)]
    out = "(" + " ".join(head)
    for x in node:
        if isinstance(x, list):
            out += "\n" + tab + "\t" + dump(x, indent + 1)
    return out + "\n" + tab + ")"


def S(*items):
    """Hilfsfunktion: Liste mit erstem Element als Schlüsselwort."""
    return [Sym(items[0]), *items[1:]]


def find(node, key):
    return [x for x in node if isinstance(x, list) and x and x[0] == key]


# ---------------------------------------------------------------------------
# Symbolbibliothek
# ---------------------------------------------------------------------------

_lib_cache = {}


def lib_symbols_of(lib):
    if lib not in _lib_cache:
        tree = parse((SYM_DIR / f"{lib}.kicad_sym").read_text())[0]
        _lib_cache[lib] = {x[1]: x for x in find(tree, "symbol")}
    return _lib_cache[lib]


def load_symbol(lib, name):
    """Liefert das Symbol flach (ohne 'extends') und mit Namen 'Lib:Name'."""
    syms = lib_symbols_of(lib)
    if name not in syms:
        sys.exit(f"Symbol {lib}:{name} nicht gefunden")
    sym = copy.deepcopy(syms[name])
    ext = find(sym, "extends")
    if ext:
        parent = load_symbol(lib, ext[0][1])
        parent_name = parent[1].split(":", 1)[1]
        merged = copy.deepcopy(parent)
        child_props = {p[1]: p for p in find(sym, "property")}
        for i, item in enumerate(merged):
            if isinstance(item, list) and item and item[0] == "property" and item[1] in child_props:
                merged[i] = child_props.pop(item[1])
            if isinstance(item, list) and item and item[0] == "symbol":
                item[1] = item[1].replace(parent_name + "_", name + "_", 1)
        for p in child_props.values():
            merged.insert(2, p)
        sym = merged
    sym[1] = f"{lib}:{name}"
    return sym


def symbol_pins(sym):
    """Pins der Einheit 1 bzw. 0: {nummer: (x, y, winkel, typ, name)}."""
    pins = {}
    for unit in find(sym, "symbol"):
        m = re.search(r"_(\d+)_(\d+)$", unit[1])
        if not m or m.group(1) not in ("0", "1") or m.group(2) not in ("0", "1"):
            continue
        for pin in find(unit, "pin"):
            at = find(pin, "at")[0]
            num = find(pin, "number")[0][1]
            pname = find(pin, "name")[0][1]
            pins[num] = (float(at[1]), float(at[2]), int(float(at[3])), str(pin[1]), pname)
    return pins


# ---------------------------------------------------------------------------
# Schaltplan-Aufbau
# ---------------------------------------------------------------------------

STUB = 2.54  # Länge der Drahtstücke an den Pins


class Schematic:
    def __init__(self):
        self.lib = {}          # lib_id -> Symbolbaum
        self.items = []        # Bauteile, Drähte, Labels ...
        self.nets = {}         # Netz -> Liste (Ref, Pin)
        self.missing_fp = []

    def text(self, txt, x, y, size=2.0, bold=True):
        font = S("font", S("size", size, size)) + ([S("bold", Sym("yes"))] if bold else [])
        self.items.append(S("text", txt, S("exclude_from_sim", Sym("no")),
                            S("at", x, y, 0),
                            S("effects", font, S("justify", Sym("left"), Sym("bottom"))),
                            S("uuid", uid("text", txt, x, y))))

    def box(self, x1, y1, x2, y2, color):
        self.items.append(S("rectangle", S("start", x1, y1), S("end", x2, y2),
                            S("stroke", S("width", 0.3), S("type", Sym("dash")),
                              S("color", *color, 1)),
                            S("fill", S("type", Sym("none"))),
                            S("uuid", uid("box", x1, y1, x2, y2))))

    def part(self, lib, name, ref, value, x, y, footprint="", conn=None, note=""):
        """Platziert ein Bauteil. conn = {Pinnummer: Netzname}; fehlende Pins -> No-Connect."""
        conn = conn or {}
        lib_id = f"{lib}:{name}"
        if lib_id not in self.lib:
            self.lib[lib_id] = load_symbol(lib, name)
        sym = self.lib[lib_id]
        pins = symbol_pins(sym)
        for p in conn:
            if p not in pins:
                sys.exit(f"{ref}: Pin {p} gibt es nicht ({sorted(pins)})")

        if footprint:
            fl, fn = footprint.split(":")
            if not (FP_DIR / f"{fl}.pretty" / f"{fn}.kicad_mod").exists():
                self.missing_fp.append(f"{ref}: {footprint}")
        else:
            fp_prop = find(sym, "property")
            footprint = next((p[2] for p in fp_prop if p[1] == "Footprint"), "")

        is_power = bool(find(sym, "power"))
        hide = S("effects", S("font", S("size", 1.27, 1.27)), S("hide", Sym("yes")))
        show = S("effects", S("font", S("size", 1.27, 1.27)), S("justify", Sym("left")))
        # Referenz/Wert platzieren: rechts neben das Bauteil, oder darüber,
        # wenn auf der rechten Seite Pins mit Labels sitzen.
        xs = [p[0] for p in pins.values()] or [0]
        ys = [p[1] for p in pins.values()] or [0]
        right_pins = any(p[2] == 180 for p in pins.values())
        if right_pins:
            top = max(max(ys), 5.08)
            ref_at, val_at = (x - 5.08, y - top - 3.81), (x - 5.08, y - top - 1.27)
        else:
            lx = x + max(max(xs), 0) + 3.81
            ref_at, val_at = (lx, y - 1.27), (lx, y + 1.27)
        datasheet = next((p[2] for p in find(sym, "property") if p[1] == "Datasheet"), "")
        node = S("symbol", S("lib_id", lib_id), S("at", x, y, 0), S("unit", 1),
                 S("exclude_from_sim", Sym("no")), S("in_bom", Sym("no" if is_power else "yes")),
                 S("on_board", Sym("no" if is_power else "yes")), S("dnp", Sym("no")),
                 S("uuid", uid("part", ref)),
                 S("property", "Reference", ref, S("at", *ref_at, 0), hide if is_power else show),
                 S("property", "Value", value, S("at", *val_at, 0), hide if is_power else show),
                 S("property", "Footprint", footprint, S("at", x, y, 0), hide),
                 S("property", "Datasheet", datasheet, S("at", x, y, 0), hide))
        if note:
            node.append(S("property", "Hinweis", note, S("at", x, y, 0), hide))
        for num in pins:
            node.append(S("pin", num, S("uuid", uid("pin", ref, num))))
        node.append(S("instances", S("project", PROJECT,
                                     S("path", "/" + ROOT_UUID, S("reference", ref), S("unit", 1)))))
        self.items.append(node)

        # Pins anschließen
        for num, (px, py, ang, _typ, _nm) in pins.items():
            sx, sy = x + px, y - py                       # Bibliothek: y nach oben
            dx = -math.cos(math.radians(ang))             # nach außen, weg vom Körper
            dy = math.sin(math.radians(ang))
            if num not in conn:
                self.items.append(S("no_connect", S("at", sx, sy), S("uuid", uid("nc", ref, num))))
                continue
            net = conn[num]
            self.nets.setdefault(net, []).append(f"{ref}.{num}")
            ex, ey = sx + dx * STUB, sy + dy * STUB
            self.items.append(S("wire", S("pts", S("xy", sx, sy), S("xy", ex, ey)),
                                S("stroke", S("width", 0), S("type", Sym("default"))),
                                S("uuid", uid("wire", ref, num))))
            if abs(dx) > 0.5:
                angle, just = (0, "left") if dx > 0 else (180, "right")
            else:
                angle, just = (270, "right") if dy > 0 else (90, "left")
            self.items.append(S("label", net, S("at", ex, ey, angle),
                                S("effects", S("font", S("size", 1.27, 1.27)),
                                  S("justify", Sym(just), Sym("bottom"))),
                                S("uuid", uid("label", ref, num))))

    def write(self):
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        tb = S("title_block",
               S("title", "Dunstabzug Steuerplatine (ESP32, Relaisstufen, LED-Licht)"),
               S("date", "2026-11-21"), S("rev", "0.1"),
               S("comment", 1, "Konzeptstand - 230-V-Teil durch Elektrofachkraft pruefen lassen"),
               S("comment", 2, "Erzeugt mit generate_schematic.py - Aenderungen bitte im Skript"))
        doc = S("kicad_sch", S("version", 20250114), S("generator", "dunstabzug_gen"),
                S("generator_version", "9.0"), S("uuid", ROOT_UUID), S("paper", "A3"), tb,
                S("lib_symbols", *self.lib.values()), *self.items,
                S("sheet_instances", S("path", "/", S("page", "1"))),
                S("embedded_fonts", Sym("no")))
        (OUT_DIR / f"{PROJECT}.kicad_sch").write_text(dump(doc) + "\n")
        pro = OUT_DIR / f"{PROJECT}.kicad_pro"
        if not pro.exists():  # Projektdatei nicht überschreiben (KiCad speichert dort Einstellungen)
            pro.write_text(json.dumps({"meta": {"filename": f"{PROJECT}.kicad_pro", "version": 3}}, indent=2) + "\n")


# ---------------------------------------------------------------------------
# Bauteile und Netze
# ---------------------------------------------------------------------------

RED = (200, 40, 30)
GREEN = (30, 120, 50)
BLUE = (40, 80, 180)

FP_MAINS_2 = "TerminalBlock_MetzConnect:TerminalBlock_MetzConnect_Type171_RT13702HBWC_1x02_P7.50mm_Horizontal"  # 7,5 mm Raster für 3 mm Netzabstand
FP_MAINS_6 = "TerminalBlock_MetzConnect:TerminalBlock_MetzConnect_Type171_RT13706HBWC_1x06_P7.50mm_Horizontal"
FP_LV_2 = "TerminalBlock_Phoenix:TerminalBlock_Phoenix_MKDS-1,5-2-5.08_1x02_P5.08mm_Horizontal"
FP_LV_3 = "TerminalBlock_Phoenix:TerminalBlock_Phoenix_MKDS-1,5-3-5.08_1x03_P5.08mm_Horizontal"
FP_FUSE = "Fuse:Fuseholder_Cylinder-5x20mm_Schurter_0031_8201_Horizontal_Open"  # Schurter OGN, bei Reichelt (PL OGN-22,5 + Haube PL OGN-A)
FP_R = "Resistor_THT:R_Axial_DIN0207_L6.3mm_D2.5mm_P10.16mm_Horizontal"
FP_R_1W = "Resistor_THT:R_Axial_DIN0414_L11.9mm_D4.5mm_P15.24mm_Horizontal"
FP_X2 = "Capacitor_THT:C_Rect_L18.0mm_W6.0mm_P15.00mm_FKS3_FKP3"
FP_CP = "Capacitor_THT:CP_Radial_D6.3mm_P2.50mm"
FP_HDR19 = "Connector_PinSocket_2.54mm:PinSocket_1x19_P2.54mm_Vertical"


def build():
    s = Schematic()

    # ---------------- Netzzone ----------------
    s.box(15, 15, 235, 285, RED)
    s.text("230 V AC - NETZZONE (nur Elektrofachkraft)", 18, 22, 2.5)

    s.text("Netzeingang und Absicherung", 18, 32)
    s.part("Connector", "Screw_Terminal_01x02", "J1", "Netz L/N", 35.56, 50.8, FP_MAINS_2,
           {"1": "L_IN", "2": "N"}, note="PE nicht ueber die Platine, Wago im Gehaeuse")
    s.part("Device", "Fuse", "F1", "T 2,5 A", 55.88, 50.8, FP_FUSE, {"1": "L_IN", "2": "L_F"})
    s.part("Device", "Varistor", "RV1", "S14K275", 76.2, 50.8,
           "Varistor:RV_Disc_D15.5mm_W4.3mm_P7.5mm", {"1": "L_F", "2": "N"})
    s.part("Device", "C", "C1", "100n X2", 96.52, 50.8, FP_X2, {"1": "L_F", "2": "N"})
    s.part("Device", "Fuse", "F2", "T 1 A", 116.84, 50.8, FP_FUSE, {"1": "L_F", "2": "L_PS"})
    s.part("power", "PWR_FLAG", "#FLG01", "PWR_FLAG", 139.7, 45.72, "", {"1": "L_PS"})
    s.part("power", "PWR_FLAG", "#FLG02", "PWR_FLAG", 154.94, 45.72, "", {"1": "N"})

    s.text("Netzteil 230 V AC -> 12 V DC (verstaerkte Isolation im Modul)", 18, 75)
    s.part("Converter_ACDC", "IRM-20-12", "PS1", "IRM-20-12", 50.8, 93.98, "",
           {"1": "L_PS", "2": "N", "3": "GND", "4": "+12V"})

    s.text("Motor-Relais K1-K4 (Kontakte 230 V, Spulen 12 V)", 18, 117)
    relais = [("K1", "M_L", "Boost direkt"), ("K2", "CM1_A", "Stufe 1"),
              ("K3", "CM2_A", "Stufe 2"), ("K4", "CM3_A", "Stufe 3")]
    for i, (ref, out, txt) in enumerate(relais):
        x = 38.1 + i * 45.72
        s.part("Relay", "FINDER-40.31", ref, f"40.31 12V - {txt}", x, 142.24, "",
               {"A1": "+12V", "A2": f"{ref}_A2", "11": "L_F", "14": out})

    s.text("Vorschaltkondensatoren CM1-CM3 (extern) mit Entladewiderstaenden", 18, 177)
    s.part("Connector", "Screw_Terminal_01x06", "J4", "CM1-CM3 extern", 35.56, 205.74, FP_MAINS_6,
           {"6": "CM1_A", "5": "M_L", "4": "CM2_A", "3": "M_L", "2": "CM3_A", "1": "M_L"},
           note="CM1-CM3 MKP >=450 V AC, Startwerte 4/6/8 uF")
    for i in range(3):
        x = 71.12 + i * 22.86
        s.part("Device", "R", f"R{2*i+1}", "470k", x, 195.58, FP_R, {"1": f"CM{i+1}_A", "2": f"BL{i+1}"})
        s.part("Device", "R", f"R{2*i+2}", "470k", x, 218.44, FP_R, {"1": f"BL{i+1}", "2": "M_L"})

    s.text("Motorausgang und RC-Snubber (optional)", 18, 236)
    s.part("Connector", "Screw_Terminal_01x02", "J3", "Motor L/N", 35.56, 254, FP_MAINS_2,
           {"1": "M_L", "2": "N"}, note="Motor wie bisher am Schalter, Betriebskondensator 6,5 uF bleibt am Motor")
    s.part("Device", "R", "R7", "100R 1W", 71.12, 248.92, FP_R_1W, {"1": "M_L", "2": "SNUB"})
    s.part("Device", "C", "C2", "100n X2", 71.12, 274.32, FP_X2, {"1": "SNUB", "2": "N"})

    # ---------------- Kleinspannung ----------------
    s.box(240, 15, 405, 285, GREEN)
    s.text("KLEINSPANNUNG 12 V / 5 V / 3,3 V (SELV)", 243, 22, 2.5)

    s.text("12 V -> 5 V", 243, 32)
    s.part("Device", "C_Polarized", "C3", "47u 25V", 256.54, 50.8, FP_CP, {"1": "+12V", "2": "GND"})
    s.part("Converter_DCDC", "R-78E5.0-0.5", "U2", "R-78E5.0-0.5", 281.94, 50.8, "",
           {"1": "+12V", "2": "GND", "3": "+5V"})
    s.part("Device", "C_Polarized", "C4", "22u 10V", 307.34, 50.8, FP_CP, {"1": "+5V", "2": "GND"})

    s.text("Relaistreiber", 243, 75)
    s.part("Transistor_Array", "ULN2003A", "U1", "ULN2003A", 271.78, 99.06, "Package_DIP:DIP-16_W7.62mm",
           {"1": "K1_CTRL", "2": "K2_CTRL", "3": "K3_CTRL", "4": "K4_CTRL",
            "8": "GND", "9": "+12V",
            "16": "K1_A2", "15": "K2_A2", "14": "K3_A2", "13": "K4_A2"})

    s.text("ESP32-DevKitC-32U (gesteckt)", 330, 32)
    s.text("J7 = DevKitC J2 (links)   J8 = DevKitC J3 (rechts)", 330, 36, 1.27, False)
    s.part("Connector_Generic", "Conn_01x19", "J7", "DevKitC J2", 345.44, 68.58, FP_HDR19,
           {"1": "+3V3", "9": "LED_PWM", "14": "GND", "19": "+5V"},
           note="1 3V3, 9 IO25, 14 GND, 19 5V")
    s.part("Connector_Generic", "Conn_01x19", "J8", "DevKitC J3", 386.08, 68.58, FP_HDR19,
           {"1": "GND", "7": "GND", "8": "K4_CTRL", "9": "K3_CTRL", "11": "K2_CTRL",
            "12": "K1_CTRL", "13": "ONEWIRE"},
           note="1 GND, 7 GND, 8 IO19, 9 IO18, 11 IO17, 12 IO16, 13 IO4")
    s.text("IO16 K1 Boost  IO17 K2  IO18 K3  IO19 K4  IO25 Licht-PWM  IO4 1-Wire", 330, 100, 1.27, False)

    s.text("LED-Licht 12 V (PWM)", 243, 130)
    s.part("Device", "R", "R8", "100R", 256.54, 152.4, FP_R, {"1": "LED_PWM", "2": "LED_G"})
    s.part("Device", "R", "R9", "10k", 271.78, 152.4, FP_R, {"1": "LED_G", "2": "GND"})
    s.part("Transistor_FET", "AO3400A", "Q1", "AO3400A", 294.64, 152.4, "",
           {"1": "LED_G", "2": "GND", "3": "LED_NEG"})
    s.part("Connector", "Screw_Terminal_01x02", "J5", "Licht +12V/LED-", 325.12, 152.4, FP_LV_2,
           {"1": "+12V", "2": "LED_NEG"})

    s.text("Temperatursensor (optional, DS18B20)", 243, 180)
    s.part("Device", "R", "R10", "4k7", 256.54, 200.66, FP_R, {"1": "+3V3", "2": "ONEWIRE"})
    s.part("Connector", "Screw_Terminal_01x03", "J6", "DS18B20 3V3/DQ/GND", 287.02, 200.66, FP_LV_3,
           {"1": "+3V3", "2": "ONEWIRE", "3": "GND"})

    s.text("Befestigung", 243, 230)
    for i in range(4):
        s.part("Mechanical", "MountingHole", f"H{i+1}", "M3", 256.54 + i * 15.24, 248.92,
               "MountingHole:MountingHole_3.2mm_M3")

    return s


if __name__ == "__main__":
    sch = build()
    sch.write()
    print(f"geschrieben: {OUT_DIR / (PROJECT + '.kicad_sch')}")
    singles = [n for n, p in sch.nets.items() if len(p) < 2]
    if singles:
        print("WARNUNG: Netze mit nur einem Anschluss:", singles)
    if sch.missing_fp:
        print("WARNUNG: Footprint nicht gefunden:", *sch.missing_fp, sep="\n  ")
    print(f"{len(sch.nets)} Netze")
