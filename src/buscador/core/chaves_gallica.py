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


ARK_RE = re.compile(r"ark:/12148/([^/]+)")
# Esse regex procura a sequência literal "ark:/12148/" seguida de um ou mais
# caracteres que NÃO sejam "/" (aquele [^/] significa "qualquer coisa exceto
# /"), e captura esse trecho ([...]+) no grupo 1 pra devolver depois.
# Funciona porque o ark id é sempre o primeiro componente depois de "ark:/12148/"


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
