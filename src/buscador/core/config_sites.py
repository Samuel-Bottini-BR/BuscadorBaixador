# -*- coding: utf-8 -*-
"""Le chaves de API por site de um arquivo .ini local (buscador.local.cfg),
que nunca vai pro git. Nao lanca erro se o arquivo ou a chave nao existirem --
devolve None, e quem chamou decide o que fazer (normalmente levantar
AcaoHumanaNecessaria)."""
import configparser
from pathlib import Path

CAMINHO_PADRAO = Path(__file__).resolve().parent.parent.parent.parent / "buscador.local.cfg"


def ler_chave(site: str, chave: str = "chave_api", caminho: Path = CAMINHO_PADRAO) -> str | None:
    if not caminho.exists():
        return None
    config = configparser.ConfigParser()
    config.read(caminho, encoding="utf-8")
    return config.get(site, chave, fallback=None)
