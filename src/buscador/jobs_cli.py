# -*- coding: utf-8 -*-
"""
Ponto de entrada de linha de comando do motor de jobs -- roda quando voce
digita "python -m buscador.jobs_cli <comando>". Comandos disponiveis:
iniciar, status, parar, retomar. O trabalho de verdade fica em
core/jobs_motor.py -- este arquivo so le os argumentos e chama o motor.
"""
import argparse
import sys
from pathlib import Path

from buscador.core.jobs_motor import (
    descrever_progresso,
    iniciar_job,
    parar_job,
    reconciliar_estados,
    retomar_job,
)
from buscador.core.jobs_registro import CAMINHO_PADRAO


def _comando_iniciar(args):
    # iniciar_job levanta ValueError (modulo desconhecido) ou OSError (nao deu
    # pra lancar o processo; o job fica marcado "erro" no registro)
    try:
        job = iniciar_job(args.modulo, args.argv, args.registro)
    except (ValueError, OSError) as erro:
        print(f"Nao deu para iniciar: {erro}")
        return 1
    print(f"Job '{job.id}' iniciado (modulo: {job.modulo}, pid: {job.pid}).")
    return 0


def _comando_status(args):
    jobs = reconciliar_estados(args.registro)
    if not jobs:
        print("Nenhum job no registro ainda.")
        return 0
    for job in jobs:
        progresso = descrever_progresso(job) if job.estado == "rodando" else ""
        linha = f"[{job.estado}] {job.id} (modulo: {job.modulo})"
        if progresso:
            linha += f" -- {progresso}"
        print(linha)
    return 0


def _comando_parar(args):
    # parar_job levanta ValueError (id inexistente) ou RuntimeError (nao deu
    # pra parar com seguranca: nada foi morto e o estado nao mudou)
    try:
        job = parar_job(args.id, args.registro)
    except (ValueError, RuntimeError) as erro:
        print(f"Nao deu para parar: {erro}")
        return 1
    print(f"Job '{job.id}': {job.estado}.")
    return 0


def _comando_retomar(args):
    # retomar_job levanta ValueError (id inexistente) ou RuntimeError (ja ha um
    # job identico rodando) e, por terminar em iniciar_job, tambem OSError (nao
    # deu pra lancar o processo; o job novo fica marcado "erro" no registro)
    try:
        job = retomar_job(args.id, args.registro)
    except (ValueError, RuntimeError, OSError) as erro:
        print(f"Nao deu para retomar: {erro}")
        return 1
    print(f"Job '{args.id}' retomado como '{job.id}' (pid: {job.pid}).")
    return 0


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
        # o log de um job pode ter qualquer texto, e o console/pipe do Windows
        # nem sempre consegue imprimir tudo: troca o que nao der por "?" em vez
        # de derrubar o comando (principalmente o status)
    parser = argparse.ArgumentParser(description="Motor de jobs do BuscadorBaixador.")
    parser.add_argument("--registro", default=CAMINHO_PADRAO, type=Path,
                         help="Caminho do arquivo de registro (uso interno/testes)")
    subparsers = parser.add_subparsers(dest="comando", required=True)

    p_iniciar = subparsers.add_parser("iniciar", help="Inicia um job novo")
    p_iniciar.add_argument("modulo", choices=["cli", "gallica_crawl", "gallica_enriquecer"])
    p_iniciar.add_argument("argv", nargs=argparse.REMAINDER,
                            help="Argumentos passados pro comando de verdade (ex.: --adapter phpbb)")
    # REMAINDER (nao "*") e essencial aqui -- com "*" o argparse tentaria
    # interpretar algo como "--adapter" como uma opcao DESTE parser (que
    # nao existe) e falharia, em vez de simplesmente repassar pro comando
    # real. REMAINDER pega tudo que sobrar depois de "modulo", sem tentar
    # interpretar nada.
    p_iniciar.set_defaults(funcao=_comando_iniciar)

    p_status = subparsers.add_parser("status", help="Mostra todos os jobs e o progresso deles")
    p_status.set_defaults(funcao=_comando_status)

    p_parar = subparsers.add_parser("parar", help="Para um job em andamento")
    p_parar.add_argument("id")
    p_parar.set_defaults(funcao=_comando_parar)

    p_retomar = subparsers.add_parser("retomar", help="Inicia de novo um job (mesmo modulo/argumentos)")
    p_retomar.add_argument("id")
    p_retomar.set_defaults(funcao=_comando_retomar)

    args = parser.parse_args(argv)
    return args.funcao(args)


if __name__ == "__main__":
    raise SystemExit(main())
