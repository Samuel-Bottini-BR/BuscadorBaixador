# -*- coding: utf-8 -*-
"""Le cookies do Chrome normal do Samuel (o do dia a dia, nao um navegador
automatizado) para reaproveitar um login que ele ja fez, sem abrir nada.
Peca auxiliar do navegador automatizado (navegador.py) -- a primeira
tentativa antes de precisar abrir qualquer janela."""
import logging

import browser_cookie3

logger = logging.getLogger(__name__)


def cookies_do_chrome(dominio: str):
    """Devolve um cookiejar com os cookies do Chrome para o dominio, ou None
    se nao achar nada (nunca logou nesse site, ou a versao do Chrome cifra
    os cookies de um jeito que a biblioteca nao consegue ler). Quem chamou
    decide o que fazer com None -- normalmente, tentar a proxima camada."""
    try:
        jar = browser_cookie3.chrome(domain_name=dominio)
    except Exception as erro:
        logger.info("Nao consegui ler cookies do Chrome para %s (%s).", dominio, erro)
        return None
    return jar if len(jar) > 0 else None
