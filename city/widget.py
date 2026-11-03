"""Componente CustomTkinter da cidade: mapa (Pillow -> PhotoImage) + painel de loja. Vive dentro da aba "Foco e Loja".

Segurança contra travamentos
  • UM único laço `after()` (_tick) e UM único ponto de agendamento; o id fica em self._job e é cancelado em destroy().
  • Intervalos fixos: 33 ms (≈30 fps), 50 ms se o quadro foi pesado, 100 ms com a aba oculta (nada é desenhado).
  • Antes de cada quadro valida winfo_exists(); exceções no desenho nunca derrubam o laço.
  • Imagens: sprites e versões redimensionadas ficam em cache no Renderer; só existe 1 PhotoImage (recriado apenas se o canvas mudar de tamanho).
Câmera FIXA: sem arrastar e sem zoom — a região da visão atual é enquadrada e centralizada no canvas."""
import math, time, traceback
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
        self.app, self.running, self._job, self._resize_job, self._toast_id, self._errs = app, running, None, None, 0, 0
        self.city = City(app.data); self.city.sync_days()                    # dias passados com a meta batida viram quadrados
        self.R, self.cam, self.fx, self.traffic = Renderer(), Camera(), FX(), Traffic()
        self.W, self.H, self.T0, self.last, self.reg = 700, 300, time.perf_counter(), time.perf_counter(), None
        top = ctk.CTkFrame(self, fg_color="transparent"); top.pack(fill="x")
        self.seg = ctk.CTkSegmentedButton(top, values=[n for _, n in C.VIEWS], command=self.set_view); self.seg.pack(side="left")
        self.seg.set(dict(C.VIEWS)[self.city.s["view"]])
        self.toast = ctk.CTkLabel(top, text="", text_color=GOLD, font=("Segoe UI", 13, "bold")); self.toast.pack(side="right", padx=8)
        self.info = ctk.CTkLabel(top, text="", text_color=MUTED); self.info.pack(side="right", padx=8)
        self.canvas = tk.Canvas(self, height=self.H, highlightthickness=0, bg="#0a0d1a"); self.canvas.pack(fill="x", pady=4)
        self.photo = ImageTk.PhotoImage(Image.new("RGB", (self.W, self.H))); self.img_id = self.canvas.create_image(0, 0, anchor="nw", image=self.photo)
        self.canvas.bind("<Configure>", self.on_size); self.canvas.bind("<ButtonRelease-1>", self.on_click)   # só clique (selecionar quadrado)
        self.panel = CityPanel(self, self); self.panel.pack(fill="both", expand=True)
        self.traffic.sync(self.city, self.now()); self.fit(); self.start()

    # ---------- ciclo de vida ----------
    def start(self):
        if self._job is None: self._job = self.after(C.FRAME_MS, self._tick)
    def destroy(self):
        for j in (self._job, self._resize_job):
            if j is not None:
                try: self.after_cancel(j)
                except Exception: pass
        self._job = self._resize_job = None; super().destroy()

    def _tick(self):
        """Quadro de animação. É o ÚNICO lugar que agenda o próximo quadro."""
        self._job = None
        if not self.winfo_exists(): return                                   # widget destruído: encerra a cadeia
        delay = C.IDLE_MS
        try:
            if self.winfo_viewable():                                        # aba oculta => não desenha nada
                t0 = time.perf_counter(); dt = min(.1, t0 - self.last); self.last = t0; t = t0 - self.T0
                self.traffic.step(dt, t); self.fx.prune(t)
                img = self.R.render(self.city, self.cam, self.W, self.H, t, self.fx, self.traffic.cars, self.running())
                if self.photo.width() != self.W or self.photo.height() != self.H: self.photo = ImageTk.PhotoImage(img); self.canvas.itemconfigure(self.img_id, image=self.photo)
                else: self.photo.paste(img)
                delay = C.FRAME_MS if (time.perf_counter() - t0) < .025 else C.HEAVY_MS   # quadro pesado => 20 fps para aliviar a thread principal
        except Exception:
            self._errs += 1
            if self._errs <= 3: traceback.print_exc()
            delay = C.HEAVY_MS * 4
        if self.winfo_exists(): self._job = self.after(delay, self._tick)

    # ---------- tempo e eventos ----------
    def now(self): return time.perf_counter() - self.T0

    def apply(self, events):
        """Aplica os eventos da engine: avisos, 'pop' de construção/evolução e fusões animadas."""
        for ev in events:
            if ev[0] == "toast": self.say(ev[1])
            elif ev[0] == "pop": self.fx.pop(ev[1], self.now())
            elif ev[0] == "merge": self.fx.merge(ev[1], self.now()); self.say(ev[2])
        self.changed()

    def say(self, msg):
        self.toast.configure(text=msg); self._toast_id += 1; n = self._toast_id
        self.after(3500, lambda: self.toast.configure(text="") if (n == self._toast_id and self.winfo_exists()) else None)

    def changed(self, force_fit=False):
        """Estado mudou: salva, ressincroniza carros, reenquadra se a região mudou e atualiza painel/cabeçalho."""
        save(self.app.data); self.traffic.sync(self.city, self.now())
        if force_fit or self.city.region() != self.reg: self.fit()
        self.panel.refresh(); self.app.update_header()

    def fit(self):
        self.reg = self.city.region(); self.cam.fit(self.reg, self.W, self.H, self.R.tall(self.city, self.reg)); self.R.prewarm(self.city, self.cam)

    # ---------- ações ----------
    def set_view(self, label):
        self.city.s["view"] = next(k for k, n in C.VIEWS if n == label); self.city.touch(); self.changed(True)   # trocar de visão não interrompe o foco
    def on_minute(self):
        """Chamado pelo FocusTab a cada minuto de foco: XP para o prédio em foco + checagem do dia."""
        self.apply(self.city.study(1))
    def dev_days(self, n):
        ev = []
        for i in range(n): ev = self.city.add_day(quiet=i < n - 1)
        self.apply(ev)
    def refresh(self):
        self.info.configure(text=f"{self.city.D} dias • {len(self.city.s['t'])} quadrados"); self.panel.refresh()

    # ---------- canvas ----------
    def on_size(self, e):
        """Redimensionou a janela: reenquadra (com debounce, para não recalcular a cada pixel arrastado)."""
        if e.width < 50 or e.height < 50 or (e.width == self.W and e.height == self.H): return
        self.W, self.H = e.width, e.height
        if self._resize_job is not None:
            try: self.after_cancel(self._resize_job)
            except Exception: pass
        self._resize_job = self.after(80, self._resized)
    def _resized(self):
        self._resize_job = None
        if not self.winfo_exists(): return
        self.photo = ImageTk.PhotoImage(Image.new("RGB", (self.W, self.H))); self.canvas.itemconfigure(self.img_id, image=self.photo); self.fit()
    def on_click(self, e):
        c, cam = self.city, self.cam; u, v = (e.x - cam.ox) / cam.k, 2 * (e.y - cam.oy) / cam.k; gx, gy = math.floor((u + v) / 2), math.floor((v - u) / 2); R = c.region()
        for d in c.geom()["days"]:
            if d["x"] == gx and d["y"] == gy and R[0] <= gx < R[2] and R[1] <= gy < R[3]:
                c.s["sel"] = d["i"]; c.touch(); save(self.app.data); self.panel.refresh(); return
