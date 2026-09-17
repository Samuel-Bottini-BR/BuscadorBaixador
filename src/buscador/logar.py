# -*- coding: utf-8 -*-
"""
Comando avulso: abre uma janela visível do navegador automatizado pra você
resolver login e/ou CAPTCHA de um site, na hora que você quiser -- sem
precisar esperar uma coleta travar pra fazer isso. Reaproveita a mesma
função (`resolver_na_mao`) que a cascata (core/metodo_coleta.py) já usa
sozinha quando trava no meio de uma coleta automática -- aqui é só um jeito
de disparar isso manualmente, de propósito, antes de começar algo grande.

Uso:
    python -m buscador.logar <nome_perfil> <url>

Exemplo (testado ao vivo em 16/09/2026, funciona):
    python -m buscador.logar internet_archive https://archive.org/account/login
"""
import argparse

from buscador.core.navegador import resolver_na_mao


def main(argv=None):
    """Função principal deste arquivo -- roda quando você digita
    "python -m buscador.logar <perfil> <url>" no terminal."""
    parser = argparse.ArgumentParser(
        description="Abre uma janela do navegador pra você logar/resolver CAPTCHA num site, na hora que quiser."
    )
    parser.add_argument(
        "perfil",
        help="Nome do perfil isolado a usar (ex.: internet_archive) -- a mesma pasta que a coleta automática vai usar depois",
    )
    parser.add_argument("url", help="Endereço da página de login (ou qualquer página) a abrir")
    args = parser.parse_args(argv)

    resolver_na_mao(args.perfil, args.url)
    print(f"Sessão salva no perfil '{args.perfil}'. Já pode rodar a coleta normalmente.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
