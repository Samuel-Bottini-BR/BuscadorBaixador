# -*- coding: utf-8 -*-
"""Ponto de entrada de linha de comando: dado uma URL, escolhe o adaptador
certo, verifica cada link, traduz o titulo, e gera a planilha da Fase 1."""
import argparse
import datetime
import re
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from buscador.adapters.gallica import GallicaAdapter
from buscador.adapters.phpbb import PhpbbAdapter
from buscador.core.planilha import gerar_planilha
from buscador.core.traducao import traduzir
from buscador.core.verificacao_links import analisar, classificar_tipo

ADAPTERS_POR_DOMINIO = {
    "grand-sud-medieval.fr": "phpbb",
    "gallica.bnf.fr": "gallica",
}

SAIDAS = Path(__file__).resolve().parent.parent.parent / "saidas"


def escolher_adapter(url, forcado=None):
    if forcado:
        return forcado
    dominio = urlparse(url).netloc.lower()
    for sufixo, nome in ADAPTERS_POR_DOMINIO.items():
        if dominio == sufixo or dominio.endswith("." + sufixo):
            return nome
    raise ValueError(f"Não sei qual adaptador usar para '{url}'. Use --adapter.")


def construir_adapter(nome_adapter, url_ou_consulta):
    if nome_adapter == "phpbb":
        return PhpbbAdapter(url_ou_consulta)
    if nome_adapter == "gallica":
        return GallicaAdapter(_extrair_consulta_gallica(url_ou_consulta))
    raise ValueError(f"Adaptador desconhecido: {nome_adapter}")


def _extrair_consulta_gallica(valor):
    """Aceita tanto uma consulta CQL direta ('gallica all "Clavius"') quanto
    uma URL do SRU copiada do navegador (usa o parametro 'query' dela)."""
    if valor.startswith("http://") or valor.startswith("https://"):
        parametros = parse_qs(urlparse(valor).query)
        if parametros.get("query"):
            return parametros["query"][0]
    return valor


def enriquecer_item(item):
    status_texto, categoria = analisar(item.link)
    item.status_link = status_texto
    item.tipo = classificar_tipo(status_texto, categoria)
    item.extra["categoria"] = categoria
    item.titulo_pt = traduzir(item.titulo_original, idioma_origem=item.extra.get("idioma_origem", "auto"))
    return item


def _slug_do_dominio(url_ou_consulta):
    """Nome de arquivo a partir do dominio da URL; se a entrada nao for uma
    URL (ex.: uma consulta CQL da Gallica), usa o proprio texto da consulta."""
    dominio = urlparse(url_ou_consulta).netloc.lower().replace("www.", "")
    base = dominio or url_ou_consulta[:40]
    slug = re.sub(r"[^a-z0-9]+", "-", base.lower()).strip("-")
    return slug or "saida"


def main(argv=None):
    parser = argparse.ArgumentParser(description="Mapeia um site para uma planilha (Fase 1).")
    parser.add_argument("url", help="URL de entrada (topico ou busca do site)")
    parser.add_argument("--adapter", choices=["phpbb", "gallica"], help="Força um adaptador específico")
    parser.add_argument("--saida", help="Caminho do .xlsx de saída (padrão: saidas/<site>_<data>.xlsx)")
    args = parser.parse_args(argv)

    try:
        nome_adapter = escolher_adapter(args.url, args.adapter)
        adapter = construir_adapter(nome_adapter, args.url)
        itens = [enriquecer_item(item) for item in adapter.iter_itens()]
    except ValueError as erro:
        print(f"Não deu para continuar: {erro}")
        return 1

    if args.saida:
        caminho_saida = Path(args.saida)
    else:
        data = datetime.date.today().isoformat()
        caminho_saida = SAIDAS / f"{_slug_do_dominio(args.url)}_{data}.xlsx"

    caminho_final = gerar_planilha(itens, caminho_saida)
    print(f"{len(itens)} itens encontrados. Planilha salva em: {caminho_final}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
