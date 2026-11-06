import clock
from util import fmt_dur
import calendar
from datetime import date
import customtkinter as ctk
from rules import month_stats, grade, level
from theme import GOLD, TEAL, RED, VIOLET, MUTED, EDGE, INK, LV, tag_color, count_up

MESES = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
C_NONE, C_HALF, C_FUT = "#4a2f3a", "#8a6d2a", "#1b2038"

hm = fmt_dur   # 150 min -> "2h e 30 min"

def build(tab):
    d = tab.app.data; y, m = tab.month; ms = month_stats(d, y, m); gr = grade(d, y, m)

    def go(delta):
        mm, yy = m + delta, y
        if mm == 0: mm, yy = 12, y - 1
        if mm == 13: mm, yy = 1, y + 1
        tab.month = (yy, mm); tab.refresh()
    nav = ctk.CTkFrame(tab.body, fg_color="transparent"); nav.pack(fill="x", pady=(0, 4))
    ctk.CTkButton(nav, text="◀", width=36, command=lambda: go(-1)).pack(side="left")
    ctk.CTkLabel(nav, text=f"{MESES[m - 1]} {y}", font=("Segoe UI", 18, "bold"), width=220).pack(side="left", padx=10)
    ctk.CTkButton(nav, text="▶", width=36, command=lambda: go(1)).pack(side="left")

    goal_total, expected = ms["goal"] * ms["n"], ms["goal"] * ms["elapsed"]
    tab.kpis([("⏱", 0, "estudado no mês", TEAL, "", hm(ms["studied"])),
              ("🎯", 0, "meta do mês", GOLD, "", hm(goal_total)),
              ("✅", ms["met"], f"dias com meta batida (de {ms['elapsed']})", VIOLET, "{:.0f}"),
              ("🏅", gr["score"], "nota do mês (0 a 10)", LV[level(gr["score"])], "{:.1f}")])

    s = tab.section("Progresso acumulado do mês")
    tab.bar(s, "Acumulado", ms["studied"], goal_total, GOLD, f"{hm(ms['studied'])} de {hm(goal_total)}")
    diff = ms["studied"] - expected
    tab.bar(s, "Ritmo até hoje", ms["studied"], expected, TEAL if diff >= 0 else RED,
            f"{'+' if diff >= 0 else '-'}{hm(abs(diff))} {'à frente' if diff >= 0 else 'atrás'} da meta")
    ctk.CTkLabel(s, text="", height=4).pack()

    s = tab.section("Nota do mês")
    big = ctk.CTkLabel(s, text="0.0", font=("Segoe UI", 46, "bold"), text_color=LV[level(gr["score"])]); big.pack()
    count_up(big, gr["score"], "{:.1f}")
    ctk.CTkLabel(s, text="de 10  •  metas 40% · constância 30% · resultados 30%", text_color=MUTED).pack(pady=(0, 6))
    tab.bar(s, "Cumprimento de metas", gr["metas"] * 10, 10, GOLD, f"{gr['metas'] * 10:.1f}/10")
    tab.bar(s, "Constância (dias com ≥ 50% da meta)", gr["const"] * 10, 10, VIOLET, f"{gr['const'] * 10:.1f}/10")
    if gr["res"] is None:
        ctk.CTkLabel(s, text="Resultados: sem simulados (peso redistribuído entre metas e constância)", text_color=MUTED, anchor="w").pack(fill="x", padx=14, pady=(4, 10))
    else:
        tab.bar(s, "Resultados (3 últimos simulados)", gr["res"] * 10, 10, TEAL, f"{gr['res'] * 10:.1f}/10")

    s = tab.section("Calendário de estudo")
    grid = ctk.CTkFrame(s, fg_color="transparent"); grid.pack(pady=(0, 6))
    for i, n in enumerate(["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]):
        ctk.CTkLabel(grid, text=n, text_color=MUTED, width=44).grid(row=0, column=i)
    mins = {day.day: v for day, v in ms["days"]}
    for r, week in enumerate(calendar.monthcalendar(y, m), 1):
        for c, day in enumerate(week):
            if not day: continue
            v, g = mins[day], ms["goal"]
            col = C_FUT if v is None else TEAL if v >= g else C_HALF if v >= g / 2 else C_NONE
            if date(y, m, day) == clock.today() and col != TEAL: col = VIOLET
            ctk.CTkLabel(grid, text=str(day), width=40, height=30, corner_radius=8, fg_color=col,
                         text_color=INK if col == TEAL else "white").grid(row=r, column=c, padx=2, pady=2)
    lg = ctk.CTkFrame(s, fg_color="transparent"); lg.pack(pady=(0, 10))
    for t, col in (("Meta batida", TEAL), ("≥ 50%", C_HALF), ("Sem estudo", C_NONE), ("Hoje", VIOLET)):
        ctk.CTkLabel(lg, text=f"  {t}  ", fg_color=col, corner_radius=8, height=22, text_color=INK if col == TEAL else "white").pack(side="left", padx=4)

    per = {}
    for day, _ in ms["days"]:
        for k, x in d["sessions"].get(day.isoformat(), {}).items():
            if k != "total": per[k] = per.get(k, 0) + x
    s = tab.section("Tempo por matéria no mês")
    if not per: ctk.CTkLabel(s, text="Nenhum estudo registrado neste mês.", text_color=MUTED).pack(pady=(0, 12))
    top = max(per.values(), default=1)
    for k, v in sorted(per.items(), key=lambda x: -x[1]): tab.bar(s, k, v, top, tag_color(k), hm(v))
    ctk.CTkLabel(s, text="", height=4).pack()
