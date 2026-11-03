"""Desenho isométrico com Pillow. Tudo (lotes, prédios, praças e carros) entra na MESMA ordenação por profundidade,
então um carro que passa atrás de um prédio fica escondido por ele. A camada estática (sem carros) é cacheada; a cada
quadro só os carros são colados e os "oclusores" (prédios na frente deles) são colados de novo por cima."""
import math
from PIL import Image, ImageDraw, ImageFont
from . import catalog as C

BG, SLAB, LOTC, SPARE = (10, 13, 26), (15, 19, 38), (28, 35, 56), (22, 40, 34)
GRID, GRID6 = (22, 27, 54), (42, 51, 88)
PLAT = [((25, 35, 69), (53, 224, 255)), ((31, 42, 90), (124, 108, 240)), ((42, 42, 78), (242, 184, 75))]
GOLD, CYAN, TEAL = (242, 184, 75), (53, 224, 255), (63, 184, 165)
clamp = lambda v: max(0.0, min(1.0, v))
def back(t): c = 1.9; return 1 + (c + 1) * (t - 1) ** 3 + c * (t - 1) ** 2
def sh(c, f): return tuple(min(255, int(v * f)) for v in c)
def mix(a, b, t): return tuple(int(a[i] * t + b[i] * (1 - t)) for i in range(3))

class FX:
    """Animações em andamento (tempo em segundos): fusões (merge) e 'pops' de construção/evolução."""
    def __init__(self): self.anims, self.pops = [], {}
    def merge(self, rect, now, dur=1.7): self.anims.append({"rect": tuple(rect), "t0": now, "dur": dur})
    def pop(self, i, now): self.pops[i] = now
    def prune(self, now):
        self.anims = [a for a in self.anims if now - a["t0"] < a["dur"]]; self.pops = {i: t for i, t in self.pops.items() if now - t < .5}
    def active(self): return bool(self.anims or self.pops)

class Camera:
    """Câmera FIXA: enquadra a região inteira, centralizada, uma única vez por visão/tamanho do canvas. Sem pan, sem zoom, sem easing."""
    def __init__(self): self.k, self.ox, self.oy = 20., 0., 0.
    def P(self, x, y, z=0.): return (self.ox + (x - y) * self.k, self.oy + (x + y) * self.k / 2 - z * self.k)
    def fit(self, R, W, H, tall):
        xr = (R[2] - R[0]) + (R[3] - R[1]); self.k = max(6., min(150., W * .94 / xr, H * .92 / (xr / 2 + tall)))
        self.ox = W / 2 - ((R[0] - R[3]) + (R[2] - R[1])) / 2 * self.k; self.oy = H / 2 - ((R[0] + R[1] + R[2] + R[3]) / 4 - tall / 2) * self.k

class Renderer:
    def __init__(self):
        self.meta, self._src, self._sc, self._key, self._base, self._occ, self.tops = C.meta(), {}, {}, None, None, [], {}
        try: self.font = ImageFont.load_default(size=11)
        except TypeError: self.font = ImageFont.load_default()

    # ---- sprites ----
    def sprite(self, key):
        if key not in self._src: self._src[key] = Image.open(C.sprite_path(key)).convert("RGBA")
        return self._src[key]
    def scaled(self, key, w, h, flip=False):
        kk = (key, w, h, flip)
        if kk not in self._sc:
            if len(self._sc) > 900: self._sc = {k_: v for k_, v in self._sc.items() if k_[0] == "thumb"}   # limite de memória (a câmera fixa gera poucos tamanhos)
            im = self.sprite(key).resize((max(1, w), max(1, h)), Image.BILINEAR); self._sc[kk] = im.transpose(Image.FLIP_LEFT_RIGHT) if flip else im
        return self._sc[kk]
    def thumb(self, key, height):
        kk = ("thumb", key, height)
        if kk not in self._sc: im = self.sprite(key); self._sc[kk] = im.resize((max(1, int(im.width * height / im.height)), height), Image.LANCZOS)
        return self._sc[kk]
    @staticmethod
    def car_step(v): return max(.2, round(v * 5) / 5)                       # entrada do carro em 5 passos => poucos tamanhos
    def car_size(self, model, cam, step):
        m = self.meta["cars/" + model]; s = cam.k * .8 / m["w"] * step; return int(m["w"] * s) + 1, int(m["h"] * s) + 1
    def prewarm(self, city, cam):
        """Gera de antemão todas as versões redimensionadas dos carros (5 passos x 2 sentidos) — o laço de desenho só LÊ o cache."""
        for model in city.s["oc"]:
            for step in (.2, .4, .6, .8, 1.0):
                w, h = self.car_size(model, cam, step)
                for flip in (False, True): self.scaled("cars/" + model, w, h, flip)
    def tall(self, city, R):
        """Margem superior (em células) para caber o prédio mais alto da região."""
        M = 1.0
        for dd in city.geom()["days"]:
            t = city.tile(dd["i"])
            if R[0] <= dd["x"] < R[2] and R[1] <= dd["y"] < R[3] and t and t["b"]:
                m = self.meta.get(C.building_key(t["b"], t["lv"]) or "")
                if m: M = max(M, m["h"] / m["bw"] * 2 * C.LOT * C.BLD_FILL + .4)
        return M

    # ---- primitivas ----
    @staticmethod
    def _box(d, P, x0, y0, x1, y1, z0, z1, c):
        d.polygon([P(x1, y0, z0), P(x1, y1, z0), P(x1, y1, z1), P(x1, y0, z1)], fill=sh(c, .8)); d.polygon([P(x0, y1, z0), P(x1, y1, z0), P(x1, y1, z1), P(x0, y1, z1)], fill=sh(c, .6))
        d.polygon([P(x0, y0, z1), P(x1, y0, z1), P(x1, y1, z1), P(x0, y1, z1)], fill=sh(c, 1.15))
    def _plat(self, d, P, rect, s, glow):
        gx, gy, w, h, kd = rect; cx, cy, ww, hh = gx + w / 2, gy + h / 2, w * s, h * s; x0, y0 = cx - ww / 2, cy - hh / 2; z = (.05, .1, .16)[kd] * s; base, gl = PLAT[kd]
        self._box(d, P, x0, y0, x0 + ww, y0 + hh, 0, z, base)
        d.line([P(x0, y0, z), P(x0 + ww, y0, z), P(x0 + ww, y0 + hh, z), P(x0, y0 + hh, z), P(x0, y0, z)], fill=mix(gl, base, .6 + .4 * glow), width=1 + kd + int(glow * 3))
        xs, ys = ([x0 + ww / 2], [y0 + hh / 2]) if kd < 2 else ([x0 + ww * f / 4 for f in (1, 2, 3)], [y0 + hh * f / 3 for f in (1, 2)])
        for xv in xs: d.line([P(xv, y0, z), P(xv, y0 + hh, z)], fill=mix(gl, base, .35), width=1 + kd)
        for yv in ys: d.line([P(x0, yv, z), P(x0 + ww, yv, z)], fill=mix(gl, base, .35), width=1 + kd)

    # ---- camada estática (tudo menos carros) ----
    def _static(self, city, cam, W, H, t, fx):
        img = Image.new("RGB", (W, H), BG); d = ImageDraw.Draw(img); P, k, S = cam.P, cam.k, city.s
        R = city.region(); G = city.geom(); plats = city.plats_for(G, R); x0, y0, x1, y1 = R; occ, objs, self.tops = [], [], {}; M = C.STREET / 2
        glow_year = city.jn() == C.PER
        d.polygon([P(x0, y0), P(x1, y0), P(x1, y1), P(x0, y1)], fill=SLAB)
        d.polygon([P(x1, y0), P(x1, y1), P(x1, y1, -.5), P(x1, y0, -.5)], fill=sh(SLAB, .5)); d.polygon([P(x0, y1), P(x1, y1), P(x1, y1, -.5), P(x0, y1, -.5)], fill=sh(SLAB, .7))
        if k >= 7:
            for i in range(x0, x1 + 1): d.line([P(i, y0), P(i, y1)], fill=GRID6 if i % 6 == 0 else GRID)
            for i in range(y0, y1 + 1): d.line([P(x0, i), P(x1, i)], fill=GRID6 if i % 6 == 0 else GRID)
        cov = {}
        for rect in plats:
            gx, gy, w, h, kd = rect
            for xx in range(w):
                for yy in range(h): cov[(gx + xx, gy + yy)] = max(kd, cov.get((gx + xx, gy + yy), -1))
            a = next((a for a in fx.anims if a["rect"] == (gx, gy, w, h)), None); p = (t - a["t0"]) / a["dur"] if a else None
            self._plat(d, P, rect, 1 if p is None else max(.01, back(clamp((p - .35) / .65))), (.5 + .5 * math.sin(t * 2.5)) if (p is None and kd == 2) else (0 if p is None else math.sin(math.pi * p)))
        zof = lambda key: (.02, .05, .1, .16)[cov.get(key, -1) + 1]

        def lamp(x, y, z):
            d.line([P(x, y, z), P(x, y, z + .16)], fill=(89, 96, 127)); q = P(x, y, z + .17); r = max(1.2, k * .05)
            d.ellipse([q[0] - r, q[1] - r, q[0] + r, q[1] + r], fill=(255, 240, 176) if glow_year else (255, 210, 122))
        def lot(x, y, z, col): self._box(d, lambda a, b, e=0: P(a, b, e + z), x + M, y + M, x + 1 - M, y + 1 - M, 0, .02, col)

        for dd in G["days"]:
            x, y, i = dd["x"], dd["y"], dd["i"]
            if not (x0 <= x < x1 and y0 <= y < y1): continue
            dx = dy = 0.0; sc = 1.0
            for a in fx.anims:                                           # fusão: os quadrados convergem para o centro do grupo e voltam
                p = (t - a["t0"]) / a["dur"]; gx, gy, w, h = a["rect"]
                if 0 <= p <= 1 and gx <= x < gx + w and gy <= y < gy + h:
                    kk = math.sin(math.pi * p) * .85; dx += (gx + w / 2 - .5 - x) * kk; dy += (gy + h / 2 - .5 - y) * kk; sc -= .3 * kk
            z, T = zof((x, y)), city.tile(i); cx, cy = x + dx, y + dy
            def cell(cx=cx, cy=cy, z=z, T=T, i=i, sc=sc):
                lot(cx, cy, z, LOTC); lamp(cx + M - .02, cy + 1 - M + .02, z); lamp(cx + 1 - M + .02, cy + M - .02, z)
                if not (T and T["b"]):
                    pts = [P(cx + .3, cy + .3, z + .03), P(cx + .7, cy + .3, z + .03), P(cx + .7, cy + .7, z + .03), P(cx + .3, cy + .7, z + .03), P(cx + .3, cy + .3, z + .03)]
                    d.line(pts, fill=mix(CYAN, LOTC, .35 + .2 * math.sin(t * 3)), width=2); return
                key = C.building_key(T["b"], T["lv"])                    # sprite SEGUE o nível atual (casa_1 → casa_2 → casa_3)
                if key is None: return
                m = self.meta[key]; pp = fx.pops.get(i); ps = back(clamp((t - pp) / .5)) if pp is not None else 1.0
                q = max(.05, round(sc * ps * 20) / 20)                   # escala quantizada em passos de 5%: os tamanhos animados também caem no cache
                s = 2 * k * C.LOT * C.BLD_FILL / m["bw"] * q; w, h = int(m["w"] * s) + 1, int(m["h"] * s) + 1; spr = self.scaled(key, w, h)
                sx, sy = P(cx + .5, cy + .5, z + .02); px, py = int(sx - m["ax"] * m["w"] * s), int(sy + m["bw"] * s / 4 - m["h"] * s)
                img.paste(spr, (px, py), spr); occ.append((cx + cy + 1, (px, py, px + w, py + h), spr)); self.tops[i] = (sx, py)
            objs.append((x + dx + y + dy + 1, cell))
        for (x, y) in G["spare"]:
            if not (x0 <= x < x1 and y0 <= y < y1): continue
            z, st = zof((x, y)), city.plaza_style(x, y)
            def pz(x=x, y=y, z=z, st=st):
                lot(x, y, z, SPARE if st else LOTC)
                if not st: return
                key = f"plazas/{st}"; m = self.meta[key]; s = 2 * k * (C.LOT + .12) / m["w"]; w, h = int(m["w"] * s) + 1, int(m["h"] * s) + 1; spr = self.scaled(key, w, h)
                sx, sy = P(x + .5, y + .5, z + .02); px, py = int(sx - w / 2), int(sy - h * .58); img.paste(spr, (px, py), spr); occ.append((x + y + 1, (px, py, px + w, py + h), spr))
            objs.append((x + y + 1, pz))
        for _, f in sorted(objs, key=lambda o: o[0]): f()
        for a in fx.anims:                                               # anel dourado da fusão
            p = (t - a["t0"]) / a["dur"]; gx, gy, w, h = a["rect"]
            if .3 < p < 1:
                q = P(gx + w / 2, gy + h / 2, .2); r = (1 - (1 - (p - .3) / .7) ** 3) * max(w, h) * k * 1.2
                d.ellipse([q[0] - r, q[1] - r / 2, q[0] + r, q[1] + r / 2], outline=mix(GOLD, BG, 1 - (p - .3) / .7), width=3)
        return img, occ

    # ---- quadro final ----
    def render(self, city, cam, W, H, t, fx, cars, running=False):
        key = (city.rev, city.s["view"], round(cam.k, 2), round(cam.ox), round(cam.oy), W, H)
        if fx.active() or key != self._key: self._base, self._occ = self._static(city, cam, W, H, t, fx); self._key = key if not fx.active() else None
        img = self._base.copy(); occ = self._occ; P = cam.P; meta = self.meta
        R = city.region()
        for c in sorted(cars, key=lambda c: c["x"] + c["dx"] * c["t"] + c["y"] + c["dy"] * c["t"]):
            x, y = c["x"] + c["dx"] * c["t"], c["y"] + c["dy"] * c["t"]
            if not (R[0] <= x <= R[2] and R[1] <= y <= R[3]): continue
            key_ = "cars/" + c["m"]; w, h = self.car_size(c["m"], cam, self.car_step(back(clamp((t - c["born"]) / .5))))   # entrada do carro usa tamanhos pré-aquecidos
            spr = self.scaled(key_, w, h, bool(c["dx"])); sx, sy = P(x + (.14 if c["dx"] else 0) + (-.14 if c["dy"] else 0), y + (.14 if c["dx"] else 0) , 0)
            px, py = int(sx - w / 2), int(sy - h * .8); img.paste(spr, (px, py), spr); dep = x + y
            for od, (l, tp, r, b), osp in occ:                           # oclusão: prédios/praças À FRENTE do carro são colados de novo por cima
                if od > dep + .02 and l < px + w and r > px and tp < py + h and b > py: img.paste(osp, (l, tp), osp)
        self._overlay(img, city, cam, t, running); return img

    def _overlay(self, img, city, cam, t, running):
        d = ImageDraw.Draw(img); P, S = cam.P, city.s; R = city.region(); pulse = .6 + .4 * math.sin(t * 4)
        def tile_xy(i):
            if not (city.ys() <= i < city.D): return None
            x, y = city.pos(i - city.ys()); return (x, y) if R[0] <= x < R[2] and R[1] <= y < R[3] else None
        sel = tile_xy(S["sel"])
        if sel:
            x, y = sel; d.line([P(x + .1, y + .1, .04), P(x + .9, y + .1, .04), P(x + .9, y + .9, .04), P(x + .1, y + .9, .04), P(x + .1, y + .1, .04)], fill=mix(GOLD, BG, pulse), width=2)
        for i, col in ((S["sel"], GOLD), (S["focus"], CYAN)):
            T = city.tile(i)
            if tile_xy(i) and T and T["b"] and i in self.tops:
                sx, top = self.tops[i]; b = C.bld(T["b"]); label = f"Nv {T['lv']}/{b['max']}"
                tw = d.textlength(label, font=self.font); d.rounded_rectangle([sx - tw / 2 - 4, top - 18, sx + tw / 2 + 4, top - 4], radius=4, fill=(19, 25, 51), outline=col)
                d.text((sx - tw / 2, top - 17), label, fill=col, font=self.font)
                if i == S["focus"] and T["lv"] < b["max"]:           # barra de XP do prédio em foco
                    d.rectangle([sx - 22, top - 24, sx + 22, top - 20], fill=(42, 51, 88)); d.rectangle([sx - 22, top - 24, sx - 22 + 44 * T["xp"] / (100 * T["lv"]), top - 20], fill=TEAL)
                    if running: d.ellipse([sx - 3, top - 34, sx + 3, top - 28], fill=mix(CYAN, BG, pulse))
