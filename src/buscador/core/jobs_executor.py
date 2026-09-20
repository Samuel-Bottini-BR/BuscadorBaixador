# -*- coding: utf-8 -*-
# src/buscador/core/jobs_executor.py
"""
Ponto de entrada do processo "executor" de um job -- lancado por
core/jobs_motor.py::iniciar_job, nunca digitado na mao. Roda o comando de
verdade do job e atualiza o registro quando ele termina:
"python -m buscador.core.jobs_executor <id_do_job> <caminho_do_registro>".
"""
import sys
from pathlib import Path

from buscador.core.jobs_motor import executar_job


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    executar_job(argv[0], Path(argv[1]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
