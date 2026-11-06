"""Modo Memória: ao clicar no logo, escolha um ano e reveja a 'foto' da cidade e as métricas daquele ano."""
import os
from datetime import date
import customtkinter as ctk
from storage import BASE
from theme import GOLD, MUTED, TEAL, PRIMARY
from util import fmt_dur
from . import catalog as C
from .engine import City
from .render import Camera, FX

class MemoryDialog(ctk.CTkToplevel):
    SIZE, EXPORT = (600, 350), (1280, 740)

    def __init__(self, master, w):
        super().__init__(master); self.w, self.img = w, None; self.title("Modo Memória — a evolução da sua cidade"); self.geometry("960x560"); self.transient(master.winfo_toplevel())
        hist = w.city.s["history"]; self.opts = {f"Ano {h['year']} — concluído em {date.fromisoformat(h['date']):%d/%m/%Y}": h for h in hist}; cur = f"Ano {w.city.year() + 1} (em andamento)"; self.opts[cur] = None
        top = ctk.CTkFrame(self, fg_color="transparent"); top.pack(fill="x", padx=14, pady=(12, 4))
        ctk.CTkLabel(top, text="📸 Modo Memória", font=("Segoe UI", 20, "bold"), text_color=GOLD).pack(side="left")
        self.sel = ctk.CTkOptionMenu(top, values=list(self.opts), command=self.show, width=300); self.sel.pack(side="right")
        body = ctk.CTkFrame(self, fg_color="transparent"); body.pack(fill="both", expand=True, padx=14, pady=6)
        self.pic = ctk.CTkLabel(body, text=""); self.pic.pack(side="left", padx=(0, 12), anchor="n")
        self.info = ctk.CTkScrollableFrame(body, label_text="Métricas do ano"); self.info.pack(side="left", fill="both", expand=True)
        bot = ctk.CTkFrame(self, fg_color="transparent"); bot.pack(fill="x", padx=14, pady=(2, 12))
        self.msg = ctk.CTkLabel(bot, text="" if hist else "Nenhum ano foi concluído ainda — mostrando o ano em andamento.", text_color=MUTED); self.msg.pack(side="left")
        ctk.CTkButton(bot, text="💾 Salvar foto (PNG)", command=self.export, **PRIMARY).pack(side="right")
        first = list(self.opts)[-2] if hist else cur; self.sel.set(first); self.show(first)

    def city_for(self, key):
        h = self.opts[key]; return (City.from_history(h) if h else self.w.city), h
    def render(self, city, size):
        cam, R = Camera(), (0, 0, 24, 18); r = self.w.R.clone(); cam.fit(R, *size, r.tall(city, R))
        return r.render(city, cam, *size, 0.0, FX(), [], False, view="ano", overlay=False)
    def show(self, key):
        city, h = self.city_for(key); self.cur = (city, h, key); img = self.render(city, self.SIZE)
        self.img = ctk.CTkImage(light_image=img, dark_image=img, size=self.SIZE); self.pic.configure(image=self.img)
        for x in self.info.winfo_children(): x.destroy()
        st = h["stats"] if h else {**City.year_stats(city.s["t"][city.ys():city.D]), "plazas": len(city.s["pz"]), "cars": len(city.s["oc"])}
        rows = [("📅 Dias concluídos", f"{st['days']} de {C.PER}"), ("⏱ Tempo de estudo", fmt_dur(st["minutes"])), ("🏢 Prédios", sum(st["buildings"].values())),
                ("📈 Nível médio", st["avg_level"]), ("🌳 Praças", st["plazas"]), ("🚗 Carros na frota", st["cars"])]
        for k, v in rows:
            r = ctk.CTkFrame(self.info, fg_color="transparent"); r.pack(fill="x"); ctk.CTkLabel(r, text=k, anchor="w").pack(side="left", padx=8); ctk.CTkLabel(r, text=str(v), text_color=TEAL).pack(side="right", padx=8)
        ctk.CTkLabel(self.info, text="Prédios por modelo", font=("Segoe UI", 13, "bold"), anchor="w").pack(fill="x", padx=8, pady=(10, 2))
        for bid, n in sorted(st["buildings"].items(), key=lambda x: -x[1]):
            name = next((b["n"] for b in C.BLD if b["id"] == bid), bid); ctk.CTkLabel(self.info, text=f"• {name}: {n}", anchor="w", text_color=MUTED).pack(fill="x", padx=14)
        ctk.CTkLabel(self.info, text="Por nível", font=("Segoe UI", 13, "bold"), anchor="w").pack(fill="x", padx=8, pady=(10, 2))
        for lv, n in sorted((int(k), v) for k, v in st["levels"].items()): ctk.CTkLabel(self.info, text=f"• Nível {lv}: {n}", anchor="w", text_color=MUTED).pack(fill="x", padx=14)
    def export(self):
        city, h, key = self.cur; os.makedirs(os.path.join(BASE, "snapshots"), exist_ok=True)
        p = os.path.join(BASE, "snapshots", f"ano_{h['year'] if h else city.year() + 1}.png"); self.render(city, self.EXPORT).save(p); self.msg.configure(text=f"Foto salva em {p}")
