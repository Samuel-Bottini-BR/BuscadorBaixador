# -*- coding: utf-8 -*-
"""
Lê os cookies (pequenos pedaços de dado que um site guarda no seu
navegador pra lembrar que você está logado, entre outras coisas) do Chrome
NORMAL do Samuel -- o do dia a dia, não um navegador automatizado -- pra
reaproveitar um login que ele já fez, sem precisar abrir nada nem pedir
nada.

Esta é uma peça auxiliar do navegador automatizado (navegador.py) -- a
primeira tentativa de resolver login, antes de precisar abrir uma janela
de verdade.

# ! IMPORTANTE (testado ao vivo em 15/09/2026): no Chrome atual do Samuel
# ! (versão 152), isso NÃO funciona -- o Google protege os cookies com uma
# ! técnica chamada "app-bound encryption" desde a versão 127 (2024),
# ! especificamente contra programas de fora lendo cookie sem passar pelo
# ! próprio navegador. Não é bug daqui -- o código abaixo já trata isso
# ! direito (devolve None, sem quebrar nada). NUNCA tente contornar essa
# ! proteção -- é a mesma categoria de regra do UC Mode/CDP Mode em
# ! navegador.py: existe técnica pra isso, mas contornar uma barreira de
# ! segurança colocada de propósito não é algo que fazemos neste projeto.
# ! Ver CLAUDE.md, seção 8.1, pra mais contexto.
"""
import logging

import browser_cookie3  # biblioteca externa que sabe onde/como o Chrome guarda os cookies no disco, e le eles

logger = logging.getLogger(__name__)


def cookies_do_chrome(dominio: str):
    """Devolve um cookiejar (uma "caixa" de cookies, formato que a
    biblioteca requests entende) com os cookies do Chrome para o domínio
    pedido, ou None se não achar nada (nunca logou nesse site, ou -- o caso
    mais comum hoje, ver aviso acima -- a versão do Chrome cifra os cookies
    de um jeito que a biblioteca não consegue ler). Quem chamou essa função
    decide o que fazer com None -- normalmente, tentar a próxima camada de
    resolução de login."""
    try:
        jar = browser_cookie3.chrome(domain_name=dominio)
    except Exception as erro:
        # Qualquer problema (cifra que não conseguimos ler, Chrome não
        # instalado, etc.) vira só um registro discreto no log, nunca um
        # erro que trava o programa -- essa camada é só a PRIMEIRA
        # tentativa, é normal e esperado que às vezes ela não funcione.
        logger.info("Nao consegui ler cookies do Chrome para %s (%s).", dominio, erro)
        return None
    return jar if len(jar) > 0 else None
    # se achou pelo menos 1 cookie, devolve a caixa toda; se veio vazia
    # (nunca logou nesse site), devolve None do mesmo jeito que se tivesse dado erro
