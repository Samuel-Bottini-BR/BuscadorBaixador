# -*- coding: utf-8 -*-
"""Ponto de entrada de linha de comando da Etapa 1: coleta bruta de uma
consulta inteira da Gallica (ex.: todos os livros do catalogo), retomavel
entre execucoes -- pode ser interrompido e rodado de novo a qualquer
momento que ele continua de onde parou. Ver core/coleta_gallica.py."""
import argparse
import shutil
from pathlib import Path

from buscador.core.checkpoint import ConsultaDivergenteError, slug_consulta
from buscador.core.coleta_gallica import COOLDOWN_429_PADRAO_SEGUNDOS, coletar

SAIDAS = Path(__file__).resolve().parent.parent.parent / "saidas"
DIRETORIO_COLETAS = SAIDAS / "gallica_crawl"


def _diretorio_do_job(consulta, job_forcado=None):
    nome = job_forcado or slug_consulta(consulta)
    return DIRETORIO_COLETAS / nome


def _mostrar_progresso(checkpoint):
    if checkpoint.total_registros_api:
        percentual = 100 * checkpoint.itens_gravados / checkpoint.total_registros_api
        print(f"  {checkpoint.itens_gravados}/{checkpoint.total_registros_api} itens ({percentual:.1f}%)")
    else:
        print(f"  {checkpoint.itens_gravados} itens coletados")


def _confirmar_reinicio(diretorio_job):
    if not diretorio_job.exists():
        return True
    resposta = input(
        f"Isso vai apagar todo o progresso salvo em '{diretorio_job}' e comecar do zero. "
        "Tem certeza? (digite 'sim' para confirmar): "
    )
    return resposta.strip().lower() == "sim"


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Etapa 1: coleta bruta de uma consulta inteira da Gallica (retomavel)."
    )
    parser.add_argument("consulta", help='Consulta CQL da Gallica (ex.: dc.type all "monographie")')
    parser.add_argument("--job", help="Nome da pasta de progresso (padrao: gerado a partir da consulta)")
    parser.add_argument("--max-resultados", type=int, default=10_000_000,
                         help="Teto de registros a buscar (padrao: bem acima do catalogo inteiro)")
    parser.add_argument("--tamanho-pagina", type=int, default=50,
                         help="Itens por pagina (maximo 50, limite da BnF)")
    parser.add_argument("--cooldown-429-minutos", type=float, default=COOLDOWN_429_PADRAO_SEGUNDOS / 60,
                         help="Minutos de pausa quando a Gallica bloquear por excesso de requisicoes")
    parser.add_argument("--reiniciar", action="store_true",
                         help="Apaga o progresso salvo desse job e comeca do zero (pede confirmacao)")
    args = parser.parse_args(argv)

    diretorio_job = _diretorio_do_job(args.consulta, args.job)

    if args.reiniciar:
        if not _confirmar_reinicio(diretorio_job):
            print("Cancelado -- nada foi apagado.")
            return 1
        shutil.rmtree(diretorio_job, ignore_errors=True)

    try:
        checkpoint = coletar(
            args.consulta, diretorio_job, tamanho_pagina=args.tamanho_pagina,
            max_registros_alvo=args.max_resultados,
            cooldown_429_segundos=args.cooldown_429_minutos * 60,
            progresso_fct=_mostrar_progresso,
        )
    except ConsultaDivergenteError as erro:
        print(f"Não deu para continuar: {erro}")
        return 1

    print(f"Coleta concluída: {checkpoint.itens_gravados} itens salvos em {diretorio_job / 'itens.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
