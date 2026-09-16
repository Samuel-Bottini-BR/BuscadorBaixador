# -*- coding: utf-8 -*-
"""
Lê chaves de API por site de um arquivo de configuração local, no formato
".ini" (um formato de texto simples, com [secoes] e "chave = valor"),
chamado buscador.local.cfg. Esse arquivo NUNCA vai pro GitHub (está listado
no .gitignore) -- é só pro seu computador, porque pode conter chaves
secretas.

Esta função não lança erro se o arquivo ou a chave não existirem -- ela só
devolve None (o jeito do Python de dizer "nada aqui"), e quem chamou decide
o que fazer com isso (normalmente, levantar um AcaoHumanaNecessaria -- ver
core/acao_humana.py -- avisando que falta configurar essa chave).
"""
import configparser  # biblioteca padrão do Python pra ler arquivos no formato .ini
from pathlib import Path

# Caminho padrão do arquivo de configuração: a raiz do projeto (a pasta
# onde fica o CLAUDE.md, o .git, etc.), não dentro de src/. Cada ".parent"
# sobe uma pasta a partir deste arquivo (core/config_sites.py) até chegar lá.
CAMINHO_PADRAO = Path(__file__).resolve().parent.parent.parent.parent / "buscador.local.cfg"


def ler_chave(site: str, chave: str = "chave_api", caminho: Path = CAMINHO_PADRAO) -> str | None:
    """Lê uma chave de dentro da seção [site] do arquivo .ini. Por padrão
    procura o campo "chave_api", mas dá pra pedir outro nome de campo (ex.:
    "usuario") passando o parâmetro "chave". Devolve None se o arquivo não
    existir, se o site não tiver seção no arquivo, ou se a chave não
    estiver preenchida ali -- nunca lança erro por isso."""
    if not caminho.exists():
        return None  # arquivo nem existe ainda -- normal, se o Samuel nunca precisou configurar chave nenhuma
    config = configparser.ConfigParser()
    config.read(caminho, encoding="utf-8")
    return config.get(site, chave, fallback=None)
    # ".get(secao, campo, fallback=None)" já resolve sozinho os casos de
    # "a seção não existe" ou "o campo não existe dentro da seção",
    # devolvendo None em vez de lançar erro -- por isso não precisamos de
    # nenhum try/except aqui
