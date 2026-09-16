# -*- coding: utf-8 -*-
"""
Ponto de entrada de linha de comando da Etapa 2: pega o que a Etapa 1
(gallica_crawl.py) já coletou em bruto (só título/link/metadado, sem
verificar nem traduzir nada ainda) e verifica cada link + traduz cada
título, em lotes, de forma retomável entre execuções. Ver
core/enriquecimento_lote.py pra entender o motor por trás disso.
"""
import argparse
from pathlib import Path

from buscador.core.coleta_csv import carregar_itens_csv
from buscador.core.enriquecimento_lote import LOTE_TAMANHO_PADRAO, WORKERS_PADRAO, enriquecer_em_lotes

SAIDAS = Path(__file__).resolve().parent.parent.parent / "saidas"
DIRETORIO_COLETAS = SAIDAS / "gallica_crawl"
# Mesma pasta que gallica_crawl.py usa -- a Etapa 2 lê o que a Etapa 1
# deixou salvo ali (o CSV bruto), então precisam apontar pro mesmo lugar.


def _mostrar_progresso(checkpoint, total_lotes):
    """Passada pro motor (core/enriquecimento_lote.py) como a função que
    ele chama depois de cada lote terminar, pra mostrar o andamento no terminal."""
    print(f"  lote {checkpoint.proximo_lote}/{total_lotes} concluído")


def main(argv=None):
    """Função principal deste arquivo -- roda quando você digita
    "python -m buscador.gallica_enriquecer <job>" no terminal, onde <job>
    é o mesmo nome de pasta usado na Etapa 1."""
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
        # se o CSV da Etapa 1 não existe, não tem nada pra enriquecer --
        # avisa de forma clara em vez de dar um erro técnico confuso
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
