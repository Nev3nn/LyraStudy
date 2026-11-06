"""Regras do app: cronograma, penalidades e reajuste por simulados."""
import clock
import calendar
from datetime import date, timedelta

DAYS = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]
PTS_PER_MIN = 10
DEV_BONUS = 5000  # atalho de desenvolvedor (Ctrl+Shift+P ou botão 🛠 na aba Foco)

def weekly_minutes(subjects, daily_h):
    """soma pesos -> horas/dia x 7 x 60 / soma = fator por ponto -> fator x peso (peso mínimo 1)."""
    w = {s: max(1, int(v)) for s, v in subjects.items()}
    total = sum(w.values())
    if not total:
        return {}
    base = daily_h * 7 * 60 / total
    return {s: round(base * v) for s, v in w.items()}

def build_schedule(subjects, daily_h, per_day=2):
    """Cada matéria aparece ao menos 1x/semana. Se há mais matérias que vagas (7 x por_dia), os dias
    'sobrando' recebem 1 matéria a mais, espaçados. Vagas extras vão para as matérias mais difíceis."""
    mins = weekly_minutes(subjects, daily_h); subs = list(mins)
    if not subs:
        return {d: [] for d in DAYS}
    w = {s: max(1, int(subjects[s])) for s in subs}
    slots = max(7 * max(1, min(per_day, len(subs))), len(subs))
    apps = {s: 1 for s in subs}
    for _ in range(slots - len(subs)):
        pool = [s for s in subs if apps[s] < 7]
        if not pool: break
        apps[max(pool, key=lambda s: w[s] / apps[s])] += 1
    base, extra = divmod(slots, 7)
    heavy = {int((j + 0.5) * 7 / extra) for j in range(extra)}
    cap = [base + (i in heavy) for i in range(7)]
    days = [[] for _ in range(7)]
    for s in sorted(subs, key=lambda s: (-apps[s], -w[s])):
        for _ in range(apps[s]):
            free = [i for i in range(7) if cap[i] > 0]
            if not free: break
            ok = [i for i in free if s not in days[i]] or free
            put = max(ok, key=lambda i: (min((min((i - j) % 7, (j - i) % 7) for j, x in enumerate(days) if s in x), default=7), cap[i]))
            days[put].append(s); cap[put] -= 1
    sched = {d: [] for d in DAYS}
    for s in subs:
        n = max(1, sum(x.count(s) for x in days)); chunk, rem = divmod(mins[s], n); first = True
        for i, x in enumerate(days):
            for _ in range(x.count(s)):
                sched[DAYS[i]].append({"subject": s, "minutes": chunk + (rem if first else 0)}); first = False
    return sched

def week_days():
    t = clock.today()
    mon = t - timedelta(t.weekday())
    return [mon + timedelta(i) for i in range(7)]

def studied(d, day, subj="total"):
    return d["sessions"].get(day.isoformat(), {}).get(subj, 0)

def goal_min(d):
    return int(d["daily_goal_h"] * 60)

def apply_penalties(d):
    """A partir do 2º dia seguido sem bater a meta, perde 50 pts x dias seguidos."""
    today, last = clock.today(), d.get("last_checked")
    d["last_checked"] = today.isoformat()
    if not last or not d["schedule"]:
        return
    day = date.fromisoformat(last)
    while day < today:
        if studied(d, day) >= goal_min(d):
            d["streak_miss"] = 0
        else:
            d["streak_miss"] += 1
            if d["streak_miss"] >= 2:
                loss = min(d["points"], 50 * d["streak_miss"])
                d["points"] -= loss
                d["penalty_log"].append({"date": day.isoformat(), "loss": loss, "streak": d["streak_miss"]})
        day += timedelta(1)

def sub_scores(sim):
    """Notas 0-10 por matéria (aceita o formato antigo, que já era 0-10)."""
    return {k: v["score"] for k, v in sim["subjects"].items()} if "subjects" in sim else dict(sim.get("scores", {}))

def overall(sim):
    if "score10" in sim: return sim["score10"]
    v = list(sub_scores(sim).values()); return sum(v) / len(v) if v else 0

def level(avg):
    return "crítico" if avg < 4 else "fraco" if avg < 6 else "ok" if avg < 8 else "forte"

def analyze(d, last=3):
    """Normaliza tudo para 0-10: média dos últimos simulados por matéria, tendência e nível. Mais fracas primeiro."""
    sims, out = d["simulados"][-last:], []
    for s in {k for x in sims for k in sub_scores(x)}:
        v = [sub_scores(x)[s] for x in sims if s in sub_scores(x)]
        out.append({"subject": s, "avg": sum(v) / len(v), "last": v[-1], "trend": v[-1] - v[-2] if len(v) > 1 else 0, "n": len(v)})
    return sorted(out, key=lambda r: r["avg"])

def propose_adjustment(d):
    """Pesos calculados ESTRITAMENTE a partir dos últimos 3 simulados (média 0-10 + tendência); o peso antigo não entra na conta."""
    new, changes = dict(d["subjects"]), []
    for r in analyze(d, 3):
        s = r["subject"]
        if s not in new: continue
        nw = max(1, min(5, int(5 - r["avg"] * 0.4 + (0.5 if r["trend"] <= -1.5 else -0.5 if r["trend"] >= 1.5 else 0) + 0.5)))
        if nw != new[s]: changes.append((s, new[s], nw, r["avg"], r["trend"]))
        new[s] = nw
    return new, changes, build_schedule(new, d["daily_goal_h"], d["per_day"])

def last3(d):
    return d["simulados"][-3:]

def reminder_due(d):
    """True se faz mais de 30 dias do último simulado (ou da criação do cronograma)."""
    last = d["simulados"][-1]["date"] if d["simulados"] else d.get("schedule_date")
    return bool(d["schedule"] and last and (clock.today() - date.fromisoformat(last)).days > 30)

def schedule_card(c, grade):
    """Espaçamento estilo Anki. grade: 0 Errei, 1 Difícil, 2 Bom, 3 Fácil."""
    if grade == 0:
        c["reps"], c["interval"] = 0, 0
        c["ease"] = max(1.3, c["ease"] - 0.2)
    else:
        c["ease"] = max(1.3, c["ease"] + (-0.15, 0, 0.15)[grade - 1])
        if c["reps"] == 0: iv = (1, 1, 3)[grade - 1]
        elif c["reps"] == 1: iv = (2, 4, 6)[grade - 1]
        else: iv = max(c["interval"] + 1, round(c["interval"] * c["ease"] * (0.8, 1, 1.3)[grade - 1]))
        c["interval"], c["reps"] = iv, c["reps"] + 1
    c["due"] = (clock.today() + timedelta(c["interval"])).isoformat()

def month_stats(d, y, m):
    today, g, n = clock.today(), goal_min(d), calendar.monthrange(y, m)[1]
    days = [(date(y, m, i), None if date(y, m, i) > today else studied(d, date(y, m, i))) for i in range(1, n + 1)]
    past = [x for _, x in days if x is not None]
    return {"days": days, "n": n, "goal": g, "elapsed": len(past), "studied": sum(past),
            "met": sum(x >= g for x in past), "half": sum(x >= g / 2 for x in past)}

def grade(d, y, m):
    """Nota 0-10 do mês: metas (40%), constância = dias com >=50% da meta (30%) e resultados = média dos 3 últimos simulados (30%)."""
    ms = month_stats(d, y, m)
    if not ms["elapsed"]: return {"score": 0.0, "metas": 0.0, "const": 0.0, "res": None}
    metas = min(1.0, ms["studied"] / (ms["goal"] * ms["elapsed"])) if ms["goal"] else 0.0
    const = ms["half"] / ms["elapsed"]
    sims = [s for s in d["simulados"] if s["date"] <= date(y, m, ms["n"]).isoformat()][-3:]
    res = sum(overall(s) for s in sims) / len(sims) / 10 if sims else None
    score = 10 * (0.4 * metas + 0.3 * const + 0.3 * res) if res is not None else 10 * (0.55 * metas + 0.45 * const)
    return {"score": round(score, 1), "metas": metas, "const": const, "res": res}

def streak(d):
    day, g, n = clock.today(), goal_min(d), 0
    if studied(d, day) < g: day -= timedelta(1)
    while g > 0 and studied(d, day) >= g: n += 1; day -= timedelta(1)
    return n
