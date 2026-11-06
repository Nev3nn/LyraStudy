"""Painel abaixo do mapa (a loja agora é o overlay shop.py): foco, fluxo automático, prédio do dia aleatório e quadrado selecionado."""
import customtkinter as ctk
from theme import PRIMARY, GOLD, TEAL, MUTED, animate
from . import catalog as C

class CityPanel(ctk.CTkFrame):
    def __init__(self, master, w):
        super().__init__(master, fg_color="transparent"); self.w = w
        self.body = ctk.CTkScrollableFrame(self); self.body.pack(fill="both", expand=True); self.build()

    @property
    def c(self): return self.w.city
    def refresh(self): self.build()
    def card(self, title=None):
        f = ctk.CTkFrame(self.body); f.pack(fill="x", padx=4, pady=4)
        if title: ctk.CTkLabel(f, text=title, font=("Segoe UI", 14, "bold"), anchor="w").pack(fill="x", padx=12, pady=(8, 2))
        return f
    def bar(self, f, text, val, color=None):
        ctk.CTkLabel(f, text=text, text_color=MUTED, anchor="w").pack(fill="x", padx=12)
        b = ctk.CTkProgressBar(f, height=8, progress_color=color or TEAL); b.pack(fill="x", padx=12, pady=(2, 6)); animate(b, max(0, min(1, val)), 500)

    def build(self):
        for x in self.body.winfo_children(): x.destroy()
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
        sw = ctk.CTkSwitch(f, text="Construir sozinho a cada novo dia", command=lambda: self.set_flag("auto", sw)); sw.pack(anchor="w", padx=12, pady=3)
        if s["auto"]: sw.select()
        sw2 = ctk.CTkSwitch(f, text="🎲 Prédio do dia aleatório (entre os desbloqueados)", command=lambda: self.set_flag("rand", sw2)); sw2.pack(anchor="w", padx=12, pady=3)
        if s["rand"]: sw2.select()
        names = {C.bld(i)["n"]: i for i in s["ob"]}
        if names: om = ctk.CTkOptionMenu(f, values=list(names), command=lambda v: self.set_flag("model", names[v], True)); om.set(C.bld(s["model"])["n"] if s["model"] in s["ob"] else list(names)[0]); om.pack(fill="x", padx=12, pady=(3, 8))
        f = self.card("Quadrado selecionado"); t = c.tile(s["sel"])
        if not t: ctk.CTkLabel(f, text="Clique num quadrado do mapa.", text_color=MUTED).pack(padx=12, pady=4)
        elif t["b"]: ctk.CTkLabel(f, text=f"Dia {s['sel'] + 1} • {C.bld(t['b'])['n']} • nível {t['lv']}/{C.bld(t['b'])['max']}").pack(padx=12, pady=4)
        else:
            ctk.CTkLabel(f, text=f"Dia {s['sel'] + 1} • fundação livre", text_color=MUTED).pack(padx=12)
            r = ctk.CTkFrame(f, fg_color="transparent"); r.pack(fill="x", padx=8, pady=6)
            ctk.CTkButton(r, text="🎲 Aleatório", width=100, command=lambda: self.w.apply(c.build(s["sel"])), **PRIMARY).pack(side="left", padx=3)
            for i in s["ob"]: ctk.CTkButton(r, text=C.bld(i)["n"], width=90, fg_color="gray30", command=lambda i=i: self.w.apply(c.build(s["sel"], i))).pack(side="left", padx=3)
        if self.w.app.admin_on:
            f = self.card("🛠 Admin"); ctk.CTkButton(f, text="Abrir painel Admin", command=self.w.app.admin_click, **PRIMARY).pack(anchor="w", padx=12, pady=(2, 10))

    def set_focus(self, i): self.c.s["focus"] = i; self.c.touch(); self.w.changed()
    def set_flag(self, k, v, raw=False):
        self.c.s[k] = v if raw else bool(v.get()); self.c.touch(); self.w.changed()
