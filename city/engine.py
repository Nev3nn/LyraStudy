"""Estado e regras da cidade (sem interface). Os dados ficam em data["city"] (data.json do Lyra Study).
Os métodos devolvem EVENTOS para a interface animar: ("toast", texto) • ("pop", índice_do_dia) • ("merge", (x, y, w, h), texto)."""
import copy, random
from datetime import date
from . import catalog as C, layout as LY
from rules import goal_min, studied

DEFAULT = {"D": 0, "t": [], "ob": ["casa", "bib"], "oc": ["car_a", "car_b"], "plaza": "auto", "unl": {}, "sel": -1, "focus": -1,
           "view": "sem", "auto": True, "rand": False, "model": "casa", "counted": [], "seed": 0}

class City:
    def __init__(self, data):
        self.d = data; s = data.setdefault("city", {})
        for k, v in DEFAULT.items(): s.setdefault(k, copy.deepcopy(v))
        if not s["seed"]: s["seed"] = random.randrange(1, 10 ** 9)
        self.s, self.rev, self.rng, self._g = s, 0, random.Random(), None

    # ---------- ano corrente ----------
    @property
    def D(self): return self.s["D"]
    def ys(self): return ((self.D - 1) // C.PER) * C.PER if self.D else 0
    def jn(self): return self.D - self.ys()
    def year(self): return self.ys() // C.PER
    def touch(self): self.rev += 1; self._g = None
    def tile(self, i): return self.s["t"][i] if 0 <= i < len(self.s["t"]) else None
    def pos(self, j): return LY.day_cell(self.s["seed"], self.year(), j)

    def geom(self):
        """Células desenvolvidas e plataformas fundidas (cacheado por revisão)."""
        if self._g: return self._g
        sd, y, jn, days, dev, spare, plats = self.s["seed"], self.year(), self.jn(), [], set(), [], []
        for j in range(jn):
            x, yy = self.pos(j); days.append({"j": j, "i": self.ys() + j, "x": x, "y": yy}); dev.add((x, yy))
        for W in range((jn + 6) // 7):                                   # semana iniciada => 2 praças aparecem
            for p in LY.spare_cells(sd, y, W // 4, W % 4): spare.append(p); dev.add(p)
        for W in range(jn // 7):
            if W // 4 >= jn // 28: gx, gy = LY.week_origin(sd, y, W // 4, W % 4); plats.append((gx, gy, 3, 3, 0))
        for m in range(jn // 28): gx, gy = LY.month_origin(sd, y, m); plats.append((gx, gy, 6, 6, 1))
        if jn == C.PER: plats.append((0, 0, LY.YEAR_W, LY.YEAR_H, 2))
        self._g = {"days": days, "dev": dev, "spare": spare, "plats": plats, "jn": jn}; return self._g

    def region(self):
        """Retângulo (x0, y0, x1, y1) mostrado em cada visão. O Ano é só a grade compacta 4x3 de blocões."""
        v, jn, s = self.s["view"], self.jn(), self.s
        if v == "ano" or not jn: return (0, 0, LY.YEAR_W, LY.YEAR_H)
        if v == "dia":
            i = s["focus"] if self.ys() <= s["focus"] < self.D else self.D - 1; x, y = self.pos(i - self.ys()); return (x, y, x + 1, y + 1)
        j = jn - 1; m, w = j // 28, (j % 28) // 7
        if v == "sem": gx, gy = LY.week_origin(s["seed"], self.year(), m, w); return (gx, gy, gx + 3, gy + 3)
        gx, gy = LY.month_origin(s["seed"], self.year(), m); return (gx, gy, gx + 6, gy + 6)

    def plats_for(self, G, R):
        """Plataformas fundidas visíveis na visão atual."""
        v, jn = self.s["view"], G["jn"]
        if v == "ano" or not jn: return G["plats"]
        if v == "dia": return []
        j = jn - 1
        if v == "sem": return [(R[0], R[1], 3, 3, 0)] if jn // 7 > j // 7 else []
        if jn // 28 > j // 28: return [(R[0], R[1], 6, 6, 1)]
        return [p for p in G["plats"] if p[4] == 0 and R[0] <= p[0] < R[2] and R[1] <= p[1] < R[3]]

    # ---------- plazas ----------
    def total_min(self): return sum(v.get("total", 0) for v in self.d["sessions"].values())
    def unlocked(self, p): return self.D >= p["d"] and self.total_min() >= p["h"] * 60
    def styles(self): return [p["id"] for p in C.PLZ if self.s["unl"].get(p["id"])]
    def plaza_style(self, x, y):
        st = self.styles()
        if not st: return None
        if self.s["plaza"] in st: return self.s["plaza"]
        return st[(x * 7 + y * 13) % len(st)]                            # "auto": mistura aleatória das desbloqueadas
    def check_plazas(self):
        ev = []
        for p in C.PLZ:
            if self.unlocked(p) and not self.s["unl"].get(p["id"]): self.s["unl"][p["id"]] = 1; ev.append(("toast", f"🌳 {p['n']} desbloqueada!"))
        return ev

    # ---------- dias e fusões ----------
    def pick_building(self):
        """Prédio de um novo dia: aleatório entre os desbloqueados (opção 'rand') ou o modelo fixo escolhido."""
        s = self.s
        if not s["auto"] or not s["ob"]: return None
        if s["rand"]: return self.rng.choice(s["ob"])
        return s["model"] if s["model"] in s["ob"] else s["ob"][0]

    def add_day(self, quiet=False):
        s, ev, i, b = self.s, [], self.D, self.pick_building()
        s["t"].append({"b": b, "lv": 1 if b else 0, "xp": 0}); s["D"] += 1; s["sel"] = i
        jn, y, sd = self.jn(), self.year(), s["seed"]
        if jn % C.PER == 0: ev.append(("merge", (0, 0, LY.YEAR_W, LY.YEAR_H), "🏙 Quadrado do Ano! Os 12 blocões estão completos"))
        elif jn % 28 == 0: gx, gy = LY.month_origin(sd, y, jn // 28 - 1); ev.append(("merge", (gx, gy, 6, 6), "🌆 4 semanas fundidas: Quadrado do Mês!"))
        elif jn % 7 == 0: j0 = jn - 7; gx, gy = LY.week_origin(sd, y, j0 // 28, (j0 % 28) // 7); ev.append(("merge", (gx, gy, 3, 3), "🏙 7 dias fundidos: Quadrado da Semana!"))
        else: ev.append(("toast", f"🧱 Novo dia: {C.bld(b)['n']} construído" if b else "🧱 Dia concluído: nova fundação"))
        self.next_focus(); ev += self.check_plazas() + [("pop", i)]; self.touch()
        return [] if quiet else ev

    def next_focus(self):
        """O prédio em foco continua em uso entre os dias; ao atingir o nível máximo, passa ao próximo que ainda evolui."""
        s, ys = self.s, self.ys(); cur = self.tile(s["focus"])
        if cur and cur["b"] and s["focus"] >= ys and cur["lv"] < C.bld(cur["b"])["max"]: return
        for i in range(self.D - 1, ys - 1, -1):
            t = self.tile(i)
            if t and t["b"] and t["lv"] < C.bld(t["b"])["max"]: s["focus"] = i; return

    def candidates(self):
        """Prédios dos últimos 7 dias (o 'quadrado ativo') que podem receber XP."""
        return [i for i in range(self.D - 1, max(self.ys(), self.D - 7) - 1, -1) if (self.tile(i) or {}).get("b")]

    # ---------- estudo ----------
    def study(self, minutes=1, today=None):
        s, ev, t = self.s, [], self.tile(self.s["focus"])
        if t and t["b"]:
            b = C.bld(t["b"])
            if t["lv"] < b["max"]:
                t["xp"] += minutes * C.XP_PER_MIN
                while t["lv"] < b["max"] and t["xp"] >= 100 * t["lv"]:
                    t["xp"] -= 100 * t["lv"]; t["lv"] += 1
                    ev += [("pop", s["focus"]), ("toast", f"⬆ {b['n']} evoluiu para o nível {t['lv']}!")]
                if t["lv"] >= b["max"]:
                    t["xp"] = 0; ev.append(("toast", f"🏆 {b['n']} no nível máximo — foco passa ao próximo prédio")); self.next_focus()
        ev += self.check_plazas() + self.check_day(today or date.today()); self.touch(); return ev

    def check_day(self, today):
        """Dia concluído = meta diária do Lyra Study batida (uma vez por data)."""
        g, iso = goal_min(self.d), today.isoformat()
        if g > 0 and iso not in self.s["counted"] and studied(self.d, today) >= g:
            self.s["counted"].append(iso); return self.add_day()
        return []

    def sync_days(self):
        """Ao abrir o app: dias passados em que a meta foi batida viram quadrados (sem animações)."""
        g = goal_min(self.d)
        for iso in sorted(self.d["sessions"]):
            if g > 0 and iso not in self.s["counted"] and self.d["sessions"][iso].get("total", 0) >= g:
                self.s["counted"].append(iso); self.add_day(quiet=True)

    # ---------- ações do usuário ----------
    def build(self, i, bid=None):
        """Constrói na fundação livre i. bid=None => prédio aleatório entre os desbloqueados."""
        t, s = self.tile(i), self.s
        if not t or t["b"] or not s["ob"]: return []
        bid = bid or self.rng.choice(s["ob"]); t["b"], t["lv"], t["xp"] = bid, 1, 0
        t2 = self.tile(s["focus"])
        if not t2 or not t2["b"]: s["focus"] = i
        self.touch(); return [("pop", i), ("toast", f"🏗 {C.bld(bid)['n']} construído")]

    def buy(self, kind, iid):
        """Compra com os pontos do Lyra Study. Retorna (ok, eventos)."""
        it = (C.bld if kind == "b" else C.car)(iid); own = self.s["ob" if kind == "b" else "oc"]
        if iid in own or self.d["points"] < it["p"]: return False, []
        self.d["points"] -= it["p"]; own.append(iid); self.touch(); return True, [("toast", f"🛒 {it['n']} adquirido!")]

    def dev_level_up(self):
        t = self.tile(self.s["focus"])
        if t and t["b"] and t["lv"] < C.bld(t["b"])["max"]: t["lv"] += 1; t["xp"] = 0; self.touch(); return [("pop", self.s["focus"])]
        return []
