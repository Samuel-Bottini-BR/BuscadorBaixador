# -*- coding: utf-8 -*-
"""Ponto de entrada de linha de comando da Etapa 2: verifica link + traduz
o que a Etapa 1 (gallica_crawl.py) ja coletou, em lotes, retomavel entre
execucoes. Ver core/enriquecimento_lote.py."""
import argparse
from pathlib import Path

from buscador.core.coleta_csv import carregar_itens_csv
from buscador.core.enriquecimento_lote import LOTE_TAMANHO_PADRAO, WORKERS_PADRAO, enriquecer_em_lotes

SAIDAS = Path(__file__).resolve().parent.parent.parent / "saidas"
DIRETORIO_COLETAS = SAIDAS / "gallica_crawl"


def _mostrar_progresso(checkpoint, total_lotes):
    print(f"  lote {checkpoint.proximo_lote}/{total_lotes} concluído")


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Etapa 2: verifica link + traduz o que a Etapa 1 já coletou (retomável)."
    )
    parser.add_argument("job", help="Nome da pasta do job (a mesma usada na Etapa 1, em saidas/gallica_crawl/)")
    parser.add_argument("--lote-tamanho", type=int, default=LOTE_TAMANHO_PADRAO,
                         help="Quantos itens por planilha final")
    parser.add_argument("--workers", type=int, default=WORKERS_PADRAO,
                         help="Quantas verificações/traduções em paralelo")
    args = parser.parse_args(argv)

    diretorio_job = DIRETORIO_COLETAS / args.job
    caminho_csv = diretorio_job / "itens.csv"
    if not caminho_csv.exists():
        print(f"Não deu para continuar: não achei '{caminho_csv}'. Rode a Etapa 1 (gallica_crawl) primeiro.")
        return 1

    itens = carregar_itens_csv(caminho_csv)
    checkpoint = enriquecer_em_lotes(
        itens, diretorio_job, lote_tamanho=args.lote_tamanho, workers=args.workers,
        progresso_fct=_mostrar_progresso,
    )

    print(f"Enriquecimento concluído: {checkpoint.total_itens} itens em {checkpoint.proximo_lote} planilha(s), "
          f"em {diretorio_job}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
