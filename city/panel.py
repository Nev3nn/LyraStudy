"""Painel abaixo do mapa: Cidade (foco, fluxo automático, dia aleatório, dev) • Prédios • Veículos • Praças."""
import customtkinter as ctk
from theme import PRIMARY, GOLD, TEAL, MUTED, EDGE, VIOLET, animate
from . import catalog as C

class CityPanel(ctk.CTkFrame):
    TABS = ["Cidade", "Prédios", "Veículos", "Praças"]

    def __init__(self, master, w):
        super().__init__(master, fg_color="transparent"); self.w, self.tab, self.thumbs, self.btns = w, "Cidade", {}, []
        self.seg = ctk.CTkSegmentedButton(self, values=self.TABS, command=self.set_tab); self.seg.set(self.tab); self.seg.pack(anchor="w", pady=(0, 4))
        self.body = ctk.CTkScrollableFrame(self); self.body.pack(fill="both", expand=True); self.build()

    # ---------- infra ----------
    @property
    def c(self): return self.w.city
    def set_tab(self, t): self.tab = t; self.build()
    def refresh(self):
        if self.tab == "Cidade": self.build()
        else:
            for b, price in self.btns: b.configure(state="normal" if self.w.app.data["points"] >= price else "disabled")
    def card(self, title=None):
        f = ctk.CTkFrame(self.body); f.pack(fill="x", padx=4, pady=4)
        if title: ctk.CTkLabel(f, text=title, font=("Segoe UI", 14, "bold"), anchor="w").pack(fill="x", padx=12, pady=(8, 2))
        return f
    def bar(self, f, text, val, color=None):
        ctk.CTkLabel(f, text=text, text_color=MUTED, anchor="w").pack(fill="x", padx=12)
        b = ctk.CTkProgressBar(f, height=8, progress_color=color or TEAL); b.pack(fill="x", padx=12, pady=(2, 6)); animate(b, max(0, min(1, val)), 500)
    def thumb(self, key, h):
        if (key, h) not in self.thumbs: im = self.w.R.thumb(key, h); self.thumbs[(key, h)] = ctk.CTkImage(light_image=im, dark_image=im, size=im.size)
        return self.thumbs[(key, h)]
    def build(self):
        for x in self.body.winfo_children(): x.destroy()
        self.btns = []; {"Cidade": self.t_city, "Prédios": self.t_bld, "Veículos": self.t_car, "Praças": self.t_plz}[self.tab]()

    # ---------- Cidade ----------
    def t_city(self):
        c, s = self.c, self.c.s; jn = c.jn()
        f = self.card("Fusão do território")
        self.bar(f, f"Dia → Semana ({jn % 7}/7)", jn % 7 / 7); self.bar(f, f"Semana → Mês ({(jn // 7) % 4}/4)", (jn // 7) % 4 / 4); self.bar(f, f"Mês → Ano ({jn // 28}/12)", jn / C.PER, GOLD)
        f = self.card("🎯 Modo Foco")
        cand = c.candidates(); lab = {i: f"Dia {i + 1} — {C.bld(c.tile(i)['b'])['n']} (Nv {c.tile(i)['lv']}/{C.bld(c.tile(i)['b'])['max']})" for i in cand}
        if cand:
            om = ctk.CTkOptionMenu(f, values=list(lab.values()), command=lambda v: self.set_focus({x: i for i, x in lab.items()}[v])); om.set(lab.get(s["focus"], list(lab.values())[0])); om.pack(fill="x", padx=12, pady=4)
            t = c.tile(s["focus"]); b = t and t["b"] and C.bld(t["b"])
            if b and t["lv"] < b["max"]: self.bar(f, f"XP {t['xp']}/{100 * t['lv']} • {C.XP_PER_MIN} XP por minuto de foco", t["xp"] / (100 * t["lv"]))
            elif b: ctk.CTkLabel(f, text="Nível máximo — o foco passa ao próximo prédio", text_color=MUTED).pack(padx=12)
        else: ctk.CTkLabel(f, text="Construa um prédio numa fundação para direcionar o XP.", text_color=MUTED).pack(padx=12, pady=4)
        f = self.card("⚙ Fluxo automático")
        sw = ctk.CTkSwitch(f, text="Construir sozinho a cada novo dia", command=lambda: self.set_flag("auto", sw)); sw.pack(anchor="w", padx=12, pady=3); sw.select() if s["auto"] else None
        sw2 = ctk.CTkSwitch(f, text="🎲 Prédio do dia aleatório (entre os desbloqueados)", command=lambda: self.set_flag("rand", sw2)); sw2.pack(anchor="w", padx=12, pady=3); sw2.select() if s["rand"] else None
        names = {C.bld(i)["n"]: i for i in s["ob"]}; om = ctk.CTkOptionMenu(f, values=list(names), command=lambda v: self.set_flag("model", names[v], True)); om.set(C.bld(s["model"])["n"] if s["model"] in s["ob"] else list(names)[0]); om.pack(fill="x", padx=12, pady=(3, 8))
        f = self.card("Quadrado selecionado"); t = c.tile(s["sel"])
        if not t: ctk.CTkLabel(f, text="Clique num quadrado do mapa.", text_color=MUTED).pack(padx=12, pady=4)
        elif t["b"]: ctk.CTkLabel(f, text=f"Dia {s['sel'] + 1} • {C.bld(t['b'])['n']} • nível {t['lv']}/{C.bld(t['b'])['max']}").pack(padx=12, pady=4)
        else:
            ctk.CTkLabel(f, text=f"Dia {s['sel'] + 1} • fundação livre", text_color=MUTED).pack(padx=12)
            r = ctk.CTkFrame(f, fg_color="transparent"); r.pack(fill="x", padx=8, pady=6)
            ctk.CTkButton(r, text="🎲 Aleatório", width=100, command=lambda: self.w.apply(c.build(s["sel"])), **PRIMARY).pack(side="left", padx=3)
            for i in s["ob"]: ctk.CTkButton(r, text=C.bld(i)["n"], width=90, fg_color="gray30", command=lambda i=i: self.w.apply(c.build(s["sel"], i))).pack(side="left", padx=3)
        f = self.card("🛠 Dev"); r = ctk.CTkFrame(f, fg_color="transparent"); r.pack(fill="x", padx=8, pady=6)
        for txt, fn in (("+1 dia", lambda: self.w.dev_days(1)), ("+7 dias", lambda: self.w.dev_days(7)), ("+28 dias", lambda: self.w.dev_days(28)), ("+1 ano", lambda: self.w.dev_days(336)), ("+1 nível", lambda: self.w.apply(c.dev_level_up()))):
            ctk.CTkButton(r, text=txt, width=70, fg_color="gray30", command=fn).pack(side="left", padx=3)

    def set_focus(self, i): self.c.s["focus"] = i; self.c.touch(); self.w.changed()
    def set_flag(self, k, v, raw=False):
        self.c.s[k] = v if raw else bool(v.get()); self.c.touch(); self.w.changed()

    # ---------- Prédios / Veículos / Praças ----------
    def row(self, title, thumbs, tags, own, kind, iid, price, extra=None):
        f = self.card(); r = ctk.CTkFrame(f, fg_color="transparent"); r.pack(fill="x", padx=10, pady=(8, 2))
        for key, h in thumbs: ctk.CTkLabel(r, text="", image=self.thumb(key, h)).pack(side="left", padx=3)
        ctk.CTkLabel(f, text=title, font=("Segoe UI", 14, "bold"), anchor="w").pack(fill="x", padx=12)
        ctk.CTkLabel(f, text=tags, text_color=MUTED, anchor="w").pack(fill="x", padx=12)
        if extra: extra(f)
        if kind:
            if own: ctk.CTkLabel(f, text="✔ Desbloqueado", text_color=TEAL, anchor="w").pack(fill="x", padx=12, pady=(0, 8))
            else:
                b = ctk.CTkButton(f, text=f"Comprar • {price} pts", command=lambda: self.buy(kind, iid), state="normal" if self.w.app.data["points"] >= price else "disabled", **PRIMARY); b.pack(anchor="w", padx=12, pady=(2, 8)); self.btns.append((b, price))
    def t_bld(self):
        for b in C.BLD: self.row(b["n"], [(f"buildings/{b['id']}_{l}", 72) for l in range(1, b["max"] + 1)], f"Níveis 1–{b['max']} • " + (f"{b['p']} pts" if b["p"] else "Grátis"), b["id"] in self.c.s["ob"], "b", b["id"], b["p"])
    def t_car(self):
        for k in C.CAR: self.row(k["n"], [(f"cars/{k['id']}", 48)], f"{k['p']} pts • Premium" if k["p"] else "Grátis", k["id"] in self.c.s["oc"], "c", k["id"], k["p"])
    def t_plz(self):
        c = self.c; f = self.card("Estilo das praças"); ctk.CTkLabel(f, text="2 praças aparecem por semana, em posições aleatórias.", text_color=MUTED, anchor="w").pack(fill="x", padx=12)
        self.var = ctk.StringVar(value=c.s["plaza"]); opts = [("auto", "🎲 Aleatório entre as desbloqueadas")] + [(p["id"], p["n"]) for p in C.PLZ if c.s["unl"].get(p["id"])]
        for v, txt in opts: ctk.CTkRadioButton(f, text=txt, variable=self.var, value=v, command=self.set_plaza).pack(anchor="w", padx=14, pady=2)
        ctk.CTkLabel(f, text="").pack()
        for p in C.PLZ:
            prog = min(c.D / p["d"], c.total_min() / 60 / p["h"], 1)
            self.row(p["n"], [(f"plazas/{p['id']}", 70)], f"Desbloqueia com {p['d']} dia(s) e {p['h']} h de estudo", False, None, None, 0, lambda f, prog=prog, p=p: self.bar(f, "✔ Desbloqueada" if c.unlocked(p) else f"{min(c.D, p['d'])}/{p['d']} dias • {min(c.total_min() / 60, p['h']):.1f}/{p['h']} h", prog))
    def set_plaza(self): self.c.s["plaza"] = self.var.get(); self.c.touch(); self.w.changed()

    def buy(self, kind, iid):
        ok, ev = self.c.buy(kind, iid)
        if ok: self.w.apply(ev); self.w.app.commit(); self.build()
