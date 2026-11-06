import clock
from util import fmt_dur
from datetime import date
import customtkinter as ctk
import history, month
from rules import (goal_min, studied, week_days, weekly_minutes, analyze, level, propose_adjustment,
                   reminder_due, grade, streak)
from simulado import SimuladoDialog, WeightsDialog, ProposalDialog
from theme import PRIMARY, GOLD, TEAL, RED, VIOLET, MUTED, LV, header, kpi, animate, chip, tag_color

class StatsTab(ctk.CTkFrame):
    VIEWS = ["Visão geral", "Mês", "Simulados"]

    def __init__(self, master, app):
        super().__init__(master, fg_color="transparent")
        self.app, self.view = app, "Visão geral"
        t = clock.today(); self.month = (t.year, t.month)
        header(self, "📊 Desempenho", "metas, constância e simulados")
        self.seg = ctk.CTkSegmentedButton(self, values=self.VIEWS, command=self.set_view); self.seg.pack(anchor="w", pady=(0, 6))
        self.body = ctk.CTkScrollableFrame(self, fg_color="transparent"); self.body.pack(fill="both", expand=True)

    def set_view(self, v):
        self.view = v; self.refresh()

    def refresh(self):
        self.seg.set(self.view)
        for w in self.body.winfo_children(): w.destroy()
        if not self.app.data["schedule"]:
            ctk.CTkLabel(self.body, text="Monte seu cronograma na aba Cronograma para ver as métricas.", text_color=MUTED).pack(pady=40); return
        {"Visão geral": self.overview, "Mês": lambda: month.build(self), "Simulados": lambda: history.build(self)}[self.view]()

    # ---------- componentes compartilhados (usados também por month.py e history.py) ----------
    def section(self, title):
        f = ctk.CTkFrame(self.body); f.pack(fill="x", padx=6, pady=8)
        ctk.CTkLabel(f, text=title, font=("Segoe UI", 15, "bold"), anchor="w").pack(fill="x", padx=14, pady=(10, 4))
        return f

    def bar(self, parent, text, val, goal, color=None, right=""):
        f = ctk.CTkFrame(parent, fg_color="transparent"); f.pack(fill="x", padx=14, pady=4)
        top = ctk.CTkFrame(f, fg_color="transparent"); top.pack(fill="x")
        ctk.CTkLabel(top, text=text, anchor="w").pack(side="left")
        ctk.CTkLabel(top, text=right, text_color=MUTED).pack(side="right")
        b = ctk.CTkProgressBar(f, height=12, progress_color=color or (TEAL if val >= goal else GOLD)); b.pack(fill="x", pady=(2, 0))
        animate(b, min(1, val / goal) if goal else 0)

    def kpis(self, items):
        row = ctk.CTkFrame(self.body, fg_color="transparent"); row.pack(fill="x")
        for i, it in enumerate(items):
            row.columnconfigure(i, weight=1, uniform="k"); kpi(row, *it).grid(row=0, column=i, padx=6, pady=6, sticky="nsew")

    def register(self):
        SimuladoDialog(self, self.app, self.after_register)

    def after_register(self):
        new, changes, sched = propose_adjustment(self.app.data)
        ProposalDialog(self, self.app, new, changes, sched) if changes else self.app.refresh()

    # ---------- Visão geral ----------
    def overview(self):
        d, today = self.app.data, clock.today(); g = goal_min(d)
        days = [x for x in week_days() if x <= today]
        hoje, semana = studied(d, today), sum(studied(d, x) for x in days)
        if reminder_due(d):
            b = ctk.CTkFrame(self.body, fg_color="#4a3a1a"); b.pack(fill="x", padx=6, pady=6)
            ctk.CTkLabel(b, text="⏰ Faz mais de 1 mês sem simulado. Recomendamos revisar manualmente os graus de dificuldade.",
                         wraplength=560, justify="left").pack(side="left", padx=12, pady=10)
            ctk.CTkButton(b, text="Revisar agora", width=110, command=lambda: WeightsDialog(self, self.app), **PRIMARY).pack(side="right", padx=12)
        self.kpis([("🏅", grade(d, today.year, today.month)["score"], "nota do mês (0 a 10)", GOLD, "{:.1f}"),
                   ("⏱", 0, f"estudado hoje (meta {fmt_dur(g)})", TEAL, "", fmt_dur(hoje)),
                   ("🔥", streak(d), "dias seguidos na meta", RED, "{:.0f}"),
                   ("📝", len(d["simulados"]), "simulados feitos", VIOLET, "{:.0f}")])
        s = self.section("Metas")
        self.bar(s, f"{'✅' if hoje >= g else '⏳'} Hoje", hoje, g, right=f"{fmt_dur(hoje)} / {fmt_dur(g)}")
        self.bar(s, f"{'✅' if semana >= g * 7 else '⏳'} Semana", semana, g * 7, right=f"{fmt_dur(semana)} / {fmt_dur(g * 7)}")
        s = self.section("Matérias da semana")
        for subj, m in weekly_minutes(d["subjects"], d["daily_goal_h"]).items():
            done = sum(studied(d, x, subj) for x in days)
            self.bar(s, subj + ("  ⚠ pendente" if done < m else "  ✅"), done, m, tag_color(subj), f"{fmt_dur(done)} / {fmt_dur(m)}")
        s = self.section("Penalidades do ano")
        year = str(today.year); lost = sum(e["loss"] for e in d["penalty_log"] if e["date"].startswith(year))
        ctk.CTkLabel(s, text=f"Pontos perdidos em {year}: {lost}  •  dias seguidos sem meta: {d['streak_miss']}",
                     text_color=RED if lost else MUTED, anchor="w").pack(fill="x", padx=14)
        for e in d["penalty_log"][-5:]:
            ctk.CTkLabel(s, text=f"   {e['date']}: -{e['loss']} pts ({e['streak']} dias seguidos)", anchor="w", text_color=MUTED).pack(fill="x", padx=14)
        ctk.CTkLabel(s, text="", height=4).pack()
        s = self.section("Análise dos últimos 3 simulados (nota 0 a 10)")
        row = ctk.CTkFrame(s, fg_color="transparent"); row.pack(fill="x", padx=14, pady=(0, 6))
        ctk.CTkButton(row, text="➕ Registrar simulado", command=self.register, **PRIMARY).pack(side="left")
        ctk.CTkButton(row, text="🔧 Revisar dificuldades", fg_color="gray30", command=lambda: WeightsDialog(self, self.app)).pack(side="left", padx=8)
        an = analyze(d)
        if not an: ctk.CTkLabel(s, text="Registre um simulado para ver a análise.", text_color=MUTED, anchor="w").pack(fill="x", padx=14, pady=8)
        for r in an:
            lv = level(r["avg"]); arrow = "🔺" if r["trend"] > 0.5 else "🔻" if r["trend"] < -0.5 else "➖"
            self.bar(s, f"{r['subject']}  {arrow}", r["avg"], 10, LV[lv], f"{r['avg']:.1f}/10 • {lv}")
        if an:
            wk = ctk.CTkFrame(s, fg_color="transparent"); wk.pack(fill="x", padx=14, pady=(8, 10))
            ctk.CTkLabel(wk, text="🎯 Pontos fracos:").pack(side="left")
            weak = [r["subject"] for r in an if r["avg"] < 6]
            for w in weak: chip(wk, w, LV[level(next(r["avg"] for r in an if r["subject"] == w))]).pack(side="left", padx=3)
            if not weak: ctk.CTkLabel(wk, text="nenhum, ótimo!", text_color=TEAL).pack(side="left", padx=6)
