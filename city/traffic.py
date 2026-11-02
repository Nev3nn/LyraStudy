"""Carros: andam pelas ruas (linhas entre os lotes) em mão única — a arte só tem a vista frontal (↙ e ↘ espelhado)."""
import random
from . import catalog as C

DIRS = ((1, 0), (0, 1))

class Traffic:
    def __init__(self): self.cars, self.dev, self.nodes, self.R = [], set(), [], (0, 0, 0, 0)

    def _in(self, x, y): return self.R[0] <= x <= self.R[2] and self.R[1] <= y <= self.R[3]

    def _ok(self, x, y, dx, dy):  # a aresta precisa encostar numa célula desenvolvida
        cells = [(min(x, x + dx), y - 1), (min(x, x + dx), y)] if dx else [(x - 1, min(y, y + dy)), (x, min(y, y + dy))]
        return any(c in self.dev for c in cells)

    def _pick(self, c):
        o = [(a, b) for a, b in DIRS if self._ok(c["x"], c["y"], a, b) and self._in(c["x"] + a, c["y"] + b)]
        if not o: return False
        c["dx"], c["dy"] = random.choice(o); return True

    def _spawn(self, m, now):
        for _ in range(40):
            if not self.nodes: return None
            n = random.choice(self.nodes); c = {"m": m, "x": n[0], "y": n[1], "dx": 1, "dy": 0, "t": random.random(), "born": now}
            if self._pick(c): return c
        return None

    def sync(self, city, now=0.0):
        G = city.geom(); self.dev, self.R = G["dev"], city.region(); self.nodes = []
        owned = city.s["oc"]
        if city.s["view"] == "dia" or not self.dev or not owned: self.cars = []; return
        for (x, y) in self.dev:
            for a, b in ((0, 0), (1, 0), (0, 1), (1, 1)):
                if self._in(x + a, y + b): self.nodes.append((x + a, y + b))
        area = (self.R[2] - self.R[0]) * (self.R[3] - self.R[1])      # região pequena (semana) = menos carros
        total = max(1, min(round(len(owned) * min(4, 1 + len(self.dev) // 8) * C.TRAFFIC), area // 5))
        self.cars = [c for c in self.cars if c["m"] in owned and self._in(c["x"], c["y"])][:total]
        while len(self.cars) < total:
            c = self._spawn(owned[len(self.cars) % len(owned)], now)
            if not c: break
            self.cars.append(c)

    def step(self, dt, now):
        for k in self.cars:
            k["t"] += dt * .9
            while k["t"] >= 1:
                k["t"] -= 1; k["x"] += k["dx"]; k["y"] += k["dy"]
                if not self._pick(k):
                    n = self._spawn(k["m"], now)
                    if n: k.update(n)
                    else: k["t"] = 0; break
