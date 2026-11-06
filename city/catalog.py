"""Catálogo da cidade, constantes urbanísticas e localização dos sprites (funciona no código e no .exe do PyInstaller)."""
import json, os, sys

def resource(*parts):
    """Pasta de recursos somente-leitura: _MEIPASS (PyInstaller --onefile) ou a raiz do projeto."""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(base, *parts)

ASSETS = resource("assets", "city")
_META = None

def meta():
    """Tamanho, largura da base (bw) e âncora (ax) de cada sprite — gerado por tools/process_assets.py."""
    global _META
    if _META is None:
        with open(os.path.join(ASSETS, "meta.json"), encoding="utf-8") as f: _META = json.load(f)
    return _META

def sprite_path(key):
    return os.path.join(ASSETS, *key.split("/")) + ".webp"

# ---- urbanismo (ajuste aqui o respiro visual do mapa) ----
STREET = 0.40            # largura das ruas, em células (antes: 0,12 — agora ~3x mais larga)
LOT = 1 - STREET         # lado do lote que sobra dentro de cada célula
BLD_FILL = 0.90          # fração do lote ocupada pela PLATAFORMA do sprite do prédio (o sprite já inclui o terreno)
FRAME_MS, HEAVY_MS, IDLE_MS = 33, 50, 100   # laço de desenho: ~30 fps; 20 fps se o quadro for pesado; 10 verificações/s com a aba oculta
PER = 336                # dias por ano (12 meses x 4 semanas x 7 dias)
XP_PER_MIN = 4           # XP do prédio em foco por minuto estudado
TRAFFIC = 0.8            # tráfego 20% menor

def _models():
    """Prédios vêm de assets/city/buildings.json (gerado por tools/process_assets.py a partir de art-source/buildings/).
    Para ADICIONAR um modelo novo basta incluir os PNGs + a letra em art-source/buildings/families.json e rodar o script."""
    try:
        with open(os.path.join(ASSETS, "buildings.json"), encoding="utf-8") as f: return json.load(f)["models"]
    except (OSError, ValueError, KeyError): return []
BLD = [dict(id=m["id"], n=m["n"], p=m["p"], max=m["max"]) for m in _models()]   # preço 0 = grátis

CAR = [dict(id=a[0], n=a[1], p=a[2]) for a in (
    ("car_a", "Sedan Urbano", 0), ("car_b", "Furgão Escolar", 0), ("car_c", "Esportivo GT", 600),
    ("car_d", "Esportivo RS", 900), ("car_e", "SUV Executivo", 1300), ("car_f", "Elétrico de Luxo", 2000))]
# Praças: metas do CICLO MENSAL (reiniciam todo mês). kind "h" = horas estudadas no mês; "d" = dias concluídos no mês.
PLZ = [dict(id="plaza_1", n="Praça dos Bancos", kind="h", need=1), dict(id="plaza_2", n="Praça da Fonte", kind="d", need=1),
       dict(id="plaza_3", n="Praça Jardim Real", kind="d", need=7)]
PLAZA_EVERY, PLAZA_MIN_UNLOCKED = 5, 2    # com 2+ praças liberadas no mês, surge uma praça nova ao acaso a cada 5 dias concluídos
ROAD_W = 0.34                              # largura do asfalto (dentro da rua de STREET = 0,40)
VIEWS = [("dia", "Dia"), ("sem", "Semana"), ("mes", "Mês"), ("ano", "Ano")]

def bld(i): return next(b for b in BLD if b["id"] == i)
def car(i): return next(c for c in CAR if c["id"] == i)
def plz(i): return next(p for p in PLZ if p["id"] == i)

def building_key(bid, lv):
    """Sprite do prédio conforme o NÍVEL atual (cai para o maior nível existente se faltar algum arquivo)."""
    m = meta(); b = bld(bid)
    for l in range(min(lv, b["max"]), 0, -1):
        if f"buildings/{bid}_{l}" in m: return f"buildings/{bid}_{l}"
    return None
