# -*- coding: utf-8 -*-
"""Sinal para os adaptadores dizerem "preciso que o Samuel faca algo" (chave
de API, login, ou resolver um CAPTCHA) em vez de travar com um erro feio ou
tentar burlar a barreira sozinho. Nunca capturar isso dentro de um laco de
retentativa de infraestrutura (429/timeout) -- so a cascata (metodo_coleta.py)
ou o ponto de entrada de um pipeline (cli.py, gallica_crawl.py) tratam."""

TIPO_CHAVE_API = "chave_api"
TIPO_LOGIN = "login"
TIPO_CAPTCHA = "captcha"


class AcaoHumanaNecessaria(Exception):
    def __init__(self, tipo: str, mensagem: str, site: str | None = None):
        self.tipo = tipo
        self.mensagem = mensagem
        self.site = site
        super().__init__(mensagem)


def formatar_aviso(erro: AcaoHumanaNecessaria) -> str:
    site = f" ({erro.site})" if erro.site else ""
    return f"Preciso da sua ajuda{site}: {erro.mensagem}"
