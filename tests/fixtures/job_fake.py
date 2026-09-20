# -*- coding: utf-8 -*-
# tests/fixtures/job_fake.py
"""
Script minusculo usado so pelos testes do motor de jobs
(test_jobs_motor.py, test_jobs_cli.py) -- roda rapido, imprime uma linha,
e sai com o codigo de saida pedido no primeiro argumento (0 por padrao),
sem precisar rodar nenhum modulo de verdade do buscador (que levaria
minutos/horas de verdade).
"""
import sys


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    print("job_fake rodou")
    return int(argv[0]) if argv else 0


if __name__ == "__main__":
    raise SystemExit(main())
