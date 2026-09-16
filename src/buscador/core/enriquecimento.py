# -*- coding: utf-8 -*-
"""
"Enriquecer" um Item quer dizer: pegar o que o adaptador já achou (título,
link) e completar com mais informação -- checar se o link funciona e
traduzir o título. Usado tanto pelo CLI de um site só (cli.py) quanto pela
Etapa 2 da coleta longa da Gallica (core/enriquecimento_lote.py), que roda
isso em paralelo sobre o que a Etapa 1 já coletou.
"""
from buscador.core.traducao import traduzir
from buscador.core.verificacao_links import analisar, classificar_tipo


def enriquecer_item(item):
    # "item" é um objeto Item (a "caixinha" de dados definida em
    # adapters/base.py). Essa função MODIFICA o item recebido (em vez de
    # criar um novo) e devolve ele mesmo de volta, já completo.
    status_texto, categoria = analisar(item.link)  # verifica se o link está vivo/quebrado/precisa login (ver core/verificacao_links.py)
    item.status_link = status_texto
    item.tipo = classificar_tipo(status_texto, categoria)
    item.extra["categoria"] = categoria
    item.titulo_pt = traduzir(item.titulo_original, idioma_origem=item.extra.get("idioma_origem", "auto"))
    # ".get("idioma_origem", "auto")": pega o idioma que o adaptador já
    # tinha guardado no dicionário "extra" (ver adapters/base.py); se não
    # tiver nenhum guardado, usa "auto" (deixa o tradutor tentar adivinhar)
    return item
