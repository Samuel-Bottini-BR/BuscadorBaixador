# -*- coding: utf-8 -*-
"""Desenha o ícone do app (um livro aberto) e salva assets/livro.png e
assets/livro.ico. Rode de novo se quiser mudar cores/formato:

    .venv\\Scripts\\python.exe scripts\\gerar_icone.py

Desenha em tamanho grande (1024) e reduz no fim -- assim as bordas ficam lisas.
"""
from pathlib import Path

from PIL import Image, ImageDraw

RAIZ = Path(__file__).resolve().parent.parent
VERDE = (36, 90, 71)        # verde do app (#245a47)
VERDE_ESCURO = (24, 62, 49)
CREME = (250, 244, 228)
LINHA = (196, 186, 160)
VINHO = (140, 32, 44)       # fita marcadora

G = 1024  # tamanho de trabalho


def desenhar() -> Image.Image:
    img = Image.new("RGBA", (G, G), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    # fundo: quadrado verde de cantos arredondados
    d.rounded_rectangle((40, 40, G - 40, G - 40), radius=210, fill=VERDE)

    meio = G // 2
    topo, base = 300, 760
    # capa (sombra escura atrás das páginas)
    d.polygon([(150, topo + 40), (meio, topo + 90), (G - 150, topo + 40),
               (G - 150, base + 40), (meio, base + 80), (150, base + 40)], fill=VERDE_ESCURO)
    # página da esquerda e da direita (levemente curvadas no meio)
    d.polygon([(185, topo), (meio - 12, topo + 60), (meio - 12, base + 45), (185, base)], fill=CREME)
    d.polygon([(G - 185, topo), (meio + 12, topo + 60), (meio + 12, base + 45), (G - 185, base)], fill=CREME)
    # linhas de texto nas páginas
    for i in range(6):
        y = topo + 95 + i * 62
        d.line([(235, y), (meio - 60, y + 38)], fill=LINHA, width=18)
        d.line([(G - 235, y), (meio + 60, y + 38)], fill=LINHA, width=18)
    # fita marcadora saindo por baixo, no meio
    d.polygon([(meio + 70, topo + 75), (meio + 130, topo + 85), (meio + 130, base + 150),
               (meio + 100, base + 120), (meio + 70, base + 150)], fill=VINHO)
    return img


def main() -> None:
    pasta = RAIZ / "assets"
    pasta.mkdir(exist_ok=True)
    grande = desenhar()
    grande.resize((256, 256), Image.LANCZOS).save(pasta / "livro.png")
    grande.resize((256, 256), Image.LANCZOS).save(
        pasta / "livro.ico", sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print(f"Ícone salvo em {pasta}")


if __name__ == "__main__":
    main()
