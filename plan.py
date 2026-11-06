import clock
from util import fmt_dur
from datetime import date, timedelta
from tkinter import messagebox
import customtkinter as ctk
from rules import DAYS, build_schedule, weekly_minutes, propose_adjustment
from simulado import ProposalDialog
from storage import save
from theme import PRIMARY, GOLD, RED, TEAL, VIOLET, EDGE, MUTED, header, chip, tag_color, animate

class PlanTab(ctk.CTkFrame):
    def __init__(self, master, app):
        super().__init__(master, fg_color="transparent")
        self.app, self.mode = app, "Hoje"

    def clear(self):
        for w in self.winfo_children(): w.destroy()

    def refresh(self):
        self.clear()
        self.view() if self.app.data["schedule"] else self.wizard()

    # ---------- Assistente (3 perguntas) ----------
    def wizard(self):
        f = ctk.CTkFrame(self); f.pack(pady=30, ipadx=24, ipady=10)
        ctk.CTkLabel(f, text="Vamos montar seu cronograma", font=("Segoe UI", 20, "bold")).pack(pady=(16, 10))
        ctk.CTkLabel(f, text="Quais matérias você vai estudar? (separe por vírgula)").pack()
        self.e_sub = ctk.CTkEntry(f, width=380, placeholder_text="Matemática, Física, Inglês"); self.e_sub.pack(pady=6)
        ctk.CTkLabel(f, text="Quantas horas por dia você quer estudar?").pack()
        self.e_h = ctk.CTkEntry(f, width=120, placeholder_text="2.5"); self.e_h.pack(pady=6)
        ctk.CTkLabel(f, text="Quantas matérias você quer estudar por dia?").pack()
        self.e_n = ctk.CTkEntry(f, width=120, placeholder_text="2"); self.e_n.pack(pady=6)
        self.err = ctk.CTkLabel(f, text="", text_color=RED); self.err.pack()
        ctk.CTkButton(f, text="Próximo", command=self.step2, **PRIMARY).pack(pady=10)

    def step2(self):
        subs = list(dict.fromkeys(s.strip() for s in self.e_sub.get().split(",") if s.strip()))
        try: h = float(self.e_h.get().replace(",", ".")); n = int(self.e_n.get())
        except ValueError: h = n = 0
        if not subs or h <= 0 or n < 1:
            return self.err.configure(text="Informe matérias, horas por dia (> 0) e matérias por dia (>= 1).")
        self.clear()
        f = ctk.CTkScrollableFrame(self, label_text="Dificuldade de cada matéria (1 = fácil, 5 = muito difícil)")
        f.pack(fill="both", expand=True, padx=40, pady=10)
        self.sl = {}
        for s in subs:
            r = ctk.CTkFrame(f, fg_color="transparent"); r.pack(fill="x", pady=6)
            ctk.CTkLabel(r, text=s, width=160, anchor="w").pack(side="left")
            v = ctk.CTkLabel(r, text="3", width=24)
            sl = ctk.CTkSlider(r, from_=1, to=5, number_of_steps=4,
                               command=lambda x, l=v: l.configure(text=str(int(round(x)))))
            sl.set(3); sl.pack(side="left", fill="x", expand=True, padx=8); v.pack(side="left"); self.sl[s] = sl
        self.err = ctk.CTkLabel(self, text="", text_color=RED); self.err.pack()
        ctk.CTkButton(self, text="Gerar cronograma", command=lambda: self.finish(h, n), **PRIMARY).pack(pady=10)

    def finish(self, h, n):
        w = {s: int(round(sl.get())) for s, sl in self.sl.items()}
        n = min(n, len(w)); d = self.app.data
        d.update(subjects=w, daily_goal_h=h, per_day=n, schedule=build_schedule(w, h, n), schedule_date=clock.today().isoformat())
        self.app.commit()

    # ---------- Cronograma + To-Do ----------
    def view(self):
        d = self.app.data; wm = weekly_minutes(d["subjects"], d["daily_goal_h"])
        top = header(self, "🗓 Cronograma", f"{fmt_dur(d['daily_goal_h'] * 60)}/dia • {fmt_dur(sum(wm.values()))}/semana • {d['per_day']} matéria(s)/dia")
        ctk.CTkButton(top, text="Reconfigurar", width=110, fg_color="gray30", command=lambda: (self.clear(), self.wizard())).pack(side="right")
        ctk.CTkButton(top, text="🔄 Reajustar (últimos 3 simulados)", width=240, command=self.readjust, **PRIMARY).pack(side="right", padx=8)
        main = ctk.CTkFrame(self, fg_color="transparent"); main.pack(fill="both", expand=True)
        left = ctk.CTkScrollableFrame(main, label_text="Grade semanal"); left.pack(side="left", fill="both", expand=True, padx=(0, 6))
        sm = ctk.CTkFrame(left, fg_color="transparent"); sm.pack(fill="x", pady=(0, 6))
        for i, (s, m) in enumerate(sorted(wm.items(), key=lambda x: -x[1])):
            chip(sm, f"{s} · {fmt_dur(m)} · dif. {d['subjects'][s]}", tag_color(s)).grid(row=i // 3, column=i % 3, padx=3, pady=2, sticky="w")
        grid = ctk.CTkFrame(left, fg_color="transparent"); grid.pack(fill="x")
        for c in range(4): grid.columnconfigure(c, weight=1, uniform="d")
        for i, day in enumerate(DAYS):
            hoje = i == clock.today().weekday(); tasks = d["schedule"].get(day, [])
            card = ctk.CTkFrame(grid, border_width=2, border_color=VIOLET if hoje else EDGE)
            card.grid(row=i // 4, column=i % 4, padx=4, pady=4, sticky="nsew")
            ctk.CTkLabel(card, text=day + (" • hoje" if hoje else ""), font=("Segoe UI", 13, "bold"), text_color=GOLD if hoje else None).pack(anchor="w", padx=10, pady=(8, 0))
            ctk.CTkLabel(card, text=fmt_dur(sum(t["minutes"] for t in tasks)), text_color=MUTED).pack(anchor="w", padx=10)
            for t in tasks: chip(card, f"{t['subject']} · {t['minutes']}m", tag_color(t["subject"])).pack(anchor="w", padx=8, pady=2)
            ctk.CTkLabel(card, text="", height=4).pack()
        right = ctk.CTkScrollableFrame(main, label_text="To-Do", width=300); right.pack(side="left", fill="y")
        self.todo_lbl = ctk.CTkLabel(right, text="", text_color=MUTED); self.todo_lbl.pack()
        self.todo_bar = ctk.CTkProgressBar(right, height=10, progress_color=TEAL); self.todo_bar.set(0); self.todo_bar.pack(fill="x", padx=10, pady=(2, 6))
        seg = ctk.CTkSegmentedButton(right, values=["Hoje", "Semana"], command=self.set_mode); seg.set(self.mode); seg.pack(pady=6)
        self.todo(right); self.upd_todo(True)

    def set_mode(self, m):
        self.mode = m; self.refresh()

    def todo(self, parent):
        d, today = self.app.data, clock.today(); self.today_keys = []
        days = [today] if self.mode == "Hoje" else [today - timedelta(today.weekday()) + timedelta(i) for i in range(7)]
        for day in days:
            tasks = d["schedule"].get(DAYS[day.weekday()], [])
            if self.mode != "Hoje":
                ctk.CTkLabel(parent, text=f"{DAYS[day.weekday()]} {day:%d/%m}", font=("Segoe UI", 13, "bold")).pack(anchor="w", pady=(8, 0))
            for t in tasks:
                key = f"{day.isoformat()}|{t['subject']}"
                if day == today: self.today_keys.append(key)
                var = ctk.BooleanVar(value=d["todo"].get(key, False))
                ctk.CTkCheckBox(parent, text=f"{t['subject']} — {fmt_dur(t['minutes'])}", variable=var,
                                command=lambda k=key, v=var: self.check(k, v)).pack(anchor="w", pady=3)

    def upd_todo(self, first=False):
        keys = self.today_keys; done = sum(bool(self.app.data["todo"].get(k)) for k in keys)
        self.todo_lbl.configure(text=f"{done}/{len(keys)} concluídas hoje")
        animate(self.todo_bar, done / len(keys) if keys else 0, 500, not first)

    def check(self, key, var):
        self.app.data["todo"][key] = var.get(); save(self.app.data); self.upd_todo()

    def readjust(self):
        d = self.app.data
        if not d["simulados"]:
            return messagebox.showinfo("Reajuste", "Registre ao menos um simulado na aba Desempenho primeiro.")
        new, changes, sched = propose_adjustment(d)
        if not changes:
            return messagebox.showinfo("Reajuste", "Os pesos já refletem seus últimos 3 simulados. Nada a mudar.")
        ProposalDialog(self, self.app, new, changes, sched)
