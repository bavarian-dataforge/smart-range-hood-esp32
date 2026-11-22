#!/usr/bin/env python3
"""
Einfacher Leiterbahn-Router für die Dunstabzug-Steuerplatine (2 Lagen).

Prinzip (Labyrinth-Router, "A*" auf einem 0,5-mm-Raster):
  1. Alle Pads und bereits verlegten Bahnen anderer Netze sind Hindernisse,
     aufgeblasen um Abstand + halbe Bahnbreite. Die Abstände kommen aus den
     Netzklassen: Netz<->Netz 3 mm, Netz<->SELV 8 mm, SELV<->SELV 0,3 mm.
  2. Ein Netz wird Pad für Pad an den schon verbundenen Teil angeschlossen
     (kürzester Weg, Lagenwechsel über Via kostet extra).
  3. Gefundene Wege werden zu geraden Segmenten zusammengefasst.

Das Ergebnis prüft danach KiCad mit dem DRC; der Router ist nur ein Helfer.

Aufruf (System-Python mit numpy):  python3 route_pcb.py
Liest  dunstabzug-steuerplatine/routing_pads.json (von generate_pcb.py)
Schreibt dunstabzug-steuerplatine/routing_result.json
"""

import heapq
import json
import os
import math
import sys
from pathlib import Path

import numpy as np

PDIR = Path(__file__).resolve().parent / "dunstabzug-steuerplatine"
G = 0.5                  # Rasterweite in mm
MARGIN = 0.25            # Sicherheitszuschlag für Rasterfehler
EDGE_CLR = 0.5

# Bahnbreiten je Netz (mm). Netz-Klasse 2,5 mm, Versorgung 0,8, Signale 0,4.
WIDTH = {"Netz": 2.5, "SELV": 0.4}
SELV_POWER = {"/+12V", "/GND", "/+5V", "/LED_NEG", "/+3V3"}
VIA_D = {"Netz": 1.8, "SELV": 0.8}
VIA_COST = {"Netz": 40.0, "SELV": 8.0}

# Bevorzugte Lage: 0 = oben (F.Cu), 1 = unten (B.Cu).
# Netz: Ausgänge (M_L, CMx) oben, Phase/Neutralleiter unten -> wenig Kreuzungen.
PREF_LAYER = {"/M_L": 0, "/CM1_A": 0, "/CM2_A": 0, "/CM3_A": 0, "/BL1": 0, "/BL2": 0,
              "/BL3": 0, "/SNUB": 0, "/L_PS": 0,
              "/L_F": 1, "/N": 1, "/L_IN": 1,
              "/GND": 1, "/+12V": 0, "/+5V": 0}

# Reihenfolge: Relaisausgänge zuerst (eingeklemmt zwischen Relais und J4),
# dann Phase und Neutralleiter, dann Kleinspannung.
ORDER = ["/CM3_A", "/CM2_A", "/CM1_A", "/M_L", "/L_F", "/N", "/L_IN", "/L_PS",
         "/BL1", "/BL2", "/BL3", "/SNUB",
         "/+12V", "/GND", "/+5V", "/K1_A2", "/K2_A2", "/K3_A2", "/K4_A2",
         "/K1_CTRL", "/K2_CTRL", "/K3_CTRL", "/K4_CTRL",
         "/LED_PWM", "/LED_G", "/LED_NEG", "/ONEWIRE", "/+3V3"]
# Zum Ausprobieren: ROUTE_FIRST="/L_F,/N" verlegt diese Netze zuerst
if os.environ.get("ROUTE_FIRST"):
    _first = os.environ["ROUTE_FIRST"].split(",")
    ORDER = _first + [n for n in ORDER if n not in _first]


def clearance(a, b):
    if {a, b} == {"Netz", "SELV"}:
        return 8.0
    if "Netz" in (a, b):
        return 3.0
    return 0.3


class Router:
    def __init__(self, data):
        self.W, self.H = data["board"]
        self.nx = int(round(self.W / G)) + 1
        self.ny = int(round(self.H / G)) + 1
        xs = np.arange(self.nx) * G
        ys = np.arange(self.ny) * G
        self.X, self.Y = np.meshgrid(xs, ys)          # [iy, ix]
        self.pads = data["pads"]
        self.slot = data["slot"]
        self.keepout = data["keepout"]
        self.copper = []      # (kind, geom, net, cls, layers, halfwidth)
        for p in self.pads:
            if p["cls"] == "Hole":
                continue
            layers = (0, 1) if p["tht"] else (0,)
            self.copper.append(("rect", (p["x"], p["y"], p["w"] / 2, p["h"] / 2),
                                p["net"], p["cls"], layers, 0.0))
        self.tracks, self.vias, self.failed = [], [], []

    # ---------------- Hindernis-Masken ----------------

    def _dist_rect(self, cx, cy, hw, hh, sl):
        dx = np.maximum(np.abs(self.X[sl] - cx) - hw, 0)
        dy = np.maximum(np.abs(self.Y[sl] - cy) - hh, 0)
        return np.hypot(dx, dy)

    def _dist_seg(self, ax, ay, bx, by, sl):
        px, py = self.X[sl] - ax, self.Y[sl] - ay
        vx, vy = bx - ax, by - ay
        L2 = vx * vx + vy * vy
        t = np.clip((px * vx + py * vy) / L2, 0, 1) if L2 > 0 else 0
        return np.hypot(px - t * vx, py - t * vy)

    def _region(self, x1, y1, x2, y2):
        ix1 = max(int(math.floor(x1 / G)), 0)
        iy1 = max(int(math.floor(y1 / G)), 0)
        ix2 = min(int(math.ceil(x2 / G)) + 1, self.nx)
        iy2 = min(int(math.ceil(y2 / G)) + 1, self.ny)
        return (slice(iy1, iy2), slice(ix1, ix2))

    def blocked(self, net, cls, radius):
        """Maske [layer, iy, ix]: True = Mittellinie einer Bahn mit Radius 'radius' darf hier nicht hin."""
        m = np.zeros((2, self.ny, self.nx), dtype=bool)
        # Platinenrand
        e = radius + (2.0 if cls == "Netz" else EDGE_CLR) + MARGIN   # Netz: 2 mm zum Rand
        edge = (self.X < e) | (self.X > self.W - e) | (self.Y < e) | (self.Y > self.H - e)
        m[:] |= edge
        # Schlitz und Sperrfläche
        x1, y1, x2, y2 = self.slot
        sl = self._region(x1 - e, y1 - e, x2 + e, y2 + e)
        m[:, sl[0], sl[1]] |= self._dist_rect((x1 + x2) / 2, (y1 + y2) / 2, (x2 - x1) / 2, (y2 - y1) / 2, sl) < e
        x1, y1, x2, y2 = self.keepout
        r = radius + MARGIN
        sl = self._region(x1 - r, y1 - r, x2 + r, y2 + r)
        m[:, sl[0], sl[1]] |= self._dist_rect((x1 + x2) / 2, (y1 + y2) / 2, (x2 - x1) / 2, (y2 - y1) / 2, sl) < r
        # Befestigungslöcher
        for p in self.pads:
            if p["cls"] == "Hole":
                r = radius + 1.6 + (3.5 if cls == "Netz" else 0.5) + MARGIN   # Schraubenkopf/Gehäuse
                sl = self._region(p["x"] - r, p["y"] - r, p["x"] + r, p["y"] + r)
                m[:, sl[0], sl[1]] |= np.hypot(self.X[sl] - p["x"], self.Y[sl] - p["y"]) < r
        # Kupfer anderer Netze
        for kind, g, onet, ocls, layers, hw in self.copper:
            if onet == net and onet:
                continue
            r = radius + clearance(cls, ocls) + hw + MARGIN
            if kind == "rect":
                cx, cy, hx, hy = g
                sl = self._region(cx - hx - r, cy - hy - r, cx + hx + r, cy + hy + r)
                d = self._dist_rect(cx, cy, hx, hy, sl)
            else:
                ax, ay, bx, by = g
                sl = self._region(min(ax, bx) - r, min(ay, by) - r, max(ax, bx) + r, max(ay, by) + r)
                d = self._dist_seg(ax, ay, bx, by, sl)
            hit = d < r
            for l in layers:
                m[l, sl[0], sl[1]] |= hit
        return m

    # ---------------- Suche ----------------

    def cell(self, x, y):
        return int(round(y / G)), int(round(x / G))

    def astar(self, starts, targets, mask, viamask, cls, hpts, pref):
        """Suche mit Richtungsgedächtnis: Abknicken kostet extra (45° wenig,
        90° mehr), die bevorzugte Lage 'pref' ist billiger. Zustand =
        (Lage, Zeile, Spalte, Richtung). Liefert Liste von Zellen (l, iy, ix)."""
        def h(iy, ix):
            return min(math.hypot(py - iy, px - ix) for py, px in hpts) * 0.999
        dirs = [(-1, 0), (-1, 1), (0, 1), (1, 1), (1, 0), (1, -1), (0, -1), (-1, -1)]
        turn = {0: 0.0, 1: 0.6, 2: 2.5, 3: 8.0, 4: 50.0}
        openq, came, cost = [], {}, {}
        for l, iy, ix in starts:
            s = (l, iy, ix, 8)
            cost[s] = 0.0
            heapq.heappush(openq, (h(iy, ix), 0.0, s))
        done = set()
        while openq:
            _, c, cur = heapq.heappop(openq)
            if cur in done:
                continue
            done.add(cur)
            l, iy, ix, d = cur
            if (l, iy, ix) in targets:
                path = [cur]
                while path[-1] in came:
                    path.append(came[path[-1]])
                return [(s[0], s[1], s[2]) for s in path[::-1]]
            layer_f = 1.0 if (pref is None or l == pref) else 1.6
            for nd, (dy, dx) in enumerate(dirs):
                ny, nx = iy + dy, ix + dx
                if not (0 <= ny < self.ny and 0 <= nx < self.nx) or mask[l, ny, nx]:
                    continue
                if dy and dx and (mask[l, iy + dy, ix] or mask[l, iy, ix + dx]):
                    continue
                w = (1.4142 if dy and dx else 1.0) * layer_f
                if d != 8:
                    k = abs(nd - d) % 8
                    w += turn[min(k, 8 - k)]
                nxt = (l, ny, nx, nd)
                nc = c + w
                if nc < cost.get(nxt, 1e18):
                    cost[nxt] = nc
                    came[nxt] = cur
                    heapq.heappush(openq, (nc + h(ny, nx), nc, nxt))
            if not viamask[0, iy, ix] and not viamask[1, iy, ix]:
                nxt = (1 - l, iy, ix, 8)
                nc = c + VIA_COST[cls]
                if nc < cost.get(nxt, 1e18):
                    cost[nxt] = nc
                    came[nxt] = cur
                    heapq.heappush(openq, (nc + h(iy, ix), nc, nxt))
        return None

    # ---------------- Netz verlegen ----------------

    def route_net(self, net):
        pads = [p for p in self.pads if p["net"] == net]
        if len(pads) < 2:
            return
        cls = pads[0]["cls"]
        width = WIDTH[cls] if net not in SELV_POWER else 0.8
        radius = width / 2
        mask = self.blocked(net, cls, radius)
        viamask = self.blocked(net, cls, max(radius, VIA_D[cls] / 2))

        def pad_cells(p):
            iy, ix = self.cell(p["x"], p["y"])
            ls = (0, 1) if p["tht"] else (0,)
            out = set()
            for l in ls:
                mask[l, iy, ix] = False
                out.add((l, iy, ix))
            return out

        # Reihenfolge: Prim-artig, immer das nächstgelegene Pad anschließen
        tree_pads = [pads[0]]
        tree = pad_cells(pads[0])
        rest = pads[1:]
        while rest:
            rest.sort(key=lambda p: min(math.hypot(p["x"] - q["x"], p["y"] - q["y"]) for q in tree_pads))
            p = rest.pop(0)
            starts = pad_cells(p)
            hpts = [self.cell(q["x"], q["y"]) for q in tree_pads]
            path = self.astar(starts, tree, mask, viamask, cls, hpts, PREF_LAYER.get(net))
            if path is None:
                self.failed.append(f"{net}: {p['ref']}.{p['num']}")
                continue
            self.emit(net, cls, width, path, p, tree_pads)
            tree |= set(path)
            tree |= starts
            tree_pads.append(p)

    def emit(self, net, cls, width, path, start_pad, tree_pads):
        # Pfad -> Punkte je Lage, Vias an Lagenwechseln
        pts = [(l, ix * G, iy * G) for l, iy, ix in path]
        # exakter Anschluss an die Padmitte
        pts[0] = (pts[0][0], start_pad["x"], start_pad["y"])
        end = pts[-1]
        for q in tree_pads:
            if abs(q["x"] - end[1]) < G and abs(q["y"] - end[2]) < G:
                pts[-1] = (end[0], q["x"], q["y"])
        segs = []
        for (l1, x1, y1), (l2, x2, y2) in zip(pts, pts[1:]):
            if l1 != l2:
                self.vias.append({"p": [x1, y1], "net": net, "cls": cls})
                self.copper.append(("rect", (x1, y1, VIA_D[cls] / 2, VIA_D[cls] / 2), net, cls, (0, 1), 0.0))
                continue
            segs.append((l1, x1, y1, x2, y2))
        # gerade Stücke zusammenfassen
        merged = []
        for s in segs:
            if merged:
                l, ax, ay, bx, by = merged[-1]
                _, cx, cy, dx, dy = s
                if l == s[0] and (bx, by) == (cx, cy):
                    v1 = (bx - ax, by - ay)
                    v2 = (dx - cx, dy - cy)
                    if abs(v1[0] * v2[1] - v1[1] * v2[0]) < 1e-9 and v1[0] * v2[0] + v1[1] * v2[1] > 0:
                        merged[-1] = (l, ax, ay, dx, dy)
                        continue
            merged.append(s)
        for l, ax, ay, bx, by in merged:
            if (ax, ay) == (bx, by):
                continue
            self.tracks.append({"a": [round(ax, 4), round(ay, 4)], "b": [round(bx, 4), round(by, 4)],
                                "w": width, "layer": l, "net": net})
            self.copper.append(("seg", (ax, ay, bx, by), net, cls, (l,), width / 2))


def main():
    data = json.loads((PDIR / "routing_pads.json").read_text())
    r = Router(data)
    nets = sorted({p["net"] for p in r.pads if p["net"] and not p["net"].startswith("unconnected")})
    order = [n for n in ORDER if n in nets] + [n for n in nets if n not in ORDER]
    for net in order:
        print(f"  verlege {net} ...", flush=True)
        r.route_net(net)
    (PDIR / "routing_result.json").write_text(json.dumps(
        {"nets": order, "tracks": r.tracks, "vias": r.vias, "failed": r.failed}, indent=1))
    print(f"{len(r.tracks)} Segmente, {len(r.vias)} Vias")
    if r.failed:
        print("NICHT verlegt:", *r.failed, sep="\n  ")
        sys.exit(1)


if __name__ == "__main__":
    main()
