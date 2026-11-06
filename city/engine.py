"""Estado e regras da cidade (sem interface). Os dados ficam em data["city"] (data.json do Lyra Study).
Os métodos devolvem EVENTOS para a interface animar: ("toast", texto) • ("pop", índice_do_dia) • ("merge", (x, y, w, h), texto)."""
import copy, random
from datetime import date
import clock
from . import catalog as C, layout as LY
from rules import goal_min, studied

DEFAULT = {"D": 0, "t": [], "ob": [], "oc": ["car_a", "car_b"], "plaza": "auto", "pz": {}, "pend": [], "since": 0, "cycle": "", "cy": {},
           "sel": -1, "focus": -1, "view": "sem", "auto": True, "rand": False, "model": "", "counted": [], "seed": 0, "history": []}

class City:
    def __init__(self, data):
        self.d = data; s = data.setdefault("city", {})
        for k, v in DEFAULT.items(): s.setdefault(k, copy.deepcopy(v))
        if not s["seed"]: s["seed"] = random.randrange(1, 10 ** 9)
        self.s, self.rev, self.rng, self._g = s, 0, random.Random(), None
        self.sanitize()

    def sanitize(self):
        """Saves antigos (modelos removidos) continuam abrindo: ids desconhecidos viram o modelo atual; níveis ficam dentro da faixa."""
        s, ids, free = self.s, [b["id"] for b in C.BLD], [b["id"] for b in C.BLD if not b["p"]]
        s["ob"] = [i for i in s["ob"] if i in ids] or free[:]
        if s["model"] not in s["ob"]: s["model"] = s["ob"][0] if s["ob"] else ""
        for t in s["t"]:
            if not t: continue
            if t.get("b") and t["b"] not in ids: t["b"] = s["model"] or None
            t["lv"] = max(1, min(t.get("lv") or 1, C.bld(t["b"])["max"])) if t.get("b") else 0

    @classmethod
    def from_history(cls, e):
        """Reconstrói o mapa de um ano concluído (para a 'foto' do Modo Memória)."""
        st = {"D": (e["idx"] + 1) * C.PER, "t": [None] * (e["idx"] * C.PER) + [dict(t, xp=0) for t in e["tiles"]], "seed": e["seed"], "pz": e["pz"], "oc": e["oc"], "view": "ano"}
        return cls({"sessions": {}, "city": st})

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
        """Células desenvolvidas, praças e plataformas fundidas (cacheado por revisão)."""
        if self._g: return self._g
        sd, y, jn, days, dev, spare, plats = self.s["seed"], self.year(), self.jn(), [], set(), [], []
        for j in range(jn):
            x, yy = self.pos(j); days.append({"j": j, "i": self.ys() + j, "x": x, "y": yy}); dev.add((x, yy))
        for W in range((jn + 6) // 7):                                   # cada semana iniciada reserva 2 lotes para praças
            for p in LY.spare_cells(sd, y, W // 4, W % 4): spare.append(p); dev.add(p)
        for W in range(jn // 7):
            if W // 4 >= jn // 28: gx, gy = LY.week_origin(sd, y, W // 4, W % 4); plats.append((gx, gy, 3, 3, 0))
        for m in range(jn // 28): gx, gy = LY.month_origin(sd, y, m); plats.append((gx, gy, 6, 6, 1))
        if jn == C.PER: plats.append((0, 0, LY.YEAR_W, LY.YEAR_H, 2))
        self._g = {"days": days, "dev": dev, "spare": spare, "plats": plats, "jn": jn}; return self._g

    def region(self, view=None):
        """Retângulo (x0, y0, x1, y1) de cada visão. O Ano é só a grade compacta 4x3 de blocões."""
        v, jn, s = view or self.s["view"], self.jn(), self.s
        if v == "ano" or not jn: return (0, 0, LY.YEAR_W, LY.YEAR_H)
        if v == "dia":
            i = s["focus"] if self.ys() <= s["focus"] < self.D else self.D - 1; x, y = self.pos(i - self.ys()); return (x, y, x + 1, y + 1)
        j = jn - 1; m, w = j // 28, (j % 28) // 7
        if v == "sem": gx, gy = LY.week_origin(s["seed"], self.year(), m, w); return (gx, gy, gx + 3, gy + 3)
        gx, gy = LY.month_origin(s["seed"], self.year(), m); return (gx, gy, gx + 6, gy + 6)

    def plats_for(self, G, R, view=None):
        v, jn = view or self.s["view"], G["jn"]
        if v == "ano" or not jn: return G["plats"]
        if v == "dia": return []
        j = jn - 1
        if v == "sem": return [(R[0], R[1], 3, 3, 0)] if jn // 7 > j // 7 else []
        if jn // 28 > j // 28: return [(R[0], R[1], 6, 6, 1)]
        return [p for p in G["plats"] if p[4] == 0 and R[0] <= p[0] < R[2] and R[1] <= p[1] < R[3]]

    # ---------- praças: metas do ciclo mensal ----------
    def cycle_key(self, today): return f"{today.year}-{today.month:02d}"
    def cycle_hours(self): return sum(v.get("total", 0) for k, v in self.d["sessions"].items() if k.startswith(self.s["cycle"])) / 60
    def cycle_days(self): return sum(1 for k in self.s["counted"] if k.startswith(self.s["cycle"]))
    def plaza_progress(self):
        """[(praça, valor_atual, meta, concluída)] no ciclo (mês) atual."""
        return [(p, self.cycle_hours() if p["kind"] == "h" else self.cycle_days(), p["need"], bool(self.s["cy"].get(p["id"]))) for p in C.PLZ]
    def styles(self): return [p["id"] for p in C.PLZ if self.s["cy"].get(p["id"])]
    def roll_cycle(self, today):
        """Todo mês o progresso e o acesso às praças reiniciam (as praças já construídas continuam no mapa)."""
        key = self.cycle_key(today)
        if self.s["cycle"] == key: return []
        first = not self.s["cycle"]; self.s["cycle"], self.s["cy"] = key, {}
        return [] if first else [("toast", "🗓 Novo mês: as metas das praças reiniciaram")]
    def free_spare(self):
        used = set(self.s["pz"]); return [p for p in self.geom()["spare"] if f"{p[0]},{p[1]}" not in used]
    def spawn_plaza(self, style=None):
        """Coloca uma praça em um lote de sobra sorteado. Sem lote livre, a praça fica na fila (pend) até surgir espaço."""
        s, st = self.s, self.styles()
        if style is None: style = s["plaza"] if s["plaza"] in st else (self.rng.choice(st) if st else None)
        if style is None: return []
        free = self.free_spare()
        if not free: s["pend"].append(style); return []
        x, y = self.rng.choice(free); s["pz"][f"{x},{y}"] = style; self.touch(); return [("toast", f"🌳 Nova praça: {C.plz(style)['n']}")]
    def flush_pending(self):
        pend, self.s["pend"] = self.s["pend"], []
        for st in pend: self.spawn_plaza(st)
    def check_plazas(self, today):
        ev = self.roll_cycle(today)
        for p, v, need, done in self.plaza_progress():
            if v >= need and not done:
                self.s["cy"][p["id"]] = 1; ev.append(("toast", f"🌳 {p['n']} desbloqueada neste mês!")); ev += self.spawn_plaza(p["id"])
        return ev

    # ---------- dias e fusões ----------
    def pick_building(self):
        """Prédio de um novo dia: aleatório entre os desbloqueados (opção 'rand') ou o modelo fixo escolhido."""
        s = self.s
        if not s["auto"] or not s["ob"]: return None
        return self.rng.choice(s["ob"]) if s["rand"] else (s["model"] if s["model"] in s["ob"] else s["ob"][0])

    def add_day(self, quiet=False, today=None):
        today = today or clock.today(); s, ev, i, b = self.s, [], self.D, self.pick_building()
        if self.D and self.jn() == C.PER: s["pz"], s["pend"] = {}, []   # começou um ano novo: o mapa é outro
        s["t"].append({"b": b, "lv": 1 if b else 0, "xp": 0, "date": today.isoformat(), "m": int(studied(self.d, today))}); s["D"] += 1; s["sel"] = i; s["since"] += 1
        jn, y, sd = self.jn(), self.year(), s["seed"]
        if jn % C.PER == 0:
            self.snapshot(today); ev.append(("merge", (0, 0, LY.YEAR_W, LY.YEAR_H), f"🏙 Quadrado do Ano {y + 1}! Foto guardada no Modo Memória"))
        elif jn % 28 == 0: gx, gy = LY.month_origin(sd, y, jn // 28 - 1); ev.append(("merge", (gx, gy, 6, 6), "🌆 4 semanas fundidas: Quadrado do Mês!"))
        elif jn % 7 == 0: j0 = jn - 7; gx, gy = LY.week_origin(sd, y, j0 // 28, (j0 % 28) // 7); ev.append(("merge", (gx, gy, 3, 3), "🏙 7 dias fundidos: Quadrado da Semana!"))
        else: ev.append(("toast", f"🧱 Novo dia: {C.bld(b)['n']} construído" if b else "🧱 Dia concluído: nova fundação"))
        self.touch(); self.next_focus()
        if len(self.styles()) >= C.PLAZA_MIN_UNLOCKED and s["since"] >= C.PLAZA_EVERY: s["since"] = 0; ev += self.spawn_plaza()   # praça nova a cada 5 dias
        self.flush_pending(); ev.append(("pop", i)); self.touch()
        return [] if quiet else ev

    def next_focus(self):
        """O prédio em foco continua em uso entre os dias; ao atingir o nível máximo, passa ao próximo que ainda evolui."""
        s, ys = self.s, self.ys(); cur = self.tile(s["focus"])
        if cur and cur.get("b") and s["focus"] >= ys and cur["lv"] < C.bld(cur["b"])["max"]: return
        for i in range(self.D - 1, ys - 1, -1):
            t = self.tile(i)
            if t and t["b"] and t["lv"] < C.bld(t["b"])["max"]: s["focus"] = i; return

    def candidates(self):
        """Prédios dos últimos 7 dias (o 'quadrado ativo') que podem receber XP."""
        return [i for i in range(self.D - 1, max(self.ys(), self.D - 7) - 1, -1) if (self.tile(i) or {}).get("b")]

    # ---------- histórico anual (Modo Memória) ----------
    @staticmethod
    def year_stats(tiles):
        tiles = [t for t in tiles if t]; by, lv = {}, {}
        for t in tiles:
            if t.get("b"): by[t["b"]] = by.get(t["b"], 0) + 1; lv[t["lv"]] = lv.get(t["lv"], 0) + 1
        n = sum(lv.values()) or 1
        return {"days": len(tiles), "minutes": sum(t.get("m", 0) for t in tiles), "buildings": by, "levels": lv, "avg_level": round(sum(k * v for k, v in lv.items()) / n, 2)}
    def snapshot(self, today):
        """Ao fechar um ano: guarda estado visual (para renderizar a 'foto') + estatísticas."""
        s, ys = self.s, self.ys(); tiles = [{"b": t["b"], "lv": t["lv"], "m": t.get("m", 0)} for t in s["t"][ys:self.D]]
        s["history"].append({"year": self.year() + 1, "idx": self.year(), "date": today.isoformat(), "seed": s["seed"], "tiles": tiles, "pz": dict(s["pz"]),
                             "oc": list(s["oc"]), "stats": {**self.year_stats(tiles), "plazas": len(s["pz"]), "cars": len(s["oc"])}})

    # ---------- estudo ----------
    def _day_tile(self, iso):
        for i in range(self.D - 1, max(0, self.D - 4) - 1, -1):
            t = self.tile(i)
            if t and t.get("date") == iso: return t
    def study(self, minutes=1, today=None):
        """Chamado a cada minuto de foco (ou em lote pelo Admin): XP no prédio em foco + dia concluído + metas das praças."""
        today = today or clock.today(); s, ev, t = self.s, [], self.tile(self.s["focus"])
        if t and t["b"]:
            b = C.bld(t["b"])
            if t["lv"] < b["max"]:
                t["xp"] += minutes * C.XP_PER_MIN
                while t["lv"] < b["max"] and t["xp"] >= 100 * t["lv"]:
                    t["xp"] -= 100 * t["lv"]; t["lv"] += 1
                    ev += [("pop", s["focus"]), ("toast", f"⬆ {b['n']} evoluiu para o nível {t['lv']}!")]
                if t["lv"] >= b["max"]:
                    t["xp"] = 0; ev.append(("toast", f"🏆 {b['n']} no nível máximo — foco passa ao próximo prédio")); self.next_focus()
        dt = self._day_tile(today.isoformat())
        if dt is not None: dt["m"] = dt.get("m", 0) + minutes
        ev += self.check_day(today) + self.check_plazas(today); self.touch(); return ev

    def check_day(self, today):
        """Dia concluído = meta diária do Lyra Study batida (uma vez por data)."""
        g, iso = goal_min(self.d), today.isoformat()
        if g > 0 and iso not in self.s["counted"] and studied(self.d, today) >= g:
            self.s["counted"].append(iso); return self.add_day(today=today)
        return []

    def sync_days(self):
        """Ao abrir o app: dias passados com a meta batida viram quadrados (sem animações)."""
        g = goal_min(self.d)
        for iso in sorted(self.d["sessions"]):
            if g > 0 and iso not in self.s["counted"] and self.d["sessions"][iso].get("total", 0) >= g:
                self.s["counted"].append(iso); self.add_day(quiet=True, today=date.fromisoformat(iso))
        self.check_plazas(clock.today()); self.touch()

    # ---------- ações do usuário / admin ----------
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

    def level_up(self, n=1):
        t = self.tile(self.s["focus"]); ev = []
        if t and t["b"]:
            mx = C.bld(t["b"])["max"]
            if t["lv"] < mx: t["lv"] = min(mx, t["lv"] + n); t["xp"] = 0; ev = [("pop", self.s["focus"]), ("toast", f"⬆ Nível {t['lv']}")]
            if t["lv"] >= mx: self.next_focus()
            self.touch()
        return ev
