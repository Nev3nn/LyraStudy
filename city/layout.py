"""Onde cada bloco aparece. Tudo é ALEATÓRIO, mas reprodutível: a posição vem de um sorteio com a semente da cidade,
então recarregar o app mantém o mapa igual.

Ano  = 12 blocões de 6x6 em grade compacta 4x3 (24x18) — sem buraco no meio. O mês escolhe um bloco ao acaso.
Mês  = 4 semanas de 3x3 em 2x2; a semana escolhe um quadrante ao acaso dentro do mês.
Sem. = 3x3 = 9 células: 7 dias + 2 sobras (viram praças). Os dias ocupam células sorteadas dentro da semana."""
import random
from functools import lru_cache

COLS, ROWS, MONTH, WEEK = 4, 3, 6, 3
YEAR_W, YEAR_H = COLS * MONTH, ROWS * MONTH

@lru_cache(maxsize=None)
def _perm(seed, key, n):
    a = list(range(n)); random.Random(f"{seed}:{key}").shuffle(a); return tuple(a)

def month_origin(seed, year, m):
    s = _perm(seed, ("m", year), COLS * ROWS)[m]; return (s % COLS) * MONTH, (s // COLS) * MONTH

def week_origin(seed, year, m, w):
    mx, my = month_origin(seed, year, m); s = _perm(seed, ("w", year, m), 4)[w]; return mx + (s % 2) * WEEK, my + (s // 2) * WEEK

def week_cell(seed, year, m, w, k):
    """k = 0..6 dias da semana; 7 e 8 = células de sobra (praças)."""
    wx, wy = week_origin(seed, year, m, w); c = _perm(seed, ("c", year, m, w), 9)[k]; return wx + c % 3, wy + c // 3

def day_cell(seed, year, j):
    return week_cell(seed, year, j // 28, (j % 28) // 7, j % 7)

def spare_cells(seed, year, m, w):
    return [week_cell(seed, year, m, w, 7), week_cell(seed, year, m, w, 8)]
