# -*- coding: utf-8 -*-
"""Ponto de entrada de linha de comando: dado uma URL, escolhe o adaptador
certo, verifica cada link, traduz o titulo, e gera a planilha da Fase 1."""
import argparse
import datetime
import re
from pathlib import Path
from urllib.parse import urlparse

from buscador.adapters.phpbb import PhpbbAdapter
from buscador.core.planilha import gerar_planilha
from buscador.core.traducao import traduzir
from buscador.core.verificacao_links import analisar, classificar_tipo

ADAPTERS_POR_DOMINIO = {
    "grand-sud-medieval.fr": "phpbb",
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
    raise ValueError(f"Adaptador desconhecido: {nome_adapter}")


def enriquecer_item(item):
    status_texto, categoria = analisar(item.link)
    item.status_link = status_texto
    item.tipo = classificar_tipo(status_texto, categoria)
    item.extra["categoria"] = categoria
    item.titulo_pt = traduzir(item.titulo_original, idioma_origem=item.extra.get("idioma_origem", "auto"))
    return item


def _slug_do_dominio(url):
    dominio = urlparse(url).netloc.lower().replace("www.", "")
    slug = re.sub(r"[^a-z0-9]+", "-", dominio).strip("-")
    return slug or "saida"


def main(argv=None):
    parser = argparse.ArgumentParser(description="Mapeia um site para uma planilha (Fase 1).")
    parser.add_argument("url", help="URL de entrada (topico ou busca do site)")
    parser.add_argument("--adapter", choices=["phpbb"], help="Força um adaptador específico")
    parser.add_argument("--saida", help="Caminho do .xlsx de saída (padrão: saidas/<site>_<data>.xlsx)")
    args = parser.parse_args(argv)

    nome_adapter = escolher_adapter(args.url, args.adapter)
    adapter = construir_adapter(nome_adapter, args.url)

    itens = [enriquecer_item(item) for item in adapter.iter_itens()]

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
