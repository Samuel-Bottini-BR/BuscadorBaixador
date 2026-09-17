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
import argparse  # biblioteca padrão do Python pra ler argumentos digitados no terminal (o "perfil" e a "url" abaixo)

from buscador.core.navegador import resolver_na_mao


def main(argv=None):
    """Função principal deste arquivo -- roda quando você digita
    "python -m buscador.logar <perfil> <url>" no terminal. "argv=None" quer
    dizer: se ninguém passar uma lista de argumentos na mão (usado nos
    testes automatizados), lê os argumentos digitados de verdade no
    terminal."""
    parser = argparse.ArgumentParser(
        description="Abre uma janela do navegador pra você logar/resolver CAPTCHA num site, na hora que quiser."
    )
    # Cada ".add_argument" abaixo ensina o argparse a esperar mais um
    # pedaço de informação digitado depois do comando, na ordem em que
    # aparecem aqui (primeiro o perfil, depois a url).
    parser.add_argument(
        "perfil",
        help="Nome do perfil isolado a usar (ex.: internet_archive) -- a mesma pasta que a coleta automática vai usar depois",
    )
    parser.add_argument("url", help="Endereço da página de login (ou qualquer página) a abrir")
    args = parser.parse_args(argv)  # lê e organiza o que foi digitado no terminal

    resolver_na_mao(args.perfil, args.url)
    # a função acima já cuida de tudo: abre a janela visível, espera você
    # resolver e apertar Enter, salva a sessão, fecha a janela sozinha
    # (ver core/navegador.py) -- este arquivo só existe pra poder chamar
    # isso a partir de um comando de terminal, com o perfil/url escolhidos por você
    print(f"Sessão salva no perfil '{args.perfil}'. Já pode rodar a coleta normalmente.")
    return 0  # 0 quer dizer "tudo certo" pro sistema operacional


if __name__ == "__main__":
    # Esse "if" só é verdadeiro quando o arquivo é executado diretamente
    # (não quando é só importado por outro arquivo) -- é o jeito padrão do
    # Python de dizer "isso aqui é o ponto de partida do programa".
    raise SystemExit(main())
