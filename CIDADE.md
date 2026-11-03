# Lyra City dentro do Lyra Study

A cidade vive na aba **Foco e Loja** (`focus.py` → `city.widget.CityWidget`). Tudo é Python (CustomTkinter + Pillow), então
entra no mesmo `.exe` do PyInstaller. A antiga casa de móveis (`house.py`) foi removida.

```
city/
  catalog.py   catálogo (10 prédios, 6 carros, 3 praças), constantes urbanísticas e acesso aos sprites (_MEIPASS)
  layout.py    posições ALEATÓRIAS (mas reprodutíveis) de meses, semanas e dias
  engine.py    estado em data["city"] + regras: XP, níveis, fusões, praças, prédio aleatório, sincronização de dias
  traffic.py   carros (mão única, -20%, limitados pela área da região)
  render.py    desenho isométrico (Pillow): profundidade única, oclusão de carros, câmera, animações de fusão
  widget.py    componente Tk (canvas, mouse, laço de animação ~30 fps) • panel.py  loja e configurações
assets/city/   sprites WebP + meta.json (gerados por tools/process_assets.py a partir de art-source/)
art-source/    as 11 artes originais (predio*.png, carros*.png, cidade_vazia.png, praça_level_*.png)
```

## Ajustes pedidos
| Pedido | Onde |
|---|---|
| Ruas largas / prédios bem afastados | `catalog.py`: `STREET = 0.40` (antes 0,12) e `BLD_FILL = 0.78` (base do prédio = 0,47 da célula; antes 0,55) |
| Prédios aleatórios por mês e semana | `layout.py`: o mês sorteia 1 dos 12 blocões, a semana 1 de 4 quadrantes, o dia 1 de 9 células |
| Praças mais frequentes e aleatórias | `engine.geom()`: 2 praças por semana iniciada (as 2 células de sobra de cada semana, em posições sorteadas); estilo "aleatório" ou fixo na aba Praças |
| Prédio do dia aleatório | `engine.pick_building()` + chave "🎲 Prédio do dia aleatório" (aba Cidade) e botão 🎲 na fundação livre |
| Aba do Ano sem buraco | `layout.py` (grade compacta 4x3 de blocões de 6x6 = 24x18) e `engine.region()` |
| Prédios mudam de sprite por nível | `catalog.building_key()` escolhe o sprite pelo nível atual a cada quadro; selo "Nv x/y" e barra de XP sobre o prédio |
| Carros somem atrás dos prédios | `render.py`: carros e prédios na mesma ordenação por profundidade (+ re-colagem dos prédios que ficam à frente) |
| Tráfego -20% | `catalog.TRAFFIC = 0.8` |

## Regras de integração
- **Dia concluído** = meta diária do Lyra Study batida (`rules.goal_min`). Dias passados com a meta batida entram sozinhos ao abrir o app.
- **XP**: cada minuto de foco dá 4 XP ao prédio em foco (nível n → n+1 custa 100·n XP). Ao chegar ao máximo, o foco passa ao próximo prédio.
- **Moeda**: os pontos do Lyra Study (`data["points"]`).
- **Estado**: `data["city"]` dentro do `data.json` (a semente do mapa também fica lá).

## Revisão: travamento, câmera e cache
- **Causa do congelamento:** no laço antigo, com a aba oculta (o caso logo ao abrir o app) o código agendava o próximo quadro duas vezes
  (um `after` no ramo "oculto" e outro no `finally`), então o número de agendamentos dobrava a cada passada até travar a thread principal.
  Agora `CityWidget._tick` tem **um único ponto de agendamento**, id guardado em `_job` e cancelado em `destroy()`; valida `winfo_exists()`;
  usa 33 ms (50 ms se o quadro for pesado) e 100 ms com a aba oculta (sem desenhar); exceções no desenho não derrubam o laço.
- **Câmera fixa:** sem arrastar, sem zoom e sem easing. `Camera.fit()` enquadra e centraliza a região da visão uma vez (e de novo só se a
  visão ou o tamanho do canvas mudar, com debounce). O clique ainda seleciona um quadrado.
- **Cache de imagens:** `Renderer.sprite()` abre cada WebP uma vez; `scaled()` guarda cada tamanho; as escalas animadas (pop de prédio e entrada
  de carro) são quantizadas e os carros são pré-aquecidos (`prewarm`). Há um único `PhotoImage`, recriado só se o canvas mudar de tamanho.
  Teste: 120 quadros seguidos com 0 `Image.open` e 0 `resize`.
- **Medidas (ano completo, 336 dias, 19 carros):** ~2,5 ms por quadro parado e ~16 ms durante a fusão do ano.
