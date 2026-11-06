"""Loja em OVERLAY: abre por cima da cidade (sem sair da aba) com minimapa, saldo e abas Prédios / Veículos / Praças."""
import clock
from datetime import date
import customtkinter as ctk
from theme import PRIMARY, GOLD, TEAL, MUTED, EDGE, animate
from util import fmt_dur
from . import catalog as C
from .render import Camera, FX

class ShopOverlay(ctk.CTkFrame):
    TABS = ["Prédios", "Veículos", "Praças"]

    def __init__(self, master, w):
        super().__init__(master, corner_radius=16, border_width=2, border_color=GOLD)
        self.w, self.tab, self.thumbs, self.btns, self.opened, self._mini = w, "Prédios", {}, [], False, None
        head = ctk.CTkFrame(self, fg_color="transparent"); head.pack(fill="x", padx=14, pady=(10, 4))
        ctk.CTkLabel(head, text="🛒 Loja da cidade", font=("Segoe UI", 18, "bold"), text_color=GOLD).pack(side="left")
        self.pts = ctk.CTkLabel(head, text="", font=("Segoe UI", 14, "bold")); self.pts.pack(side="left", padx=14)
        ctk.CTkButton(head, text="✕ Fechar", width=84, fg_color="gray30", command=self.close).pack(side="right")
        body = ctk.CTkFrame(self, fg_color="transparent"); body.pack(fill="both", expand=True, padx=12, pady=(0, 10))
        left = ctk.CTkFrame(body, width=290); left.pack(side="left", fill="y", padx=(0, 8)); left.pack_propagate(False)
        ctk.CTkLabel(left, text="🗺 Mapa da cidade (ano atual)", font=("Segoe UI", 13, "bold")).pack(pady=(10, 4))
        self.mini = ctk.CTkLabel(left, text=""); self.mini.pack(padx=8)
        self.mini_info = ctk.CTkLabel(left, text="", text_color=MUTED, wraplength=260, justify="left"); self.mini_info.pack(padx=10, pady=8)
        right = ctk.CTkFrame(body, fg_color="transparent"); right.pack(side="left", fill="both", expand=True)
        self.seg = ctk.CTkSegmentedButton(right, values=self.TABS, command=self.set_tab); self.seg.set(self.tab); self.seg.pack(anchor="w", pady=(0, 4))
        self.list = ctk.CTkScrollableFrame(right); self.list.pack(fill="both", expand=True)

    # ---------- abrir / fechar ----------
    def toggle(self): self.close() if self.opened else self.open()
    def open(self):
        self.opened = True; self.place(relx=.015, rely=.02, relwidth=.97, relheight=.96); self.lift()
        self.winfo_toplevel().bind("<Escape>", lambda e: self.close()); self.refresh()
    def close(self):
        self.opened = False; self.place_forget()
        try: self.winfo_toplevel().unbind("<Escape>")
        except Exception: pass

    # ---------- conteúdo ----------
    @property
    def c(self): return self.w.city
    def set_tab(self, t): self.tab = t; self.build()
    def refresh(self):
        if not self.opened: return
        self.pts.configure(text=f"⭐ {self.w.app.data['points']} pts"); self.update_mini(); self.build()
    def update_mini(self):
        """Minimapa: o ano inteiro (12 blocões) renderizado com o MESMO renderer (sprites em cache compartilhado)."""
        if self._mini is None: self._mini = self.w.R.clone()
        size, cam, R = (270, 190), Camera(), (0, 0, 24, 18); cam.fit(R, *size, self._mini.tall(self.c, R))
        img = self._mini.render(self.c, cam, *size, 0.0, FX(), [], False, view="ano", overlay=False)
        self._img = ctk.CTkImage(light_image=img, dark_image=img, size=size); self.mini.configure(image=self._img)
        self.mini_info.configure(text=f"{self.c.D} dias • {len(self.c.s['pz'])} praças • {len(self.c.s['oc'])} carros • {len(self.c.s['ob'])}/{len(C.BLD)} prédios")
    def thumb(self, key, h):
        if (key, h) not in self.thumbs: im = self.w.R.thumb(key, h); self.thumbs[(key, h)] = ctk.CTkImage(light_image=im, dark_image=im, size=im.size)
        return self.thumbs[(key, h)]
    def build(self):
        for x in self.list.winfo_children(): x.destroy()
        self.btns = []; {"Prédios": self.t_bld, "Veículos": self.t_car, "Praças": self.t_plz}[self.tab]()
    def card(self):
        f = ctk.CTkFrame(self.list); f.pack(fill="x", padx=4, pady=4); return f
    def bar(self, f, text, val, color=None):
        ctk.CTkLabel(f, text=text, text_color=MUTED, anchor="w").pack(fill="x", padx=12)
        b = ctk.CTkProgressBar(f, height=8, progress_color=color or TEAL); b.pack(fill="x", padx=12, pady=(2, 6)); animate(b, max(0, min(1, val)), 500)
    def row(self, title, thumbs, tags, own, kind, iid, price):
        f = self.card(); r = ctk.CTkFrame(f, fg_color="transparent"); r.pack(fill="x", padx=10, pady=(8, 2))
        for key, h in thumbs: ctk.CTkLabel(r, text="", image=self.thumb(key, h)).pack(side="left", padx=3)
        ctk.CTkLabel(f, text=title, font=("Segoe UI", 14, "bold"), anchor="w").pack(fill="x", padx=12)
        ctk.CTkLabel(f, text=tags, text_color=MUTED, anchor="w").pack(fill="x", padx=12)
        if own: ctk.CTkLabel(f, text="✔ Desbloqueado", text_color=TEAL, anchor="w").pack(fill="x", padx=12, pady=(0, 8))
        else:
            b = ctk.CTkButton(f, text=f"Comprar • {price} pts", command=lambda: self.buy(kind, iid), state="normal" if self.w.app.data["points"] >= price else "disabled", **PRIMARY); b.pack(anchor="w", padx=12, pady=(2, 8)); self.btns.append((b, price))
        return f
    def t_bld(self):
        if not C.BLD: ctk.CTkLabel(self.list, text="Nenhum prédio no catálogo.\nAdicione artes em art-source/buildings e rode tools/process_assets.py.", text_color=MUTED).pack(pady=30)
        for b in C.BLD: self.row(b["n"], [(f"buildings/{b['id']}_{l}", 84) for l in range(1, b["max"] + 1)], f"Níveis 1–{b['max']} • " + (f"{b['p']} pts" if b["p"] else "Grátis"), b["id"] in self.c.s["ob"], "b", b["id"], b["p"])
    def t_car(self):
        for k in C.CAR: self.row(k["n"], [(f"cars/{k['id']}", 50)], f"{k['p']} pts • Premium" if k["p"] else "Grátis", k["id"] in self.c.s["oc"], "c", k["id"], k["p"])
    def t_plz(self):
        c = self.c; t = clock.today(); nxt = date(t.year + (t.month == 12), t.month % 12 + 1, 1)
        f = self.card(); ctk.CTkLabel(f, text="🗓 Metas do mês", font=("Segoe UI", 14, "bold"), anchor="w").pack(fill="x", padx=12, pady=(8, 0))
        ctk.CTkLabel(f, text=f"O progresso e o acesso reiniciam em {nxt:%d/%m} (as praças já construídas ficam no mapa).", text_color=MUTED, anchor="w", wraplength=420, justify="left").pack(fill="x", padx=12)
        n = len(c.styles()); left = max(0, C.PLAZA_EVERY - c.s["since"])
        ctk.CTkLabel(f, text=(f"🌳 Nova praça aleatória em {left} dia(s)." if n >= C.PLAZA_MIN_UNLOCKED else f"Libere {C.PLAZA_MIN_UNLOCKED} praças no mês para ganhar uma praça nova a cada {C.PLAZA_EVERY} dias."), anchor="w", text_color=GOLD).pack(fill="x", padx=12, pady=(4, 8))
        f = self.card(); ctk.CTkLabel(f, text="Estilo das praças novas", font=("Segoe UI", 14, "bold"), anchor="w").pack(fill="x", padx=12, pady=(8, 2))
        self.var = ctk.StringVar(value=c.s["plaza"]); opts = [("auto", "🎲 Aleatório entre as liberadas")] + [(p["id"], p["n"]) for p in C.PLZ if c.s["cy"].get(p["id"])]
        for v, txt in opts: ctk.CTkRadioButton(f, text=txt, variable=self.var, value=v, command=self.set_plaza).pack(anchor="w", padx=14, pady=2)
        ctk.CTkLabel(f, text="").pack()
        for p, v, need, done in c.plaza_progress():
            goal = f"{fmt_dur(need * 60)} de estudo" if p["kind"] == "h" else f"{need} dia(s) concluído(s)"; cur = fmt_dur(v * 60) if p["kind"] == "h" else f"{int(v)}"
            fr = self.card(); r = ctk.CTkFrame(fr, fg_color="transparent"); r.pack(fill="x", padx=10, pady=(8, 2)); ctk.CTkLabel(r, text="", image=self.thumb(f"plazas/{p['id']}", 70)).pack(side="left", padx=3)
            ctk.CTkLabel(fr, text=p["n"], font=("Segoe UI", 14, "bold"), anchor="w").pack(fill="x", padx=12)
            self.bar(fr, ("✔ Liberada neste mês" if done else f"Meta: {goal} no mês • atual: {cur}"), min(1, v / need), TEAL if done else None)
    def set_plaza(self): self.c.s["plaza"] = self.var.get(); self.c.touch(); self.w.changed()
    def buy(self, kind, iid):
        ok, ev = self.c.buy(kind, iid)
        if ok: self.w.apply(ev); self.w.app.commit(); self.refresh()
