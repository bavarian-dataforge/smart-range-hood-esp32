#!/usr/bin/env python3
"""
Trägerplatte für den Einbau in den Aufnahmeraum der alten Steuerung.

Erzeugt eine Bohrschablone 1:1 (A4 hochkant, SVG in mm). Ausdrucken mit 100 %
(„Tatsächliche Größe“), Kontrollmaß 100 mm nachmessen, aufkleben, körnen, bohren.

Maße Aufnahmeraum (Skizze 23.11.2026): 145 mm breit, 220 mm tief,
Auflageleisten 10 mm, Laschen vorne 45 mm über der Leiste, ca. 5 mm von der Wand.

Koordinaten: X quer (0 = linke Plattenkante), Y in Einschubrichtung
(0 = Vorderkante an der Öffnung, wächst nach hinten).

Aufruf: python3 make_traegerplatte.py  ->  traegerplatte-bohrschablone.svg
"""
from pathlib import Path

# --- Platte -----------------------------------------------------------------
PLATE_W = 143.0          # 145 mm Raum - 2 mm Spiel
PLATE_D = 205.0          # 220 mm Raum - 15 mm Spalt hinten (kein Anschlag)
PLATE_T = 3.0            # Polycarbonat/FR4

# --- Platine 100 x 160, Netzklemmen (Platinen-x = 0) nach hinten ------------
PCB_W, PCB_L = 100.0, 160.0
PCB_X0 = (PLATE_W - PCB_W) / 2          # links/rechts gleich viel Luft
PCB_Y_BACK = 162.0                       # Hinterkante der Platine
PCB_HOLES = [(4, 4), (156, 4), (4, 96), (156, 96)]   # aus dem KiCad-Layout (H1-H4)


def pcb_to_plate(xb, yb):
    """Platinen-Koordinate (x 0..160 entlang, y 0..100 quer) -> Platte."""
    return PCB_X0 + yb, PCB_Y_BACK - xb


# --- Becherkondensatoren stehend, M8-Bolzen ---------------------------------
CAP_Y = (PCB_Y_BACK + PLATE_D) / 2
CAP_X = [PLATE_W / 2 - 30, PLATE_W / 2 + 30]
CAP_D_MAX = 40.0

# --- Winkel vorne (Alu 25 x 50, 15 mm breit), Langloch zur Lasche ----------
ANGLE_X0, ANGLE_W, ANGLE_LEG = 0.0, 15.0, 25.0
LASCHE_X = 5.0 - 1.0                     # 5 mm von der Wand, Platte 1 mm von der Wand
LASCHE_H = 45.0 - PLATE_T                # über Plattenoberseite

holes = []   # (x, y, d, label)
for xb, yb in PCB_HOLES:
    x, y = pcb_to_plate(xb, yb)
    holes.append((x, y, 3.2, "M3 Abstandsbolzen Platine"))
for x in CAP_X:
    holes.append((x, CAP_Y, 8.5, "M8 Becherkondensator"))
for side in ("L", "R"):
    x0 = ANGLE_X0 + 7.5 if side == "L" else PLATE_W - 7.5
    for y in (7.0, 18.0):
        holes.append((x0, y, 3.2, f"M3 Winkel {side}"))
for x in (14.0, PLATE_W - 14.0):        # Kabelbinder innerhalb der Leisten (Leiste 10 mm)
    for y in (40.0, 100.0, 150.0, 195.0):
        holes.append((x, y - 3, 4.0, "Kabelbinder"))
        holes.append((x, y + 3, 4.0, "Kabelbinder"))


def svg():
    W, H = 210, 297
    ox, oy = (W - PLATE_W) / 2, 30          # Platte auf dem Blatt, Vorderkante unten
    def P(x, y):                             # Y wächst nach hinten = nach oben auf dem Blatt
        return ox + x, oy + PLATE_D - y
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}mm" height="{H}mm" viewBox="0 0 {W} {H}" '
         f'font-family="Helvetica, Arial, sans-serif">',
         f'<rect width="{W}" height="{H}" fill="#fff"/>',
         f'<text x="10" y="10" font-size="5" font-weight="bold">Trägerplatte {PLATE_W:.0f} × {PLATE_D:.0f} × {PLATE_T:.0f} mm – Bohrschablone 1:1</text>',
         '<text x="10" y="16" font-size="3">Mit 100 % drucken, Kontrollmaß unten messen. Isolierend: Polycarbonat oder FR4. Blick von oben.</text>',
         '<text x="10" y="21" font-size="3">↑ hinten (geschlossen, ca. 15 mm Spalt)</text>']
    x, y = P(0, PLATE_D)
    o.append(f'<rect x="{x}" y="{y}" width="{PLATE_W}" height="{PLATE_D}" fill="none" stroke="#000" stroke-width="0.4"/>')
    # Platine
    x0, y0 = P(PCB_X0, PCB_Y_BACK)
    o.append(f'<rect x="{x0}" y="{y0}" width="{PCB_W}" height="{PCB_L}" fill="#2f7d46" fill-opacity="0.12" stroke="#2f7d46" stroke-width="0.3" stroke-dasharray="2 1"/>')
    o.append(f'<text x="{x0 + PCB_W/2}" y="{y0 + 6}" font-size="3" text-anchor="middle" fill="#2f7d46">Platine 100 × 160 – Netzklemmen hier (hinten)</text>')
    o.append(f'<text x="{x0 + PCB_W/2}" y="{y0 + PCB_L - 3}" font-size="3" text-anchor="middle" fill="#2f7d46">ESP32 / Kleinspannung vorne</text>')
    # Kondensatoren
    for cx in CAP_X:
        x, y = P(cx, CAP_Y)
        o.append(f'<circle cx="{x}" cy="{y}" r="{CAP_D_MAX/2}" fill="none" stroke="#1d4f99" stroke-width="0.3" stroke-dasharray="2 1"/>')
    # Winkel
    for xa in (ANGLE_X0, PLATE_W - ANGLE_W):
        x, y = P(xa, ANGLE_LEG)
        o.append(f'<rect x="{x}" y="{y}" width="{ANGLE_W}" height="{ANGLE_LEG}" fill="#999" fill-opacity="0.15" stroke="#666" stroke-width="0.3" stroke-dasharray="1.5 1"/>')
    # Bohrungen mit Fadenkreuz
    for hx, hy, d, _ in holes:
        x, y = P(hx, hy)
        o.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="{d/2}" fill="none" stroke="#c00" stroke-width="0.25"/>')
        o.append(f'<path d="M{x-d/2-1.5:.2f} {y:.2f} H{x+d/2+1.5:.2f} M{x:.2f} {y-d/2-1.5:.2f} V{y+d/2+1.5:.2f}" stroke="#c00" stroke-width="0.15"/>')
    # Legende
    ly = oy + PLATE_D + 8
    o.append(f'<text x="{ox}" y="{oy + PLATE_D + 4}" font-size="3">↓ vorne (Öffnung, Einschub) – Winkel links/rechts an die Laschen</text>')
    leg = [("Ø 3,2", "4× Abstandsbolzen Platine M3 × 10, 4× Winkel M3 Senkkopf von unten (liegt auf der Leiste)"),
           ("Ø 8,5", "2× Becherkondensator M8 (Mutter unten)"),
           ("Ø 4,0", "16× Kabelbinder 2,5–3,6 mm (Zugentlastung)")]
    for i, (a, b) in enumerate(leg):
        o.append(f'<text x="{ox}" y="{ly + 5*i + 4}" font-size="3"><tspan font-weight="bold">{a}</tspan>  {b}</text>')
    wy = ly + 19
    o.append(f'<text x="{ox}" y="{wy}" font-size="3"><tspan font-weight="bold">Winkel</tspan> Alu 25 × 50 × 2 mm, 15 mm breit. Langloch 4,5 × 10 mm (senkrecht) im 50er-Schenkel,</text>')
    o.append(f'<text x="{ox}" y="{wy+4.5}" font-size="3">Mitte ca. {LASCHE_H:.0f} mm über Plattenoberseite – erst nach Probeeinschub an der Lasche anzeichnen.</text>')
    o.append(f'<text x="{ox}" y="{wy+9}" font-size="3" fill="#c00">Noch prüfen: Höhe ≥ 100 mm, Lage/Ø der Laschenschraube, Bolzengröße der Becherkondensatoren.</text>')
    # Kontrollmaß
    cy = H - 12
    o.append(f'<path d="M{ox} {cy} H{ox+100} M{ox} {cy-2} V{cy+2} M{ox+100} {cy-2} V{cy+2}" stroke="#000" stroke-width="0.3"/>')
    o.append(f'<text x="{ox+50}" y="{cy-3}" font-size="3" text-anchor="middle">Kontrollmaß 100 mm</text>')
    o.append('</svg>')
    return "\n".join(o)


def main():
    out = Path(__file__).resolve().parent / "traegerplatte-bohrschablone.svg"
    out.write_text(svg(), encoding="utf-8")
    print("geschrieben:", out)
    for hx, hy, d, lab in holes:
        print(f"  X {hx:6.1f}  Y {hy:6.1f}  Ø {d:3.1f}  {lab}")


if __name__ == "__main__":
    main()
