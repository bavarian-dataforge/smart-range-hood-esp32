#!/usr/bin/env python3
"""
Einfache 3D-Modelle (VRML) für die Netz-Schraubklemmen J1, J3, J4.

KiCad 10 liefert für MetzConnect Type 171 (RT137, Raster 7,5 mm) keine
3D-Modelle mit. Dieses Skript erzeugt Platzhalter: grüner Klemmenkörper,
Schraubenköpfe oben, Leitereinführungen zum Platinenrand.

Aufruf:   python3 make_3d_terminals.py
Schreibt: 3d/Schraubklemme_P7.50mm_1x02.wrl und _1x06.wrl
generate_pcb.py hängt diese Modelle an J1, J3 und J4.

Maße aus dem Footprint (F.Fab): Körper x -3,75 … (n-1)·7,5+3,75, y -4,5 … 4,5.
Höhe geschätzt 12 mm. Leitereinführung auf der Footprint-Seite -y.
"""
import math
from pathlib import Path

OUT = Path(__file__).resolve().parent / "3d"
PITCH = 7.5
HEIGHT = 12.0

GREEN = "0.2 0.65 0.3"
METAL = "0.75 0.75 0.78"
DARK = "0.08 0.08 0.08"


class Mesh:
    """Sammelt Flächen je Farbe. KiCads VRML-Leser verarbeitet einfache
    IndexedFaceSets zuverlässig, verschachtelte Transforms/Primitive nicht."""

    def __init__(self):
        self.parts = {}

    def _add(self, color, pts, faces):
        P, F = self.parts.setdefault(color, ([], []))
        off = len(P)
        P.extend(pts)
        F.extend([[i + off for i in f] for f in faces])

    def box(self, cx, cy, cz, sx, sy, sz, color):
        x0, x1 = cx - sx / 2, cx + sx / 2
        y0, y1 = cy - sy / 2, cy + sy / 2
        z0, z1 = cz - sz / 2, cz + sz / 2
        pts = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
               (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
        faces = [[3, 2, 1, 0], [4, 5, 6, 7], [0, 1, 5, 4],
                 [1, 2, 6, 5], [2, 3, 7, 6], [3, 0, 4, 7]]
        self._add(color, pts, faces)

    def cyl(self, cx, cy, cz, r, h, color, seg=20):
        pts = []
        for z in (cz - h / 2, cz + h / 2):
            for i in range(seg):
                a = 2 * math.pi * i / seg
                pts.append((cx + r * math.cos(a), cy + r * math.sin(a), z))
        faces = [list(range(seg - 1, -1, -1)), [seg + i for i in range(seg)]]
        for i in range(seg):
            j = (i + 1) % seg
            faces.append([i, j, seg + j, seg + i])
        self._add(color, pts, faces)

    def vrml(self):
        out = ["#VRML V2.0 utf8\n"]
        for color, (P, F) in self.parts.items():
            # KiCad: 1 VRML-Einheit = 0,1 Zoll = 2,54 mm
            pts = ", ".join(f"{x / 2.54:.4f} {y / 2.54:.4f} {z / 2.54:.4f}" for x, y, z in P)
            idx = " ".join(" ".join(map(str, f)) + " -1" for f in F)
            out.append(f"Shape {{ appearance Appearance {{ material Material {{ diffuseColor {color} }} }}\n"
                       f"  geometry IndexedFaceSet {{ solid FALSE coord Coordinate {{ point [ {pts} ] }}\n"
                       f"    coordIndex [ {idx} ] }} }}\n")
        return "".join(out)


def model(n):
    # VRML-Koordinaten: x wie Footprint, y = -y(Footprint), z nach oben, Einheit mm
    m = Mesh()
    x0, x1 = -3.75, (n - 1) * PITCH + 3.75
    m.box((x0 + x1) / 2, 0, HEIGHT / 2, x1 - x0, 9.0, HEIGHT, GREEN)
    for i in range(n):
        x = i * PITCH
        m.cyl(x, -1.0, HEIGHT + 0.4, 2.4, 0.8, METAL)          # Schraubenkopf
        m.box(x, -1.0, HEIGHT + 0.9, 3.4, 0.7, 0.2, DARK)      # Schlitz
        m.box(x, 4.55, 4.5, 5.0, 0.2, 4.5, DARK)               # Leitereinführung
        m.box(x, 4.7, 4.5, 3.6, 0.2, 3.0, METAL)               # Klemmkorb
    return m.vrml()


def main():
    OUT.mkdir(exist_ok=True)
    for n in (2, 6):
        p = OUT / f"Schraubklemme_P7.50mm_1x{n:02d}.wrl"
        p.write_text(model(n))
        print("geschrieben:", p)


if __name__ == "__main__":
    main()
