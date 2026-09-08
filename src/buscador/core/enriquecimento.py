# -*- coding: utf-8 -*-
"""Verifica o link e traduz o titulo de um Item -- usado tanto pelo CLI de
um site so (cli.py) quanto pela Etapa 2 da coleta longa da Gallica
(core/enriquecimento_lote.py), que roda isso em paralelo sobre o que a
Etapa 1 ja coletou."""
from buscador.core.traducao import traduzir
from buscador.core.verificacao_links import analisar, classificar_tipo


def enriquecer_item(item):
    status_texto, categoria = analisar(item.link)
    item.status_link = status_texto
    item.tipo = classificar_tipo(status_texto, categoria)
    item.extra["categoria"] = categoria
    item.titulo_pt = traduzir(item.titulo_original, idioma_origem=item.extra.get("idioma_origem", "auto"))
    return item
