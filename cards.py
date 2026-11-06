import clock
import uuid
from copy import copy
from datetime import date
from tkinter import messagebox
import customtkinter as ctk
import images
from rules import schedule_card
from storage import save
from theme import PRIMARY, GOLD, TEAL, RED, VIOLET, EDGE, MUTED, header, chip, tag_color

GRADES = [("Errei", RED), ("Difícil", "#c98a3a"), ("Bom", TEAL), ("Fácil", "#4a90d9")]
NONE = "—"

class CardsTab(ctk.CTkFrame):
    def __init__(self, master, app):
        super().__init__(master, fg_color="transparent")
        self.app, self.mode, self.queue, self.show_ans = app, "Estudar", [], False
        self.f_sub, self.f_cat, self.last_sub, self.cm_subj = "Todas", "Todas", None, None
        self.reset_form()
        header(self, "🧠 Revisão", "flashcards com repetição espaçada")
        self.seg = ctk.CTkSegmentedButton(self, values=["Estudar", "Gerenciar", "Categorias"], command=self.set_mode)
        self.seg.pack(anchor="w")
        self.body = ctk.CTkFrame(self, fg_color="transparent"); self.body.pack(fill="both", expand=True, pady=8)

    # ---------- estado ----------
    def reset_form(self):
        self.editing, self.img, self.orig, self.fresh = None, {"q": None, "a": None}, {}, set()

    def discard(self):  # apaga imagens novas que não chegaram a ser salvas
        for n in self.fresh: images.remove(n)
        self.reset_form()

    def set_mode(self, m):
        if m != "Gerenciar": self.discard()
        self.mode = m; self.refresh()

    def get(self, cid):
        return next(c for c in self.app.data["cards"] if c["id"] == cid)

    def subjects(self):
        d = self.app.data
        return sorted({*d["subjects"], *(c["subject"] for c in d["cards"])})

    def cat_labels(self, subj):
        out = []
        for s, cs in self.app.data["categories"].items():
            if subj in ("Todas", s):
                for cat, subs in cs.items():
                    for lab in [cat] + [f"{cat} › {x}" for x in subs]:
                        if lab not in out: out.append(lab)
        return out

    def match(self, c):
        if self.f_sub not in ("Todas", c["subject"]): return False
        if self.f_cat == "Todas": return True
        cat, _, sub = self.f_cat.partition(" › ")
        return c.get("category") == cat and (not sub or c.get("sub") == sub)

    def refresh(self):
        self.seg.set(self.mode)
        today = clock.today().isoformat()
        due = [c for c in self.app.data["cards"] if c["due"] <= today and self.match(c)]
        self.queue = [c["id"] for c in sorted(due, key=lambda c: c["due"])]
        self.show_ans = False
        self.render()

    def render(self):
        for w in self.body.winfo_children(): w.destroy()
        {"Estudar": self.study, "Gerenciar": self.manage, "Categorias": self.cats_view}[self.mode]()

    # ---------- Estudar ----------
    def side(self, parent, text, img, font, color=None):
        if text: ctk.CTkLabel(parent, text=text, wraplength=560, font=font, text_color=color).pack(pady=(22, 6))
        im = images.load(img)
        if im: ctk.CTkLabel(parent, text="", image=im).pack(pady=6)

    def study(self):
        d = self.app.data; today = clock.today().isoformat()
        top = ctk.CTkFrame(self.body, fg_color="transparent"); top.pack(fill="x", pady=(0, 6))
        labs = ["Todas"] + self.cat_labels(self.f_sub)
        if self.f_cat not in labs: self.f_cat = "Todas"
        om = ctk.CTkOptionMenu(top, values=labs, command=self.set_fcat); om.set(self.f_cat); om.pack(side="right", padx=(6, 0))
        om = ctk.CTkOptionMenu(top, values=["Todas"] + self.subjects(), command=self.set_fsub); om.set(self.f_sub); om.pack(side="right")
        # barra lateral hierárquica: categoria > subcategoria, com cartões pendentes
        side = ctk.CTkScrollableFrame(self.body, width=190, label_text="Seções"); side.pack(side="left", fill="y", padx=(0, 8))
        due = [c for c in d["cards"] if c["due"] <= today and self.f_sub in ("Todas", c["subject"])]
        for lab in ["Todas"] + self.cat_labels(self.f_sub):
            cat, _, sub = lab.partition(" › ")
            n = sum(1 for c in due if lab == "Todas" or (c.get("category") == cat and (not sub or c.get("sub") == sub)))
            on = lab == self.f_cat
            ctk.CTkButton(side, text=("      └ " if sub else "") + f"{sub or cat} ({n})", anchor="w", height=28,
                          fg_color=VIOLET if on else "transparent", hover_color=EDGE,
                          text_color=None if (on or lab == "Todas") else tag_color(sub or cat),
                          command=lambda l=lab: self.set_fcat(l)).pack(fill="x", pady=1)
        main = ctk.CTkFrame(self.body, fg_color="transparent"); main.pack(side="left", fill="both", expand=True)
        if not self.queue:
            txt = "🎉 Tudo revisado por hoje!" if d["cards"] else "Você ainda não tem cartões.\nCrie o primeiro na aba Gerenciar."
            ctk.CTkLabel(main, text=txt, font=("Segoe UI", 18), text_color=MUTED).pack(expand=True); return
        c = self.get(self.queue[0])
        crumbs = ctk.CTkFrame(main, fg_color="transparent"); crumbs.pack(fill="x")
        for i, x in enumerate((c["subject"], c.get("category"), c.get("sub"))):  # etiquetas: matéria › categoria › subcategoria
            if x:
                if i: ctk.CTkLabel(crumbs, text="›", text_color=MUTED).pack(side="left")
                chip(crumbs, x, tag_color(x)).pack(side="left", padx=3)
        ctk.CTkLabel(crumbs, text=f"{len(self.queue)} para revisar", text_color=MUTED).pack(side="right")
        bar = ctk.CTkFrame(main, fg_color="transparent"); bar.pack(side="bottom", pady=8)
        card = ctk.CTkScrollableFrame(main, corner_radius=16); card.pack(fill="both", expand=True, pady=8)
        self.side(card, c["q"], c.get("q_img"), ("Segoe UI", 20, "bold"))
        if not self.show_ans:
            ctk.CTkButton(bar, text="Mostrar resposta", height=42, command=self.reveal, **PRIMARY).pack(); return
        ctk.CTkFrame(card, height=2, fg_color=EDGE).pack(fill="x", padx=30, pady=8)
        self.side(card, c["a"], c.get("a_img"), ("Segoe UI", 17), TEAL)
        for g, (name, col) in enumerate(GRADES):
            t = copy(c); schedule_card(t, g)
            when = "hoje" if t["interval"] == 0 else f"{t['interval']} d"
            ctk.CTkButton(bar, text=f"{name}\n{when}", fg_color=col, width=110, height=52,
                          command=lambda g=g: self.grade(g)).pack(side="left", padx=5)

    def set_fsub(self, v):
        self.f_sub = v; self.refresh()

    def set_fcat(self, v):
        self.f_cat = v; self.refresh()

    def reveal(self):
        self.show_ans = True; self.render()

    def grade(self, g):
        cid = self.queue.pop(0); schedule_card(self.get(cid), g)
        if g == 0: self.queue.append(cid)  # volta para o fim da fila desta sessão
        save(self.app.data); self.show_ans = False; self.render()

    # ---------- Gerenciar (criar / editar) ----------
    def fill_cats(self, cat=None, sub=None):
        cs = [NONE] + list(self.app.data["categories"].get(self.om_subj.get(), {}))
        self.om_cat.configure(values=cs); self.om_cat.set(cat if cat in cs else NONE); self.fill_subs(sub)

    def fill_subs(self, sub=None):
        ss = [NONE] + self.app.data["categories"].get(self.om_subj.get(), {}).get(self.om_cat.get(), [])
        self.om_sub.configure(values=ss); self.om_sub.set(sub if sub in ss else NONE)

    def upd_img(self):
        for s, lbl in self.img_lbl.items(): lbl.configure(text="✔" if self.img[s] else "—")

    def pick_img(self, side):
        n = images.pick()
        if not n: return
        self.clear_img(side, False); self.img[side] = n; self.fresh.add(n); self.upd_img()

    def clear_img(self, side, upd=True):
        old = self.img[side]
        if old in self.fresh: images.remove(old); self.fresh.discard(old)  # só apaga o que ainda não foi salvo
        self.img[side] = None
        if upd: self.upd_img()

    def manage(self):
        d = self.app.data; ed = self.get(self.editing) if self.editing else None
        subs = list(dict.fromkeys(list(d["subjects"]) + ([ed["subject"]] if ed else []))) or ["Geral"]
        f = ctk.CTkFrame(self.body); f.pack(fill="x")
        row = ctk.CTkFrame(f, fg_color="transparent"); row.pack(fill="x", padx=10, pady=(10, 4))
        self.om_subj = ctk.CTkOptionMenu(row, values=subs, width=150, command=lambda _: self.fill_cats()); self.om_subj.pack(side="left")
        self.om_cat = ctk.CTkOptionMenu(row, values=[NONE], width=150, command=lambda _: self.fill_subs()); self.om_cat.pack(side="left", padx=6)
        self.om_sub = ctk.CTkOptionMenu(row, values=[NONE], width=150); self.om_sub.pack(side="left")
        self.om_subj.set(ed["subject"] if ed else (self.last_sub if self.last_sub in subs else subs[0]))
        self.fill_cats(ed.get("category") if ed else None, ed.get("sub") if ed else None)
        ctk.CTkLabel(f, text="Pergunta (frente)", anchor="w").pack(fill="x", padx=10)
        self.q = ctk.CTkTextbox(f, height=55); self.q.pack(fill="x", padx=10, pady=(0, 4))
        ctk.CTkLabel(f, text="Resposta (verso)", anchor="w").pack(fill="x", padx=10)
        self.a = ctk.CTkTextbox(f, height=55); self.a.pack(fill="x", padx=10, pady=(0, 4))
        if ed: self.q.insert("1.0", ed["q"]); self.a.insert("1.0", ed["a"])
        ir = ctk.CTkFrame(f, fg_color="transparent"); ir.pack(fill="x", padx=10, pady=(0, 4))
        self.img_lbl = {}
        for side, txt in (("q", "frente"), ("a", "verso")):
            ctk.CTkButton(ir, text=f"🖼 Imagem da {txt}", width=150, fg_color="gray30", command=lambda s=side: self.pick_img(s)).pack(side="left")
            self.img_lbl[side] = ctk.CTkLabel(ir, text="", text_color=TEAL, width=24); self.img_lbl[side].pack(side="left")
            ctk.CTkButton(ir, text="✖", width=28, fg_color="gray30", command=lambda s=side: self.clear_img(s)).pack(side="left", padx=(0, 14))
        self.upd_img()
        r = ctk.CTkFrame(f, fg_color="transparent"); r.pack(fill="x", padx=10, pady=(0, 10))
        ctk.CTkButton(r, text="Salvar alterações" if ed else "Adicionar cartão", command=self.save_card, **PRIMARY).pack(side="left")
        if ed: ctk.CTkButton(r, text="Cancelar edição", fg_color="gray30", command=self.cancel_edit).pack(side="left", padx=6)
        self.msg = ctk.CTkLabel(r, text="", text_color=RED); self.msg.pack(side="left", padx=10)
        lst = ctk.CTkScrollableFrame(self.body, label_text=f"Seus cartões ({len(d['cards'])})"); lst.pack(fill="both", expand=True, pady=8)
        for c in sorted(d["cards"], key=lambda c: (c["subject"], c.get("category", ""), c["due"])):
            rw = ctk.CTkFrame(lst, fg_color="transparent"); rw.pack(fill="x")
            ctk.CTkButton(rw, text="🗑", width=32, fg_color="gray30", command=lambda i=c["id"]: self.delete(i)).pack(side="right", padx=2)
            ctk.CTkButton(rw, text="✏", width=32, fg_color="gray30", command=lambda i=c["id"]: self.edit(i)).pack(side="right")
            pic = " 🖼" if c.get("q_img") or c.get("a_img") else ""
            for x in (c["subject"], c.get("category"), c.get("sub")):
                if x: chip(rw, x, tag_color(x)).pack(side="left", padx=2)
            ctk.CTkLabel(rw, anchor="w", text=f" {c['q'][:45]}{pic}  •  {c['due']}").pack(side="left")

    def save_card(self):
        q, a = self.q.get("1.0", "end").strip(), self.a.get("1.0", "end").strip()
        if not (q or self.img["q"]) or not (a or self.img["a"]):
            return self.msg.configure(text="Frente e verso precisam de texto ou imagem.")
        cat, sub = self.om_cat.get(), self.om_sub.get()
        rec = {"subject": self.om_subj.get(), "category": "" if cat == NONE else cat, "sub": "" if sub == NONE else sub,
               "q": q, "a": a, "q_img": self.img["q"], "a_img": self.img["a"]}
        d = self.app.data
        if self.editing:
            for s in ("q", "a"):  # imagem trocada/removida na edição: apaga o arquivo antigo
                if self.orig.get(s) and self.orig[s] != self.img[s]: images.remove(self.orig[s])
            self.get(self.editing).update(rec)
        else:
            d["cards"].append({"id": uuid.uuid4().hex[:8], **rec, "due": clock.today().isoformat(), "interval": 0, "ease": 2.5, "reps": 0})
        self.last_sub = rec["subject"]; save(d); self.reset_form(); self.render()

    def edit(self, cid):
        self.discard(); c = self.get(cid); self.editing = cid
        self.img = {"q": c.get("q_img"), "a": c.get("a_img")}; self.orig = dict(self.img); self.render()

    def cancel_edit(self):
        self.discard(); self.render()

    def delete(self, cid):
        c = self.get(cid)
        images.remove(c.get("q_img")); images.remove(c.get("a_img"))
        self.app.data["cards"] = [x for x in self.app.data["cards"] if x["id"] != cid]
        if self.editing == cid: self.discard()
        save(self.app.data); self.render()

    # ---------- Categorias e subcategorias ----------
    def set_cm(self, v):
        self.cm_subj = v; self.render()

    def add_cat(self, e):
        n = e.get().strip()
        if not n: return
        self.app.data["categories"].setdefault(self.cm_subj, {}).setdefault(n, []); save(self.app.data); self.render()

    def add_sub(self, cat, e):
        n = e.get().strip(); subs = self.app.data["categories"][self.cm_subj][cat]
        if n and n not in subs: subs.append(n); save(self.app.data)
        self.render()

    def del_cat(self, cat):
        if not messagebox.askyesno("Remover categoria", f"Remover '{cat}' e suas subcategorias?\nOs cartões continuam existindo, só ficam sem categoria."): return
        del self.app.data["categories"][self.cm_subj][cat]
        for c in self.app.data["cards"]:
            if c["subject"] == self.cm_subj and c.get("category") == cat: c["category"] = c["sub"] = ""
        save(self.app.data); self.render()

    def del_sub(self, cat, sub):
        self.app.data["categories"][self.cm_subj][cat].remove(sub)
        for c in self.app.data["cards"]:
            if c["subject"] == self.cm_subj and c.get("category") == cat and c.get("sub") == sub: c["sub"] = ""
        save(self.app.data); self.render()

    def cats_view(self):
        d = self.app.data; subs = self.subjects() or ["Geral"]
        if self.cm_subj not in subs: self.cm_subj = subs[0]
        top = ctk.CTkFrame(self.body, fg_color="transparent"); top.pack(fill="x")
        om = ctk.CTkOptionMenu(top, values=subs, command=self.set_cm); om.set(self.cm_subj); om.pack(side="left")
        e = ctk.CTkEntry(top, width=220, placeholder_text="Nova categoria"); e.pack(side="left", padx=8)
        ctk.CTkButton(top, text="➕ Categoria", width=110, command=lambda: self.add_cat(e), **PRIMARY).pack(side="left")
        lst = ctk.CTkScrollableFrame(self.body, label_text=f"Categorias de {self.cm_subj}"); lst.pack(fill="both", expand=True, pady=8)
        cs = d["categories"].get(self.cm_subj, {})
        if not cs: ctk.CTkLabel(lst, text="Nenhuma categoria ainda. Crie a primeira acima.", text_color="gray70").pack(pady=20)
        count = lambda **k: sum(all(c.get(a) == b for a, b in k.items()) and c["subject"] == self.cm_subj for c in d["cards"])
        for cat, subs_ in cs.items():
            rw = ctk.CTkFrame(lst, fg_color="transparent"); rw.pack(fill="x", pady=(10, 0))
            chip(rw, cat, tag_color(cat)).pack(side="left")
            ctk.CTkLabel(rw, text=f"  {count(category=cat)} cartão(ões)", text_color=MUTED).pack(side="left")
            ctk.CTkButton(rw, text="🗑", width=32, fg_color="gray30", command=lambda c=cat: self.del_cat(c)).pack(side="right")
            se = ctk.CTkEntry(rw, width=150, placeholder_text="Subcategoria")
            ctk.CTkButton(rw, text="➕", width=32, command=lambda c=cat, x=se: self.add_sub(c, x)).pack(side="right", padx=4)
            se.pack(side="right")
            for s in subs_:
                r2 = ctk.CTkFrame(lst, fg_color="transparent"); r2.pack(fill="x")
                ctk.CTkLabel(r2, text="      └", text_color=MUTED).pack(side="left")
                chip(r2, s, tag_color(s)).pack(side="left", padx=4)
                ctk.CTkLabel(r2, text=str(count(category=cat, sub=s)), text_color=MUTED).pack(side="left")
                ctk.CTkButton(r2, text="🗑", width=28, fg_color="gray30", command=lambda c=cat, x=s: self.del_sub(c, x)).pack(side="right")
