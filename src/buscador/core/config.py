# -*- coding: utf-8 -*-
"""Le a chave da API da DDB de fora do codigo (variavel de ambiente ou
arquivo local, nunca hardcoded -- CLAUDE.md, secao 5)."""
import configparser
import os
from pathlib import Path

RAIZ_PROJETO = Path(__file__).resolve().parents[3]
ARQUIVO_CONFIG_LOCAL = RAIZ_PROJETO / "buscador.local.cfg"


class ConfigError(Exception):
    pass


def obter_ddb_api_key():
    chave = os.environ.get("DDB_API_KEY")
    if chave:
        return chave

    if ARQUIVO_CONFIG_LOCAL.exists():
        parser = configparser.ConfigParser()
        parser.read(ARQUIVO_CONFIG_LOCAL, encoding="utf-8")
        chave = parser.get("ddb", "api_key", fallback=None)
        if chave:
            return chave

    raise ConfigError(
        "Chave da API da DDB não encontrada. Cadastre-se de graça em "
        "https://www.deutsche-digitale-bibliothek.de/user/register, gere uma "
        "chave, e guarde na variável de ambiente DDB_API_KEY ou no arquivo "
        f"{ARQUIVO_CONFIG_LOCAL.name} (seção [ddb], chave api_key)."
    )
