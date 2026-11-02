"""Lyra City — metrópole isométrica dentro da aba "Foco e Loja".

catalog  : catálogo (prédios, carros, praças), constantes urbanísticas e acesso aos sprites
layout   : posições (aleatórias porém reprodutíveis) de meses, semanas e dias no mapa
engine   : estado e regras (XP, níveis, fusões dia→semana→mês→ano, praças) — sem interface
traffic  : carros (ruas de mão única, redução de 20% do tráfego)
render   : desenho isométrico com Pillow (ordenação por profundidade, câmera, animações)
widget   : componente CustomTkinter que o FocusTab usa
panel    : painel de loja/configurações
"""
