# -*- coding: utf-8 -*-
# tests/fixtures/job_lento_fake.py
"""Script minusculo usado so pelos testes do motor de jobs -- fica rodando
por bastante tempo (bem mais que qualquer teste precisa esperar), pra dar
tempo de testar 'parar' um job que ainda esta rodando de verdade."""
import time


def main():
    time.sleep(120)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
