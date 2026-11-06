"""Utilitários de formatação."""

def fmt_dur(minutes):
    """Minutos -> texto legível: 45 -> '45 min' • 60 -> '1h' • 150 -> '2h e 30 min' • 125 -> '2h e 5 min'."""
    m = int(round(minutes or 0)); h, r = divmod(max(m, 0), 60)
    if h == 0: return f"{r} min"
    return f"{h}h" if r == 0 else f"{h}h e {r} min"
