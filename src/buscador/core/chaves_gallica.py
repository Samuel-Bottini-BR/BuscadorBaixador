# -*- coding: utf-8 -*-
"""
Chaves de identificação de obras na Gallica: extrai o "ark id" de uma URL,
que é o identificador canônico de uma obra dentro do sistema de arquivo
digital da Biblioteca Nacional Francesa.

A Gallica é um repositório de obras digitalizadas: https://gallica.bnf.fr
Cada obra tem um único "ark id" (ARK = Archival Resource Key), que aparece
em qualquer link da obra com o padrão ark:/12148/<id>. Esse id é o que usamos
aqui como "chave canônica" pra ligar dados de duas fontes diferentes sobre
a mesma obra (sem depender de título, que pode variar ou estar incompleto).
"""
import re
from typing import Optional


ARK_RE = re.compile(r"ark:/12148/([A-Za-z0-9]+)")
# Esse regex procura a sequência literal "ark:/12148/" seguida de um ou mais
# caracteres alfanuméricos (letras ou dígitos), e captura esse trecho
# ([A-Za-z0-9]+) no grupo 1 pra devolver depois -- o ark id em si é sempre
# só letras/dígitos, então parar no primeiro caractere que não for isso
# funciona pra qualquer coisa que venha colada depois (barra de um sufixo
# tipo "/f21.item", mas também ".item" sem barra, "?rk=..." de parâmetro
# de busca, "#" de fragmento, ou lixo de raspagem tipo espaço/parêntese --
# achado real ao processar saidas/gallica_mapa_livros.json: ~15% dos ark
# ids vinham com esse tipo de lixo grudado quando a regra antiga só sabia
# parar na barra ([^/]+), ver tests/test_chaves_gallica.py pros exemplos
# reais que motivaram essa correção).


def extrair_ark_id(link: str) -> Optional[str]:
    """Extrai o ark id (identificador canônico) de uma URL da Gallica.

    Procura o padrão "ark:/12148/<id>" dentro da URL e devolve só o id.
    Funciona com http:// ou https://, e com qualquer sufixo depois do id
    (como "/f21.item" ou "/f1.image").

    Args:
        link: URL da Gallica, ou None.

    Returns:
        O ark id (ex.: "btv1b8595063v"), ou None se não achar o padrão.
    """
    if link is None or link == "":
        return None

    match = ARK_RE.search(link)
    if match:
        return match.group(1)
    return None
