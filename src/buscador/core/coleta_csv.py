# -*- coding: utf-8 -*-
"""Escritor incremental de CSV para a coleta bruta da Gallica (Etapa 1):
grava cada pagina assim que chega, em vez de guardar tudo na memoria ate o
fim -- ver core/checkpoint.py para a peca irma que lembra onde parou.

O CSV tambem serve como saida "leve", facil de importar em outros programas
(diferente do .xlsx colorido, que so existe depois, na Etapa 2)."""
import csv
import os

from buscador.adapters.base import Item

COLUNAS = [
    "titulo_original", "link", "autor", "ano", "explicacao", "fonte",
    "provedor", "dominio_publico", "url_pagina", "idioma_origem", "tipo_doc",
]


class EscritorCsvIncremental:
    """Abre o CSV em modo 'acrescentar': se o arquivo ja existe (retomando
    uma coleta interrompida), continua escrevendo no fim dele em vez de
    apagar o que ja tinha."""

    def __init__(self, caminho_csv):
        self.caminho_csv = caminho_csv
        arquivo_novo = not caminho_csv.exists() or caminho_csv.stat().st_size == 0
        caminho_csv.parent.mkdir(parents=True, exist_ok=True)
        self._arquivo = open(caminho_csv, "a", newline="", encoding="utf-8")
        self._escritor = csv.DictWriter(self._arquivo, fieldnames=COLUNAS)
        if arquivo_novo:
            self._escritor.writeheader()
            self._sincronizar()

    def escrever_pagina(self, itens):
        for item in itens:
            self._escritor.writerow(_linha_de(item))
        self._sincronizar()

    def _sincronizar(self):
        self._arquivo.flush()
        os.fsync(self._arquivo.fileno())

    def fechar(self):
        self._arquivo.close()

    def __enter__(self):
        return self

    def __exit__(self, tipo_erro, erro, traceback):
        self.fechar()


def carregar_itens_csv(caminho_csv):
    """Le o CSV inteiro e devolve uma lista de Item, descartando links
    repetidos (mantendo a primeira ocorrencia). Isso protege contra o unico
    jeito de duplicar uma linha nesse desenho: o programa ser interrompido
    bem entre 'gravei a pagina no CSV' e 'salvei o checkpoint dela' -- ao
    retomar, a pagina e buscada de novo e a linha aparece duas vezes."""
    vistos = set()
    itens = []
    with open(caminho_csv, newline="", encoding="utf-8") as arquivo:
        for linha in csv.DictReader(arquivo):
            if linha["link"] in vistos:
                continue
            vistos.add(linha["link"])
            itens.append(_item_de(linha))
    return itens


def _linha_de(item: Item) -> dict:
    return {
        "titulo_original": item.titulo_original,
        "link": item.link,
        "autor": item.autor,
        "ano": item.ano,
        "explicacao": item.explicacao,
        "fonte": item.fonte,
        "provedor": item.provedor,
        "dominio_publico": item.dominio_publico,
        "url_pagina": item.url_pagina,
        "idioma_origem": item.extra.get("idioma_origem", ""),
        "tipo_doc": item.extra.get("tipo_doc", ""),
    }


def _item_de(linha: dict) -> Item:
    return Item(
        titulo_original=linha["titulo_original"],
        link=linha["link"],
        autor=linha["autor"],
        ano=linha["ano"],
        explicacao=linha["explicacao"],
        fonte=linha["fonte"],
        provedor=linha["provedor"],
        dominio_publico=linha["dominio_publico"],
        url_pagina=linha["url_pagina"],
        extra={"idioma_origem": linha["idioma_origem"], "tipo_doc": linha["tipo_doc"]},
    )
