"""Componente CustomTkinter da cidade: mapa animado (Pillow -> PhotoImage) + painel de loja. Vive dentro da aba "Foco e Loja"."""
import math, time
import tkinter as tk
import customtkinter as ctk
from PIL import Image, ImageTk
from storage import save
from theme import GOLD, MUTED
from . import catalog as C
from .engine import City
from .panel import CityPanel
from .render import Renderer, Camera, FX
from .traffic import Traffic

class CityWidget(ctk.CTkFrame):
    def __init__(self, master, app, running=lambda: False):
        super().__init__(master, fg_color="transparent")
        self.app, self.running = app, running
        self.city = City(app.data); self.city.sync_days()                    # dias passados com a meta batida viram quadrados
        self.R, self.cam, self.fx, self.traffic, self._toast_id = Renderer(), Camera(), FX(), Traffic(), 0
        self.W, self.H, self.T0, self.last, self.reg, self._drag = 700, 300, time.perf_counter(), time.perf_counter(), None, None
        top = ctk.CTkFrame(self, fg_color="transparent"); top.pack(fill="x")
        self.seg = ctk.CTkSegmentedButton(top, values=[n for _, n in C.VIEWS], command=self.set_view); self.seg.pack(side="left")
        self.seg.set(dict(C.VIEWS)[self.city.s["view"]])
        self.toast = ctk.CTkLabel(top, text="", text_color=GOLD, font=("Segoe UI", 13, "bold")); self.toast.pack(side="right", padx=8)
        self.info = ctk.CTkLabel(top, text="", text_color=MUTED); self.info.pack(side="right", padx=8)
        self.canvas = tk.Canvas(self, height=self.H, highlightthickness=0, bg="#0a0d1a", cursor="fleur"); self.canvas.pack(fill="x", pady=4)
        self.photo = ImageTk.PhotoImage(Image.new("RGB", (self.W, self.H))); self.img_id = self.canvas.create_image(0, 0, anchor="nw", image=self.photo)
        self.canvas.bind("<Configure>", self.on_size); self.canvas.bind("<ButtonPress-1>", self.on_press); self.canvas.bind("<B1-Motion>", self.on_move)
        self.canvas.bind("<ButtonRelease-1>", self.on_release); self.canvas.bind("<MouseWheel>", self.on_wheel)
        self.canvas.bind("<Button-4>", lambda e: self.zoom(1.15, e)); self.canvas.bind("<Button-5>", lambda e: self.zoom(.87, e))
        self.panel = CityPanel(self, self); self.panel.pack(fill="both", expand=True)
        self.traffic.sync(self.city, self.now()); self.fit(True); self.loop()

    # ---------- tempo e eventos ----------
    def now(self): return time.perf_counter() - self.T0

    def apply(self, events):
        """Aplica os eventos devolvidos pela engine: avisos, 'pop' de construção/evolução e fusões animadas."""
        for ev in events:
            if ev[0] == "toast": self.say(ev[1])
            elif ev[0] == "pop": self.fx.pop(ev[1], self.now())
            elif ev[0] == "merge": self.fx.merge(ev[1], self.now()); self.say(ev[2])
        self.changed()

    def say(self, msg):
        self.toast.configure(text=msg); self._toast_id += 1; n = self._toast_id
        self.after(3500, lambda: self.toast.configure(text="") if n == self._toast_id else None)

    def changed(self, force_fit=False):
        """Estado mudou: salva, ressincroniza carros, reenquadra a câmera se a região mudou e atualiza painel/cabeçalho."""
        save(self.app.data); self.traffic.sync(self.city, self.now())
        reg = self.city.region()
        if force_fit or reg != self.reg: self.fit()
        self.panel.refresh(); self.app.update_header()

    def fit(self, snap=False):
        self.reg = self.city.region(); self.cam.fit(self.reg, self.W, self.H, self.R.tall(self.city, self.reg), snap)

    # ---------- ações ----------
    def set_view(self, label):
        self.city.s["view"] = next(k for k, n in C.VIEWS if n == label); self.city.touch(); self.changed(True)   # trocar de visão não interrompe o foco

    def on_minute(self):
        """Chamado pelo FocusTab a cada minuto de foco concluído: XP para o prédio em foco + checagem do dia."""
        self.apply(self.city.study(1))

    def dev_days(self, n):
        ev = []
        for i in range(n): ev = self.city.add_day(quiet=i < n - 1)
        self.apply(ev)

    def refresh(self):
        self.info.configure(text=f"{self.city.D} dias • {len(self.city.s['t'])} quadrados"); self.panel.refresh()

    # ---------- mouse ----------
    def on_size(self, e):
        if e.width < 50 or e.height < 50: return
        self.W, self.H = e.width, e.height; self.photo = ImageTk.PhotoImage(Image.new("RGB", (self.W, self.H))); self.canvas.itemconfigure(self.img_id, image=self.photo); self.fit(True)
    def on_press(self, e): self._drag = [e.x, e.y, 0]
    def on_move(self, e):
        if not self._drag: return
        dx, dy = e.x - self._drag[0], e.y - self._drag[1]; self._drag[0], self._drag[1] = e.x, e.y; self._drag[2] += abs(dx) + abs(dy); self.cam.pan(dx, dy)
    def on_release(self, e):
        if self._drag and self._drag[2] < 5: self.pick(e.x, e.y)
        self._drag = None
    def on_wheel(self, e): self.zoom(1.15 if e.delta > 0 else .87, e)
    def zoom(self, f, e): self.cam.zoom(f, e.x, e.y)
    def pick(self, px, py):
        c, cam = self.city, self.cam; u, v = (px - cam.ox) / cam.k, 2 * (py - cam.oy) / cam.k; gx, gy = math.floor((u + v) / 2), math.floor((v - u) / 2)
        for d in c.geom()["days"]:
            R = c.region()
            if d["x"] == gx and d["y"] == gy and R[0] <= gx < R[2] and R[1] <= gy < R[3]:
                c.s["sel"] = d["i"]; c.touch(); save(self.app.data); self.panel.refresh(); return

    # ---------- laço de animação (~30 fps; pausa quando a aba não está visível) ----------
    def loop(self):
        try:
            if not self.winfo_viewable(): self.after(250, self.loop); return
            now = time.perf_counter(); dt = min(.1, now - self.last); self.last = now; t = now - self.T0
            self.cam.step(); self.traffic.step(dt, t); self.fx.prune(t)
            img = self.R.render(self.city, self.cam, self.W, self.H, t, self.fx, self.traffic.cars, self.running())
            if self.photo.width() != self.W or self.photo.height() != self.H: self.photo = ImageTk.PhotoImage(img); self.canvas.itemconfigure(self.img_id, image=self.photo)
            else: self.photo.paste(img)
        finally:
            self.after(33, self.loop)
