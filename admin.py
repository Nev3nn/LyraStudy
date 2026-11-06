"""Conta Admin (testes e depuração). A senha NÃO fica no código: no primeiro acesso você cria uma senha, que é guardada em
data["admin"] só como hash PBKDF2 com sal. Esqueceu? Apague a chave "admin" do data.json.
Logado, o Admin pode: adiantar horas de estudo (pontos + XP + níveis na hora) e avançar o calendário (dias, meses, anos) —
a data simulada vale para o app inteiro (relógio virtual em clock.py) e os dias avançados contam como metas cumpridas."""
import hashlib, hmac, secrets
from datetime import date
import clock
import customtkinter as ctk
from tkinter import messagebox
from rules import goal_min, PTS_PER_MIN
from storage import save
from theme import PRIMARY, GOLD, MUTED, RED, TEAL

ITER = 150_000

def _hash(pw, salt): return hashlib.pbkdf2_hmac("sha256", pw.encode("utf-8"), bytes.fromhex(salt), ITER).hex()
def has_password(d): return bool(d.get("admin", {}).get("hash"))
def set_password(d, pw):
    salt = secrets.token_hex(16); a = d.setdefault("admin", {}); a["salt"], a["hash"] = salt, _hash(pw, salt)
def verify(d, pw):
    a = d.get("admin", {}); return bool(a.get("hash")) and hmac.compare_digest(a["hash"], _hash(pw, a["salt"]))

# ---------- ações (puras: usadas pela interface e pelos testes) ----------
def add_study(app, minutes, subject="Geral"):
    """Simula horas de estudo agora: sessão do dia, pontos (10/min) e XP/níveis do prédio em foco, instantaneamente."""
    d, today = app.data, clock.today(); s = d["sessions"].setdefault(today.isoformat(), {"total": 0})
    s["total"] += minutes; s[subject] = s.get(subject, 0) + minutes; d["points"] += PTS_PER_MIN * minutes
    w = app.city_widget(); w.apply(w.city.study(minutes, today)); app.commit()

def add_points(app, n): app.data["points"] += n; app.commit()

def level_up(app, n):
    w = app.city_widget(); w.apply(w.city.level_up(n)); app.commit()

def advance_days(app, n, credit=True):
    """Avança o calendário n dias. credit=True: cada dia vira uma sessão que bate a meta (sem pontos) e entra na cidade."""
    d, w, g, ev = app.data, app.city_widget(), None, []; g = goal_min(d)
    for _ in range(n):
        clock.set_offset(clock.offset() + 1); t = clock.today()
        if credit and g > 0: d["sessions"][t.isoformat()] = {"total": g, "Geral": g, "sim": True}
        ev += w.city.check_day(t) + w.city.check_plazas(t)
    d.setdefault("admin", {})["offset"] = clock.offset(); d["last_checked"] = clock.today().isoformat(); d["streak_miss"] = 0   # sem penalidades pelos dias pulados
    w.apply(ev); app.commit()

def advance_to_next_month(app, credit=True):
    t = clock.today(); nxt = date(t.year + (t.month == 12), t.month % 12 + 1, 1); advance_days(app, (nxt - t).days, credit)

def restore_clock(app):
    """Volta ao relógio real e remove as sessões simuladas que ficaram no futuro."""
    d, real = app.data, date.today(); clock.set_offset(0); d.setdefault("admin", {})["offset"] = 0
    for k in [k for k, v in d["sessions"].items() if v.get("sim") and k > real.isoformat()]: del d["sessions"][k]
    save(d); app.commit()

def reset_city(app):
    """Zera a cidade (e as sessões simuladas) e volta ao relógio real."""
    d = app.data; d.pop("city", None)
    for k in [k for k, v in d["sessions"].items() if v.get("sim")]: del d["sessions"][k]
    clock.set_offset(0); d.setdefault("admin", {})["offset"] = 0; save(d); app.city_widget().reload(); app.commit()

# ---------- diálogos ----------
class LoginDialog(ctk.CTkToplevel):
    def __init__(self, master, app):
        super().__init__(master); self.app = app; first = not has_password(app.data)
        self.title("Conta Admin"); self.geometry("380x300" if first else "380x240"); self.transient(master.winfo_toplevel()); self.after(150, self.grab_set)
        ctk.CTkLabel(self, text="🔐 Conta Admin", font=("Segoe UI", 18, "bold"), text_color=GOLD).pack(pady=(18, 4))
        ctk.CTkLabel(self, text="Primeiro acesso: crie a senha do Admin." if first else "Digite a senha do Admin.", text_color=MUTED).pack()
        self.e1 = ctk.CTkEntry(self, width=240, show="•", placeholder_text="Senha"); self.e1.pack(pady=(14, 4)); self.e1.focus_set()
        self.e2 = None
        if first: self.e2 = ctk.CTkEntry(self, width=240, show="•", placeholder_text="Confirmar senha (mín. 6 caracteres)"); self.e2.pack(pady=4)
        self.err = ctk.CTkLabel(self, text="", text_color=RED); self.err.pack(pady=4)
        ctk.CTkButton(self, text="Criar e entrar" if first else "Entrar", command=self.go, **PRIMARY).pack(pady=6); self.bind("<Return>", lambda e: self.go())
    def go(self):
        d, pw = self.app.data, self.e1.get()
        if self.e2 is not None:
            if len(pw) < 6: return self.err.configure(text="Use ao menos 6 caracteres.")
            if pw != self.e2.get(): return self.err.configure(text="As senhas não conferem.")
            set_password(d, pw); save(d)
        elif not verify(d, pw): return self.err.configure(text="Senha incorreta.")
        self.destroy(); self.app.set_admin(True)

class AdminPanel(ctk.CTkToplevel):
    def __init__(self, master, app):
        super().__init__(master); self.app = app; self.title("Painel Admin"); self.geometry("460x640"); self.transient(master.winfo_toplevel())
        ctk.CTkLabel(self, text="🛠 Painel Admin", font=("Segoe UI", 18, "bold"), text_color=GOLD).pack(pady=(14, 2))
        self.lbl = ctk.CTkLabel(self, text="", text_color=MUTED); self.lbl.pack()
        box = ctk.CTkScrollableFrame(self); box.pack(fill="both", expand=True, padx=12, pady=8)
        def sec(t): f = ctk.CTkFrame(box); f.pack(fill="x", pady=5); ctk.CTkLabel(f, text=t, font=("Segoe UI", 14, "bold"), anchor="w").pack(fill="x", padx=12, pady=(8, 2)); r = ctk.CTkFrame(f, fg_color="transparent"); r.pack(fill="x", padx=8, pady=(0, 8)); return r
        def btn(r, txt, fn): ctk.CTkButton(r, text=txt, width=78, fg_color="gray30", command=lambda: (fn(), self.upd())).pack(side="left", padx=3, pady=2)
        r = sec("⏱ Adiantar horas de estudo (pontos + XP + níveis, na hora)"); self.subj = ctk.CTkOptionMenu(r, values=list(app.data["subjects"]) + ["Geral"]); self.subj.pack(side="left", padx=3)
        for txt, m in (("+15 min", 15), ("+1 h", 60), ("+5 h", 300), ("+10 h", 600)): btn(r, txt, lambda m=m: add_study(app, m, self.subj.get()))
        r = sec("⭐ Pontos e níveis")
        for txt, fn in (("+1000 pts", lambda: add_points(app, 1000)), ("+5000 pts", lambda: add_points(app, 5000)), ("+1 nível", lambda: level_up(app, 1)), ("Nível máx.", lambda: level_up(app, 9))): btn(r, txt, fn)
        r = sec("📅 Avançar o calendário"); self.credit = ctk.CTkCheckBox(r, text="Cumprir a meta nos dias avançados"); self.credit.select(); self.credit.pack(anchor="w", padx=6, pady=(0, 4))
        r2 = ctk.CTkFrame(r.master, fg_color="transparent"); r2.pack(fill="x", padx=8, pady=(0, 8))
        cr = lambda: bool(self.credit.get())
        for txt, fn in (("+1 dia", lambda: advance_days(app, 1, cr())), ("+7 dias", lambda: advance_days(app, 7, cr())), ("+1 mês", lambda: advance_to_next_month(app, cr())), ("+1 ano", lambda: advance_days(app, 365, cr()))): btn(r2, txt, fn)
        r = sec("↩ Relógio e cidade"); btn(r, "Relógio real", lambda: restore_clock(app))
        btn(r, "Reiniciar cidade", lambda: reset_city(app) if messagebox.askyesno("Reiniciar cidade", "Zerar a cidade e as sessões simuladas?") else None)
        ctk.CTkButton(self, text="Sair do modo Admin", fg_color=RED, command=lambda: (self.destroy(), app.set_admin(False))).pack(pady=8); self.upd()
    def upd(self):
        sim = clock.offset(); self.lbl.configure(text=f"Data do app: {clock.today():%d/%m/%Y}" + (f"  (simulada: +{sim} dias)" if sim else "  (relógio real)"))
