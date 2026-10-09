# -*- coding: utf-8 -*-
from pathlib import Path

from PIL import Image

ASSETS = Path(__file__).resolve().parent.parent / "assets"


def test_icone_png_e_ico_existem_e_abrem():
    assert Image.open(ASSETS / "livro.png").size == (256, 256)
    ico = Image.open(ASSETS / "livro.ico")
    assert (16, 16) in ico.info["sizes"] and (256, 256) in ico.info["sizes"]
