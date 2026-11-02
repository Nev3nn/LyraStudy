"""Recorta as folhas de arte (art-source/*.png) em sprites WebP com fundo transparente.
Uso:  pip install pillow numpy scipy   &&   python tools/process_assets.py
Saída: assets/city/{buildings,cars,plazas}/*.webp  +  assets/city/meta.json (tamanhos e âncoras)."""
import json, os, sys
import numpy as np
from PIL import Image, ImageEnhance
from scipy import ndimage as ndi

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC, OUT = os.path.join(ROOT, "art-source"), os.path.join(ROOT, "assets", "city")

def mask_of(img, thr=13):
    """Remove o fundo escuro ajustando um gradiente quadrático nas bordas da folha."""
    a = np.asarray(img.convert("RGB")).astype(float); H, W, _ = a.shape
    yy, xx = np.mgrid[0:H, 0:W]; u, v = xx / W, yy / H
    X = np.stack([np.ones_like(u), u, v, u * u, v * v, u * v, u ** 3, v ** 3], -1).reshape(-1, 8)
    edge = np.zeros((H, W), bool); edge[:14] = edge[-14:] = True; edge[:, :14] = edge[:, -14:] = True
    bg = np.stack([(X @ np.linalg.lstsq(X[edge.ravel()], a[..., c].ravel()[edge.ravel()], rcond=None)[0]).reshape(H, W) for c in range(3)], -1)
    d = np.abs(a - bg).max(2)
    m = ndi.binary_closing(d > thr, iterations=2)
    return ndi.binary_fill_holes(m), d

def comps(img, min_area=2500, thr=28, group=True):
    """Detecta peças com um limiar ALTO (separa prédios ligados por brilho/sombra no chão); o recorte usa o limiar baixo."""
    _, d = mask_of(img, 13); m = ndi.binary_fill_holes(ndi.binary_closing(d > thr, iterations=1)); lab, n = ndi.label(m)
    objs = [(i, ndi.find_objects(lab)[i - 1], (lab == i).sum()) for i in range(1, n + 1)]
    # descarta ruído e legendas ("Level 1": blobs baixos e achatados); com agrupamento, min_area vale para o grupo inteiro
    objs = [o for o in objs if o[2] >= (300 if group else min_area) and (o[1][0].stop - o[1][0].start) > 22]
    # junta pedaços que se sobrepõem na horizontal (ex.: prédio + vegetação solta)
    groups = []
    for i, sl, _ in sorted(objs, key=lambda o: o[1][1].start):
        if not group: groups.append({"ids": [i], "x0": sl[1].start, "x1": sl[1].stop}); continue
        for g in groups:
            if sl[1].start < g["x1"] - 6 and sl[1].stop > g["x0"] + 6: g["ids"].append(i); g["x0"] = min(g["x0"], sl[1].start); g["x1"] = max(g["x1"], sl[1].stop); break
        else: groups.append({"ids": [i], "x0": sl[1].start, "x1": sl[1].stop})
    if group: groups = [g for g in groups if sum((lab == i).sum() for i in g["ids"]) >= min_area]
    return lab, d, groups

def cut(img, lab, d, ids, thr=13, lo=7):
    """Alpha = silhueta preenchida linha a linha, usando limiar BAIXO dentro de uma janela em volta da peça
    (as faces escuras dos prédios quase não contrastam com o fundo)."""
    core = np.isin(lab, ids); ys, xs = np.where(core); y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    win = np.zeros_like(core); win[max(0, y0 - 4):y1 + 6, max(0, x0 - 10):x1 + 10] = True
    low = ndi.binary_closing((d > lo) & win, iterations=2) | core
    span = np.zeros_like(core)
    for y in range(max(0, y0 - 4), min(core.shape[0], y1 + 6)):
        r = np.flatnonzero(low[y])
        if len(r): span[y, r.min():r.max() + 1] = True
    alpha = ndi.gaussian_filter(ndi.binary_erosion(span, iterations=1).astype(float), .8)
    yy, xx = np.where(alpha > .02); Y0, Y1, X0, X1 = yy.min(), yy.max() + 1, xx.min(), xx.max() + 1
    rgba = np.dstack([np.asarray(img.convert("RGB")), (alpha * 255).astype(np.uint8)])
    return Image.fromarray(rgba, "RGBA").crop((max(0, X0 - 2), max(0, Y0 - 2), X1 + 2, Y1 + 2))

def trim_base(im):
    """Recorta o retângulo escuro de sombra da base em formato de losango isométrico (2:1), alinhado ao lote."""
    a = np.asarray(im).copy(); H, W = a.shape[:2]
    band = a[int(H * .9):, :, 3] > 120; cols = np.where(band.any(0))[0]
    if not len(cols): return im
    bw = (cols.max() - cols.min() + 1) / 2 + 4; cx = (cols.max() + cols.min()) / 2; cy = H - bw / 2 - 1
    yy, xx = np.mgrid[0:H, 0:W]; outside = (np.abs(xx - cx) / bw + np.abs(yy - cy) / (bw / 2) > 1) & (yy > cy)
    a[..., 3] = np.where(outside, 0, a[..., 3]); return Image.fromarray(a, "RGBA")

def tint(im, shift, sat=1.5):
    r, g, b, a = im.split(); h, s, v = Image.merge("RGB", (r, g, b)).convert("HSV").split()
    h = h.point(lambda x: (x + shift) % 256)
    out = Image.merge("HSV", (h, s, v)).convert("RGB"); out = ImageEnhance.Color(out).enhance(sat)
    return Image.merge("RGBA", (*out.split(), a))

def colorize(im, rgb, amt=.5):
    """Tinge a carroceria (tons médios) mantendo brilho, faróis e janelas."""
    a = np.asarray(im).astype(float); lum = a[..., :3].mean(2, keepdims=True)
    w = np.clip(1 - np.abs(lum - 110) / 95, 0, 1) * amt
    tgt = lum / 110 * np.array(rgb, float)
    a[..., :3] = np.clip(a[..., :3] * (1 - w) + tgt * w, 0, 255)
    return Image.fromarray(a.astype(np.uint8), "RGBA")

def meta(im):
    a = np.asarray(im)[..., 3] > 120; H = a.shape[0]; band = a[int(H * .88):]
    cols = np.where(band.any(0))[0]; bw = int(cols.max() - cols.min() + 1) if len(cols) else im.width
    return {"w": im.width, "h": im.height, "bw": bw, "ax": round(float((cols.min() + cols.max()) / 2 / im.width), 3) if len(cols) else .5}

M = {}
def save(path, im):
    p = os.path.join(OUT, path + ".webp"); os.makedirs(os.path.dirname(p), exist_ok=True)
    im.save(p, "WEBP", quality=88, method=6); M[path] = meta(im); return M[path]

# ---- prédios: (id, folha, deslocamento de matiz) -> níveis = sprites da folha, do menor para o maior
BUILD = [("casa", "predio", 0), ("bib", "predio_2", 0), ("lab", "predio_5", 0), ("cow", "predio", 90), ("mus", "predio_2", 150),
         ("hub", "predio_5", 110), ("neo", "predio_3", 0), ("eco", "predio_4", 0), ("ony", "predio_3", 85), ("sol", "predio_4", -75)]
cache = {}
for bid, sheet, shift in BUILD:
    if sheet not in cache:
        img = Image.open(os.path.join(SRC, sheet + ".png")); lab, d, gr = comps(img)
        cache[sheet] = [cut(img, lab, d, g["ids"]) for g in gr]
    for lv, im in enumerate(cache[sheet], 1): save(f"buildings/{bid}_{lv}", trim_base(tint(im, shift) if shift else im))
    print(bid, sheet, "níveis:", len(cache[sheet]))

# ---- carros: 8 por folha (2 colunas x 4 linhas), ordenados por linha/coluna
CARS = [("car_a", "carros", 3, 0, None), ("car_b", "carros", 3, 1, None), ("car_c", "carros_2", 1, 0, (225, 45, 70)),
        ("car_d", "carros_2", 1, 1, (245, 185, 60)), ("car_e", "carros_2", 0, 1, None), ("car_f", "carros", 0, 0, (50, 205, 215))]
sheets = {}
for cid, sheet, row, col, shift in CARS:
    if sheet not in sheets:
        img = Image.open(os.path.join(SRC, sheet + ".png")); lab, d, gr = comps(img, 6000, 24, False)
        objs = sorted(gr, key=lambda g: (round(ndi.center_of_mass(np.isin(lab, g["ids"]))[0] / 192), ndi.center_of_mass(np.isin(lab, g["ids"]))[1]))
        sheets[sheet] = (img, lab, d, objs); print(sheet, "carros:", len(objs))
    img, lab, d, objs = sheets[sheet]; im = cut(img, lab, d, objs[row * 2 + col]["ids"], 13); save(f"cars/{cid}", colorize(im, shift) if shift else im)

# ---- praças
for n in (1, 2, 3):
    img = Image.open(os.path.join(SRC, f"praça_level_{n}.png")); lab, d, gr = comps(img, 3000, 14)
    ids = [i for g in gr for i in g["ids"]]; save(f"plazas/plaza_{n}", cut(img, lab, d, ids, 14))

with open(os.path.join(OUT, "meta.json"), "w") as f: json.dump(M, f, separators=(",", ":"))
print(len(M), "sprites gerados")
