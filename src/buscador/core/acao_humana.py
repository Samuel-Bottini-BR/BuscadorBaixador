# -*- coding: utf-8 -*-
"""
Este arquivo define o "sinal de socorro" do programa: um jeito padronizado
dos adaptadores dizerem "preciso que o Samuel faça algo" (conseguir uma
chave de API, fazer login, resolver um CAPTCHA) em vez de travar com um
erro feio e confuso, OU pior, tentar contornar essa barreira sozinho sem
avisar ninguém.

Regra importante: esse sinal NUNCA deve ser "capturado" (tratado, ignorado
silenciosamente) dentro de um laço de retentativa de infraestrutura (tipo
o que trata 429/timeout em core/http_educado.py ou core/coleta_gallica.py)
-- ele só deve ser tratado pela cascata (core/metodo_coleta.py) ou pelo
ponto de entrada de um pipeline (cli.py, gallica_crawl.py), onde vira uma
mensagem clara pro Samuel. Se fosse capturado no lugar errado, o aviso
sumiria escondido atrás de uma retentativa automática, e o Samuel nunca
saberia que precisava agir.
"""

# Os "tipos" possíveis desse sinal -- guardados como texto simples em vez
# de número, pra ficar fácil de ler numa mensagem de log/erro.
TIPO_CHAVE_API = "chave_api"
TIPO_LOGIN = "login"
TIPO_CAPTCHA = "captcha"


class AcaoHumanaNecessaria(Exception):
    # Herda de Exception (o tipo genérico de erro do Python) -- criar essa
    # classe própria permite ter um erro com nome que já explica o que
    # aconteceu, e com campos extras (tipo, mensagem, site) além do texto
    # comum que todo erro tem.
    def __init__(self, tipo: str, mensagem: str, site: str | None = None):
        # __init__ roda quando o código faz "raise AcaoHumanaNecessaria(...)"
        # -- "tipo: str" e "site: str | None" são "dicas de tipo" (type
        # hints), que documentam que tipo de valor cada parâmetro espera,
        # sem forçar isso de verdade (o Python não trava se vier errado).
        self.tipo = tipo
        self.mensagem = mensagem  # instrução pronta pra mostrar pro Samuel, em português
        self.site = site  # qual site causou isso (opcional -- "| None" quer dizer que pode ficar sem preencher)
        super().__init__(mensagem)
        # "super().__init__(...)" chama o __init__ da classe-mãe
        # (Exception), garantindo que esse objeto continua se comportando
        # como um erro normal do Python por baixo dos panos (ex.: dá pra
        # fazer "str(erro)" e pegar a mensagem)


def formatar_aviso(erro: AcaoHumanaNecessaria) -> str:
    """Transforma um AcaoHumanaNecessaria numa única linha de texto pronta
    pra mostrar no terminal, incluindo o nome do site quando tiver um."""
    site = f" ({erro.site})" if erro.site else ""
    # se "erro.site" tiver algum valor, monta o texto " (nome-do-site)";
    # se não tiver (for None ou vazio), essa parte fica vazia
    return f"Preciso da sua ajuda{site}: {erro.mensagem}"
