# Como inserir novos modelos de prédio

Os prédios são **dados**, não código: `assets/city/buildings.json` é gerado a partir de `art-source/buildings/` por
`python tools/process_assets.py`. Nada em `city/` precisa mudar.

## 1) Nomes dos arquivos
`art-source/buildings/nivel_<NÍVEL>-<LETRA>.png` — cada **letra** é um modelo; cada **nível** (1, 2, 3, 4…) é uma evolução dele.
Ex.: `nivel_1-f.png`, `nivel_2-f.png`, `nivel_3-f.png` = modelo "f" com 3 níveis (o máximo é o maior nível que existir).

## 2) `art-source/buildings/families.json`
```json
{ "f": { "id": "ind", "n": "Fábrica Retrô", "p": 1800 } }
```
`id` = prefixo do sprite (`assets/city/buildings/ind_1.webp`…), `n` = nome na loja, `p` = preço em pontos (0 = grátis).

## 3) Gerar
```
pip install -r requirements-dev.txt
python tools/process_assets.py
```
O script remove o fundo branco, recorta, mede a base de cada sprite (`meta.json`) e escreve `buildings.json`. Rode o app e o modelo já aparece na loja.
Saves antigos continuam abrindo: se um modelo some do catálogo, os prédios dele viram o modelo atual (`engine.sanitize`).

## 4) Especificação das imagens (para gerar com IA)
- **Fundo branco puro**, sem sombras fora do terreno; um único prédio centralizado, **retrato 512×768**.
- **Visão isométrica 2:1** (mesmo ângulo em TODOS os níveis e modelos); o prédio sobre o **próprio terreno em losango** (grama/pedra) — o losango
  é a base que encaixa no lote e na rua.
- A largura do losango deve ser parecida entre os níveis do mesmo modelo (o jogo escala pela largura da base); a **altura** cresce com o nível.
- Evolução sugerida: Nv1 simples e baixo → Nv2 mais andares/detalhes → Nv3 grande, com varandas/telhado especial → Nv4 ícone do modelo.
- Mantenha a paleta do modelo igual em todos os níveis.

### Modelo de prompt
> Isometric 2:1 voxel/pixel-art building, **<DESCRIÇÃO DO MODELO>**, evolution **level <N> of <MAX>** (<o que muda neste nível>), standing on its own diamond-shaped ground tile
> (<grama | calçada de pedra>), centered, pure white background, no cast shadow outside the tile, soft daylight, consistent camera angle with the previous levels, 512x768.

## 5) Praças e carros
Seguem o mesmo fluxo: `art-source/praça_level_N.png` (3 praças) e as folhas `carros*.png` (veja `CARS` em `tools/process_assets.py`).
