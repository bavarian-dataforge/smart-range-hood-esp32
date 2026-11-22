#!/usr/bin/env python3
"""
Erzeugt die Platine (PCB) der Dunstabzug-Steuerplatine: Umriss, Frässchlitz,
platzierte Bauteile mit Netzen, Netzklassen, Abstandsregeln, Sperrfläche und
Beschriftung. Leiterbahnen werden NICHT verlegt (das passiert im PCB-Editor).

Muss mit dem Python von KiCad laufen (wegen des Moduls pcbnew):

  /Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3 generate_pcb.py

Vorher generate_schematic.py ausführen. Achtung: überschreibt die .kicad_pcb.
Koordinaten in mm, Platinenecke links oben = (0, 0).
"""

import json
import re
import subprocess
import sys
from pathlib import Path

import pcbnew

HERE = Path(__file__).resolve().parent
PROJECT = "dunstabzug-steuerplatine"
PDIR = HERE / PROJECT
SCH = PDIR / f"{PROJECT}.kicad_sch"
PCB = PDIR / f"{PROJECT}.kicad_pcb"
PRO = PDIR / f"{PROJECT}.kicad_pro"
DRU = PDIR / f"{PROJECT}.kicad_dru"
KICAD_CLI = "/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli"
FP_DIR = Path("/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints")

BOARD_W, BOARD_H = 160.0, 100.0
OX, OY = 50.0, 50.0            # Lage der Platine auf dem Zeichenblatt
BARRIER_X = 100.0              # Mitte der Isolationsbarriere

# Netze der Netzzone (230 V). Alles andere ist Kleinspannung.
MAINS_NETS = ["L_IN", "L_F", "L_PS", "N", "M_L", "CM1_A", "CM2_A", "CM3_A",
              "BL1", "BL2", "BL3", "SNUB"]

# Bauteilplatzierung: Referenz -> (x, y, Drehung in Grad, gegen Uhrzeigersinn)
# Bezugspunkt ist jeweils Pad 1 des Footprints.
PLACEMENT = {
    # Netzzone
    "J1": (11, 20, 90),          # Netz L/N, Klemmen 7,5 mm Raster zum linken Rand
    "F1": (23, 8, 0),           # Sicherung T 2,5 A
    "RV1": (26, 24, 0),
    "C1": (40, 24, 0),          # X2 100 nF
    "J4": (11, 70, 90),          # Anschluss CM1–CM3, Pads y 70 … 32,5
    # Entladewiderstände: je Kondensator eine Reihe CMx -> R_ungerade -> BLx -> R_gerade -> M_L.
    # Bewusst nicht direkt neben J4: dort bleibt bei 3 mm Netzabstand kein Platz für Leiterbahnen.
    "R1": (40, 40, 0), "R2": (54, 40, 0),
    "R3": (40, 52, 0), "R4": (54, 52, 0),
    "R5": (40, 64, 0), "R6": (54, 64, 0),
    "F2": (30, 82, 0),          # Sicherung Netzteil T 1 A
    "J3": (11, 86, 90),          # Motor, Pads y 86 / 78,5
    "R7": (24, 94, 0), "C2": (46, 94, 0),   # RC-Snubber
    # Über der Barriere: Spule rechts (SELV), Kontakte links (Netz)
    "K1": (108, 14, 180), "K2": (108, 30, 180), "K3": (108, 46, 180), "K4": (108, 62, 180),
    "PS1": (72, 73, 0),         # AC links, DC rechts
    # Kleinspannung
    "U1": (113, 18, 0),
    "J7": (128, 10, 0), "J8": (153.4, 10, 0),   # ESP32-DevKitC, Reihenabstand 25,4 mm
    "U2": (124, 66, 0), "C4": (137, 64, 0), "C3": (124, 74, 0),
    "R8": (139, 70, 0), "R9": (139, 76, 0), "Q1": (154, 73, 0),
    "R10": (124, 80, 0),
    "J6": (126, 90, 0), "J5": (144, 90, 0),
    # Befestigung
    "H1": (4, 4, 0), "H2": (156, 4, 0), "H3": (4, 96, 0), "H4": (156, 96, 0),
}


def mm(v):
    return pcbnew.FromMM(v)


def pt(x, y):
    return pcbnew.VECTOR2I(mm(OX + x), mm(OY + y))


# ---------------------------------------------------------------------------
# Netzliste aus dem Schaltplan
# ---------------------------------------------------------------------------

def read_netlist():
    out = PDIR / "netlist.net"
    subprocess.run([KICAD_CLI, "sch", "export", "netlist", "--format", "kicadsexpr",
                    "-o", str(out), str(SCH)], check=True, capture_output=True)
    text = out.read_text()
    out.unlink()
    comps = {}
    for m in re.finditer(r'\(comp\s+\(ref "([^"]+)"\)\s*\(value "([^"]*)"\)\s*\(footprint "([^"]*)"\)', text):
        comps[m.group(1)] = (m.group(2), m.group(3))
    pin_net = {}
    for m in re.finditer(r'\(net\s*\(code "?\d+"?\)\s*\(name "([^"]+)"\)(.*?)\n\t\t\)', text, re.S):
        for ref, pin in re.findall(r'\(ref "([^"]+)"\)\s*\(pin "([^"]+)"\)', m.group(2)):
            pin_net[(ref, pin)] = m.group(1)
    return comps, pin_net


# ---------------------------------------------------------------------------
# Projekt: Netzklassen und Regeln
# ---------------------------------------------------------------------------

def netclass(name, clearance, track, prio):
    return {"bus_width": 12, "clearance": clearance, "diff_pair_gap": 0.25,
            "diff_pair_via_gap": 0.25, "diff_pair_width": 0.2, "line_style": 0,
            "microvia_diameter": 0.3, "microvia_drill": 0.1, "name": name,
            "pcb_color": "rgba(0, 0, 0, 0.000)", "priority": prio,
            "schematic_color": "rgba(0, 0, 0, 0.000)", "track_width": track,
            "via_diameter": 0.8, "via_drill": 0.4, "wire_width": 6}


def write_project_rules():
    pro = json.loads(PRO.read_text()) if PRO.exists() else {}
    pro.setdefault("meta", {"filename": PRO.name, "version": 3})
    pro["net_settings"] = {
        "classes": [
            netclass("Default", 0.25, 0.4, 2147483647),
            netclass("Netz", 3.0, 2.5, 0),
            netclass("SELV", 0.25, 0.5, 1),
        ],
        "meta": {"version": 4},
        "net_colors": None,
        "netclass_assignments": None,
        "netclass_patterns": (
            [{"netclass": "Netz", "pattern": f"/{n}"} for n in MAINS_NETS] +
            [{"netclass": "SELV", "pattern": p} for p in
             ["/+12V", "/+5V", "/+3V3", "/GND", "/K?_A2", "/K?_CTRL", "/LED_*", "/ONEWIRE"]]
        ),
    }
    PRO.write_text(json.dumps(pro, indent=2) + "\n")

    DRU.write_text(
        "(version 1)\n\n"
        "# Verstaerkte Isolierung zwischen Netz (230 V) und Kleinspannung (SELV).\n"
        "# Kueche = verschmutzte Umgebung, daher grosszuegig.\n"
        "(rule \"Netz zu SELV Luftstrecke\"\n"
        "  (condition \"A.NetClass == 'Netz' && B.NetClass == 'SELV'\")\n"
        "  (constraint clearance (min 8mm)))\n\n"
        "(rule \"Netz zu SELV Kriechstrecke\"\n"
        "  (condition \"A.NetClass == 'Netz' && B.NetClass == 'SELV'\")\n"
        "  (constraint creepage (min 8mm)))\n\n"
        "# Netz untereinander (L, N, Motor, Kondensatoren): 3 mm Luft- und Kriechstrecke\n"
        "(rule \"Netz zu Netz Kriechstrecke\"\n"
        "  (condition \"A.NetClass == 'Netz' && B.NetClass == 'Netz'\")\n"
        "  (constraint creepage (min 3mm)))\n\n"
        "# Netz: Abstand zu Platinenrand und Befestigungsloechern (Schraube am Gehaeuse)\n"
        "(rule \"Netz Randabstand\"\n"
        "  (condition \"A.NetClass == 'Netz'\")\n"
        "  (constraint edge_clearance (min 2mm)))\n\n"
        "(rule \"Netz Lochabstand\"\n"
        "  (condition \"A.NetClass == 'Netz' && B.Type == 'Footprint' && B.Reference == 'H*'\")\n"
        "  (constraint hole_clearance (min 3.5mm)))\n\n"
        "# Netzleiterbahnen breit genug fuer 2-3 A\n"
        "(rule \"Netz Leiterbahnbreite\"\n"
        "  (condition \"A.NetClass == 'Netz'\")\n"
        "  (constraint track_width (min 2mm) (opt 2.5mm)))\n"
    )


# ---------------------------------------------------------------------------
# Platine aufbauen
# ---------------------------------------------------------------------------

def add_rect(board, x1, y1, x2, y2, layer, width=0.1):
    s = pcbnew.PCB_SHAPE(board)
    s.SetShape(pcbnew.SHAPE_T_RECT)
    s.SetStart(pt(x1, y1))
    s.SetEnd(pt(x2, y2))
    s.SetLayer(layer)
    s.SetWidth(mm(width))
    board.Add(s)


def add_text(board, txt, x, y, size=2.0, layer=pcbnew.F_SilkS, angle=0):
    t = pcbnew.PCB_TEXT(board)
    t.SetText(txt)
    t.SetPosition(pt(x, y))
    t.SetLayer(layer)
    t.SetTextSize(pcbnew.VECTOR2I(mm(size), mm(size)))
    t.SetTextThickness(mm(size * 0.15))
    if angle:
        t.SetTextAngle(pcbnew.EDA_ANGLE(angle, pcbnew.DEGREES_T))
    board.Add(t)


def add_rule_area(board, x1, y1, x2, y2, name):
    z = pcbnew.ZONE(board)
    z.SetIsRuleArea(True)
    z.SetZoneName(name)
    z.SetDoNotAllowTracks(True)
    z.SetDoNotAllowVias(True)
    z.SetDoNotAllowPads(False)
    z.SetDoNotAllowFootprints(False)
    for setter in ("SetDoNotAllowZoneFills", "SetDoNotAllowCopperPour"):
        if hasattr(z, setter):
            getattr(z, setter)(True)
            break
    z.SetLayerSet(pcbnew.LSET.AllCuMask())
    ol = z.Outline()
    ol.NewOutline()
    for x, y in ((x1, y1), (x2, y1), (x2, y2), (x1, y2)):
        ol.Append(mm(OX + x), mm(OY + y))
    board.Add(z)


def build():
    comps, pin_net = read_netlist()
    missing = set(comps) - set(PLACEMENT)
    if missing:
        sys.exit(f"Keine Platzierung für: {sorted(missing)}")

    write_project_rules()
    board = pcbnew.NewBoard(str(PCB))

    # Netze anlegen
    nets = {}
    for name in sorted(set(pin_net.values())):
        ni = pcbnew.NETINFO_ITEM(board, name)
        board.Add(ni)
        nets[name] = ni

    # Bauteile
    for ref, (value, fpid) in sorted(comps.items()):
        lib, name = fpid.split(":", 1)
        fp = pcbnew.FootprintLoad(str(FP_DIR / f"{lib}.pretty"), name)
        if fp is None:
            sys.exit(f"{ref}: Footprint {fpid} nicht gefunden")
        fp.SetFPIDAsString(fpid)
        if "MetzConnect_Type171" in name:
            # KiCad liefert dafür kein 3D-Modell; eigenes aus make_3d_terminals.py
            n = int(name.split("_1x")[1][:2])
            wrl = Path(__file__).resolve().parent / "3d" / f"Schraubklemme_P7.50mm_1x{n:02d}.wrl"
            models = fp.Models()
            models.clear()
            m = pcbnew.FP_3DMODEL()
            m.m_Filename = "${KIPRJMOD}/../3d/" + wrl.name   # relativ, damit das Repo überall funktioniert
            models.push_back(m)
        fp.SetReference(ref)
        fp.SetValue(value)
        x, y, rot = PLACEMENT[ref]
        fp.SetPosition(pt(x, y))
        fp.SetOrientation(pcbnew.EDA_ANGLE(rot, pcbnew.DEGREES_T))
        if ref.startswith("H") or ref in ("R1", "R2", "R3", "R4", "R5", "R6"):
            fp.Reference().SetVisible(False)
        board.Add(fp)
        for pad in fp.Pads():
            net = pin_net.get((ref, pad.GetNumber()))
            if net:
                pad.SetNet(nets[net])

    # Umriss und Frässchlitz unter den Relais (zwischen Spule und Kontakten)
    add_rect(board, 0, 0, BOARD_W, BOARD_H, pcbnew.Edge_Cuts)
    add_rect(board, BARRIER_X - 1, 2, BARRIER_X + 1, 66, pcbnew.Edge_Cuts)

    # Keine Leiterbahnen/Kupferflächen auf der Barriere
    add_rule_area(board, BARRIER_X - 5, 0, BARRIER_X + 5, 68, "Isolationsbarriere")

    # Zonengrenze und Beschriftung
    s = pcbnew.PCB_SHAPE(board)
    s.SetShape(pcbnew.SHAPE_T_SEGMENT)
    s.SetStart(pt(BARRIER_X, 67.5))
    s.SetEnd(pt(BARRIER_X, 69))
    s.SetLayer(pcbnew.F_SilkS)
    s.SetWidth(mm(0.3))
    board.Add(s)
    add_text(board, "! 230 V AC !", 62, 31.5, 2.5)
    add_text(board, "NETZ", 62, 35.5, 2.0)
    add_text(board, "SELV 12V", 117, 48, 1.5, angle=90)
    add_text(board, "T 2,5 A", 38, 15.5, 1.5)
    add_text(board, "T 1 A", 45, 89.5, 1.5)
    add_text(board, "L  N", 3, 26, 1.2, angle=90)
    add_text(board, "Motor L N", 3, 80, 1.2, angle=90)
    add_text(board, "CM1-CM3", 3, 47, 1.2, angle=90)
    add_text(board, "R1-R6", 52, 70, 1.0)
    add_text(board, "Dunstabzug Steuerplatine v0.1", 80, 98.3, 1.2)

    pcbnew.SaveBoard(str(PCB), board)
    export_pads(board)
    print(f"geschrieben: {PCB}")
    print(f"{len(comps)} Bauteile, {len(nets)} Netze")


# ---------------------------------------------------------------------------
# Schnittstelle zum Router (route_pcb.py läuft im System-Python mit numpy)
# ---------------------------------------------------------------------------

PADS_JSON = PDIR / "routing_pads.json"
ROUTES_JSON = PDIR / "routing_result.json"
VIA = {"Netz": (1.8, 1.0), "SELV": (0.8, 0.4)}       # Durchmesser, Bohrung
SELV_ZONE = (106.0, 1.0, 159.0, 99.0)                 # GND-Fläche unten


def export_pads(board):
    pads = []
    for fp in board.GetFootprints():
        for p in fp.Pads():
            bb = p.GetBoundingBox()
            x = pcbnew.ToMM(p.GetPosition().x) - OX
            pads.append({
                "ref": fp.GetReference(), "num": p.GetNumber(),
                "net": p.GetNetname(),
                "cls": p.GetNetClassName() if p.GetNetname() and not p.GetNetname().startswith("unconnected")
                       else ("Netz" if x < BARRIER_X else "SELV"),
                "x": x, "y": pcbnew.ToMM(p.GetPosition().y) - OY,
                "w": pcbnew.ToMM(bb.GetWidth()), "h": pcbnew.ToMM(bb.GetHeight()),
                "tht": p.GetAttribute() == pcbnew.PAD_ATTRIB_PTH,
            })
        if fp.GetReference().startswith("H"):
            pads.append({"ref": fp.GetReference(), "num": "hole", "net": "", "cls": "Hole",
                         "x": pcbnew.ToMM(fp.GetPosition().x) - OX,
                         "y": pcbnew.ToMM(fp.GetPosition().y) - OY,
                         "w": 3.2, "h": 3.2, "tht": True})
    PADS_JSON.write_text(json.dumps({
        "board": [BOARD_W, BOARD_H],
        "slot": [BARRIER_X - 1, 2, BARRIER_X + 1, 66],
        "keepout": [BARRIER_X - 5, 0, BARRIER_X + 5, 68],
        "pads": pads,
    }, indent=1))


def apply_routes():
    board = pcbnew.LoadBoard(str(PCB))
    nets = {n: board.FindNet(n) for n in json.loads(ROUTES_JSON.read_text())["nets"]}
    data = json.loads(ROUTES_JSON.read_text())
    layers = [pcbnew.F_Cu, pcbnew.B_Cu]
    for t in data["tracks"]:
        tr = pcbnew.PCB_TRACK(board)
        tr.SetStart(pt(*t["a"]))
        tr.SetEnd(pt(*t["b"]))
        tr.SetWidth(mm(t["w"]))
        tr.SetLayer(layers[t["layer"]])
        tr.SetNet(nets[t["net"]])
        board.Add(tr)
    for v in data["vias"]:
        via = pcbnew.PCB_VIA(board)
        via.SetPosition(pt(*v["p"]))
        d, drill = VIA[v["cls"]]
        via.SetWidth(mm(d))
        via.SetDrill(mm(drill))
        via.SetNet(nets[v["net"]])
        board.Add(via)

    # GND-Fläche auf der Unterseite der Kleinspannungszone
    gnd = board.FindNet("/GND")
    z = pcbnew.ZONE(board)
    z.SetLayer(pcbnew.B_Cu)
    z.SetNet(gnd)
    z.SetZoneName("GND SELV")
    z.SetLocalClearance(mm(0.4))
    z.SetMinThickness(mm(0.3))
    z.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL)
    ol = z.Outline()
    ol.NewOutline()
    x1, y1, x2, y2 = SELV_ZONE
    for x, y in ((x1, y1), (x2, y1), (x2, y2), (x1, y2)):
        ol.Append(mm(OX + x), mm(OY + y))
    board.Add(z)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())

    pcbnew.SaveBoard(str(PCB), board)
    print(f"Leiterbahnen: {len(data['tracks'])}, Vias: {len(data['vias'])}, GND-Fläche gefüllt")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--apply-routes":
        apply_routes()
    else:
        build()
