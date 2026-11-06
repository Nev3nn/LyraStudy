"""Aba PDFs: explorador de pastas. Navegue entre pastas (abrir/entrar/voltar/trilha), crie e remova pastas em qualquer nível,
mova PDFs entre pastas e marque cada PDF como "Estudado". As pastas das matérias do cronograma são criadas automaticamente na raiz."""
import os, re, sys, shutil, subprocess, unicodedata
from datetime import datetime
from tkinter import messagebox
import customtkinter as ctk
from storage import BASE, save
from theme import PRIMARY, TEAL, MUTED, EDGE, GOLD, header, tag_color, animate

FOLDER = os.path.join(BASE, "PDFs")
OLD = os.path.join(BASE, "Aulas")      # nome antigo: migrado automaticamente
TRASH = "_Removidas"

def open_file(path):
    if sys.platform.startswith("win"): os.startfile(path)
    else: subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", path])

def fmt(n):
    for u in ("B", "KB", "MB"):
        if n < 1024: return f"{n:.1f} {u}"
        n /= 1024
    return f"{n:.1f} GB"

def slug(name):  # "Matemática" -> "Matematica"
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return re.sub(r"[^\w\- ]", "", s).strip() or "Materia"

def count_pdfs(path):
    return sum(1 for _, _, fs in os.walk(path) for f in fs if f.lower().endswith(".pdf"))

def listing(path, root=False):
    """([(pasta, nº de PDFs dentro, recursivo)], [(pdf, tamanho)]) de um diretório."""
    folders, files = [], []
    for e in sorted(os.listdir(path), key=str.lower):
        p = os.path.join(path, e)
        if os.path.isdir(p) and not (root and e.startswith("_")): folders.append((e, count_pdfs(p)))
        elif e.lower().endswith(".pdf"): files.append((e, os.path.getsize(p)))
    return folders, files

def ensure(subjects, skip=()):
    """Garante PDFs/ e uma pasta por matéria (menos as removidas pelo usuário). Retorna {pasta: nome da matéria}."""
    if os.path.isdir(OLD) and not os.path.exists(FOLDER): os.rename(OLD, FOLDER)
    os.makedirs(FOLDER, exist_ok=True); names = {slug(s): s for s in subjects}
    for k in names:
        if k not in skip: os.makedirs(os.path.join(FOLDER, k), exist_ok=True)
    return names

def all_dirs():
    """Todas as pastas (caminhos relativos) para o diálogo de mover; '' = raiz."""
    out = [""]
    for r, ds, _ in os.walk(FOLDER):
        ds[:] = sorted(d for d in ds if not (r == FOLDER and d.startswith("_")))
        out += [os.path.relpath(os.path.join(r, d), FOLDER).replace("\\", "/") for d in ds]
    return out

class MoveDialog(ctk.CTkToplevel):
    """Escolhe a pasta de destino e move o PDF."""
    def __init__(self, master, tab, rel):
        super().__init__(master); self.title("Mover PDF"); self.geometry("420x190"); self.transient(master.winfo_toplevel()); self.after(150, self.grab_set)
        ctk.CTkLabel(self, text=f"Mover “{os.path.basename(rel)}” para:", wraplength=380).pack(pady=(16, 6))
        opts = {("📚 PDFs (raiz)" if d == "" else "📁 " + d): d for d in all_dirs()}; om = ctk.CTkOptionMenu(self, values=list(opts), width=340); om.pack(pady=4)
        def go():
            dest = os.path.join(FOLDER, opts[om.get()], os.path.basename(rel)); src = os.path.join(FOLDER, rel)
            if os.path.abspath(dest) != os.path.abspath(src):
                if os.path.exists(dest): return messagebox.showwarning("Mover PDF", "Já existe um arquivo com esse nome na pasta de destino.")
                shutil.move(src, dest); new = os.path.relpath(dest, FOLDER).replace("\\", "/"); done = tab.app.data["pdf_done"]
                if tab.is_done(rel): done[:] = [x for x in done if x not in (rel, "/" + rel)] + [new]; save(tab.app.data)
            self.destroy(); tab.refresh()
        ctk.CTkButton(self, text="Mover", command=go, **PRIMARY).pack(pady=12)

class LibraryTab(ctk.CTkFrame):
    def __init__(self, master, app):
        super().__init__(master, fg_color="transparent")
        self.app, self.rel, self.sig, self.keys, self._job = app, [], None, [], None
        header(self, "📚 PDFs", "seu explorador de materiais, pasta por pasta")
        top = ctk.CTkFrame(self, fg_color="transparent"); top.pack(fill="x")
        self.count = ctk.CTkLabel(top, text="", text_color=TEAL); self.count.pack(side="left", padx=8)
        for text, cmd, kw in [("Atualizar", self.refresh, {}), ("📂 Abrir no sistema", lambda: open_file(self.cwd()), dict(fg_color="gray30")), ("➕ Pasta", self.add_folder, PRIMARY), ("⬆ Voltar", self.up, dict(fg_color="gray30"))]:
            ctk.CTkButton(top, text=text, width=90, command=cmd, **kw).pack(side="right", padx=3)
        self.crumbs = ctk.CTkFrame(self, fg_color="transparent"); self.crumbs.pack(fill="x", pady=(6, 2))
        self.pbar = ctk.CTkProgressBar(self, height=8, progress_color=TEAL); self.pbar.set(0); self.pbar.pack(fill="x", padx=8, pady=(2, 4))
        self.grid_f = ctk.CTkScrollableFrame(self); self.grid_f.pack(fill="both", expand=True, pady=(0, 8))
        for c in range(3): self.grid_f.columnconfigure(c, weight=1, uniform="c")
        self._job = self.after(200, self.watch)

    # ---------- navegação ----------
    def cwd(self): return os.path.join(FOLDER, *self.rel)
    def data(self):
        d = self.app.data; names = ensure(d["subjects"], d["skip_folders"])
        if not os.path.isdir(self.cwd()): self.rel = []                       # pasta atual foi apagada por fora
        folders, files = listing(self.cwd(), root=not self.rel); return names, folders, files
    def enter(self, name): self.rel.append(name); self.refresh()
    def up(self):
        if self.rel: self.rel.pop(); self.refresh()
    def goto(self, depth): self.rel = self.rel[:depth]; self.refresh()
    def label(self, names, depth):   # nome amigável: pastas de matéria na raiz mostram o nome da matéria (com acento)
        n = self.rel[depth]; return names.get(n, n) if depth == 0 else n
    def is_done(self, key): return key in self.app.data["pdf_done"] or "/" + key in self.app.data["pdf_done"]

    def watch(self):  # monitora a pasta aberta a cada 3 s; UM único agendamento e só enquanto o widget existir
        self._job = None
        if not self.winfo_exists(): return
        try:
            if self.sig != self.data(): self.refresh()
        except Exception: pass
        if self.winfo_exists(): self._job = self.after(3000, self.watch)
    def destroy(self):
        if self._job is not None:
            try: self.after_cancel(self._job)
            except Exception: pass
        super().destroy()

    # ---------- ações ----------
    def add_folder(self):
        n = ctk.CTkInputDialog(text=f"Nome da nova pasta em “{self.rel[-1] if self.rel else 'PDFs'}”:", title="Nova pasta").get_input()
        if not n or not n.strip(): return
        k = slug(n); os.makedirs(os.path.join(self.cwd(), k), exist_ok=True)
        if not self.rel: d = self.app.data; d["skip_folders"] = [x for x in d["skip_folders"] if x != k]; save(d)
        self.refresh()
    def remove_folder(self, name):
        path = os.path.join(self.cwd(), name); n = count_pdfs(path)
        if not messagebox.askyesno("Remover pasta", f"Remover a pasta “{name}” ({n} PDF(s))?\n\nEla será movida para PDFs\\{TRASH}, sem apagar seus arquivos."): return
        trash = os.path.join(FOLDER, TRASH); os.makedirs(trash, exist_ok=True)
        dest = os.path.join(trash, "_".join(self.rel + [name]))
        if os.path.exists(dest): dest += datetime.now().strftime("_%Y%m%d%H%M%S")
        shutil.move(path, dest)
        if not self.rel and name not in self.app.data["skip_folders"]: self.app.data["skip_folders"].append(name); save(self.app.data)   # pasta de matéria não volta sozinha
        self.refresh()
    def toggle(self, key, var, card):
        done = self.app.data["pdf_done"]; done[:] = [x for x in done if x not in (key, "/" + key)]
        if var.get(): done.append(key)
        card.configure(border_color=TEAL if var.get() else "gray25"); save(self.app.data); self.update_count()
    def update_count(self):
        n = sum(self.is_done(k) for k in self.keys); self.count.configure(text=f"✅ {n}/{len(self.keys)} estudados nesta pasta")
        animate(self.pbar, n / len(self.keys) if self.keys else 0, 500, True)

    # ---------- tela ----------
    def refresh(self):
        names, folders, files = self.sig = self.data()
        for w in self.crumbs.winfo_children(): w.destroy()
        parts = ["📚 PDFs"] + [self.label(names, i) for i in range(len(self.rel))]
        for i, p in enumerate(parts):
            if i: ctk.CTkLabel(self.crumbs, text="›", text_color=MUTED).pack(side="left")
            ctk.CTkButton(self.crumbs, text=p, width=10, height=26, fg_color="transparent" if i < len(parts) - 1 else EDGE, hover_color=EDGE, command=lambda d=i: self.goto(d)).pack(side="left", padx=2)
        for w in self.grid_f.winfo_children(): w.destroy()
        items = [("dir", n, c) for n, c in folders] + [("pdf", n, s) for n, s in files]; self.keys = ["/".join(self.rel + [n]) for n, _ in files]
        if not items: ctk.CTkLabel(self.grid_f, text="Pasta vazia.\nColoque PDFs aqui ou crie subpastas com “➕ Pasta”.", text_color=MUTED).grid(row=0, column=0, columnspan=3, pady=40)
        for i, (kind, name, extra) in enumerate(items):
            card = ctk.CTkFrame(self.grid_f, corner_radius=12, border_width=2, border_color="gray25"); card.grid(row=i // 3, column=i % 3, padx=6, pady=6, sticky="nsew")
            shown = names.get(name, name) if (kind == "dir" and not self.rel) else name; col = tag_color(shown)
            ctk.CTkFrame(card, height=5, corner_radius=3, fg_color=col).pack(fill="x", padx=14, pady=(10, 0))
            if kind == "dir":
                ctk.CTkLabel(card, text="📁 " + shown, wraplength=210, font=("Segoe UI", 14, "bold")).pack(padx=10, pady=(8, 2)); ctk.CTkLabel(card, text=f"{extra} PDF(s)", text_color=MUTED).pack()
                r = ctk.CTkFrame(card, fg_color="transparent"); r.pack(fill="x", padx=12, pady=12)
                ctk.CTkButton(r, text="Abrir pasta", command=lambda n=name: self.enter(n), **PRIMARY).pack(side="left", fill="x", expand=True)
                ctk.CTkButton(r, text="🗑", width=34, fg_color="gray30", command=lambda n=name: self.remove_folder(n)).pack(side="left", padx=(6, 0))
            else:
                key = "/".join(self.rel + [name]); on = self.is_done(key); card.configure(border_color=TEAL if on else "gray25")
                ctk.CTkLabel(card, text="📄 " + name, wraplength=210, font=("Segoe UI", 14, "bold")).pack(padx=10, pady=(8, 2)); ctk.CTkLabel(card, text=fmt(extra), text_color=MUTED).pack()
                var = ctk.BooleanVar(value=on); ctk.CTkCheckBox(card, text="Estudado", variable=var, command=lambda a=key, v=var, c=card: self.toggle(a, v, c)).pack(pady=(8, 0))
                r = ctk.CTkFrame(card, fg_color="transparent"); r.pack(fill="x", padx=12, pady=12)
                ctk.CTkButton(r, text="Abrir PDF", command=lambda p=os.path.join(self.cwd(), name): open_file(p), **PRIMARY).pack(side="left", fill="x", expand=True)
                ctk.CTkButton(r, text="📁", width=34, fg_color="gray30", command=lambda k=key: MoveDialog(self, self, k)).pack(side="left", padx=(6, 0))
        self.update_count()
