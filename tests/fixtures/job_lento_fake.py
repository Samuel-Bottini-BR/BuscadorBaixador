# -*- coding: utf-8 -*-
# tests/fixtures/job_lento_fake.py
"""Script minusculo usado so pelos testes do motor de jobs -- fica rodando
por bastante tempo (bem mais que qualquer teste precisa esperar), pra dar
tempo de testar 'parar' um job que ainda esta rodando de verdade.
Argumento opcional: um caminho de arquivo, onde o script grava o proprio PID
antes de dormir (assim o teste sabe qual e o PID do comando real e consegue
conferir se ele morreu junto com o executor)."""
import os
import sys
import time


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    if argv:
        with open(argv[0], "w", encoding="utf-8") as arquivo:
            arquivo.write(str(os.getpid()))
    time.sleep(120)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
