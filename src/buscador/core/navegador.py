# -*- coding: utf-8 -*-
"""
Navegador automatizado, usando a biblioteca SeleniumBase -- controla um
Chrome de verdade por código, então roda JavaScript de verdade (diferente
do ClienteEducado, que só lê o HTML cru). Por isso resolve tanto "site só
mostra conteúdo depois de rodar JavaScript" quanto "site pede login" e
"apareceu CAPTCHA".

Guarda uma sessão persistente (que continua existindo entre uma execução e
outra) por site -- um perfil de Chrome completo, guardado na pasta
sessoes_navegador/<site>/ -- pra não precisar logar de novo toda vez que o
programa roda. O próprio Chrome cuida de persistir (salvar de forma
duradoura) cookies, localStorage (outro jeito de site guardar dado no
navegador) etc. dentro desse perfil sozinho -- não precisamos escrever
código pra salvar/carregar isso na mão.

# ! NUNCA usar os parâmetros uc / uc_cdp / uc_sub do SeleniumBase (Driver())
# ! -- eles ligam o chamado "UC Mode" / "CDP Mode", feitos especificamente
# ! pra disfarçar a automação e enganar sistemas de detecção de robô. Isso é
# ! proibido neste projeto (CLAUDE.md, seção 8.1, mesma regra do caso
# ! zvdd.de na seção 12). Não é negociável, mesmo que esses parâmetros
# ! estejam disponíveis a uma linha de distância no pacote instalado.
"""
from pathlib import Path

from seleniumbase import Driver

# Pasta onde cada site ganha sua própria subpasta de perfil de Chrome
# (login, cookies, etc. isolados por site -- nunca o Chrome pessoal do
# Samuel, que fica aberto e em uso o tempo todo).
PASTA_SESSOES = Path(__file__).resolve().parent.parent.parent.parent / "sessoes_navegador"


def caminho_perfil(site: str) -> Path:
    """Devolve a pasta de perfil de Chrome de um site específico (ainda
    que ela não exista no disco ainda -- só calcula o caminho)."""
    return PASTA_SESSOES / site


def abrir_navegador(site: str, headless: bool = True) -> Driver:
    """Abre um Chrome com o perfil salvo desse site (login/cookies/etc
    persistem sozinhos entre execucoes). headless=True roda invisivel
    (coleta automatica); headless=False abre a janela (para o Samuel
    resolver login/CAPTCHA na mao)."""
    # "headless" (literalmente "sem cabeça", em inglês) é o termo comum
    # pra um navegador rodando SEM mostrar janela nenhuma na tela -- ele
    # continua funcionando de verdade por dentro, só não aparece.
    perfil = caminho_perfil(site)
    perfil.mkdir(parents=True, exist_ok=True)
    # ! NUNCA passar uc=True, uc_cdp=True nem uc_sub=True aqui -- ver aviso
    # ! no topo do arquivo. Só os parâmetros normais de automação (sem disfarce).
    return Driver(headless=headless, user_data_dir=str(perfil))
    # "user_data_dir" é o parâmetro que diz ao Chrome pra usar essa pasta
    # como perfil completo -- é aí que a "mágica" da sessão persistente
    # acontece, sem precisarmos escrever nada a mais


def resolver_na_mao(site: str, url: str) -> None:
    """Abre uma janela visivel na url, espera o Samuel resolver login e/ou
    CAPTCHA olhando a tela, e fecha assim que ele apertar Enter no terminal.
    A sessao fica salva automaticamente no perfil do site (ver
    abrir_navegador) -- nao precisa fazer mais nada depois disso."""
    driver = abrir_navegador(site, headless=False)  # headless=False -> janela visível de verdade
    try:
        driver.get(url)  # navega até a página pedida
        input(
            f"Uma janela do Chrome abriu para '{site}'. Resolva login e/ou "
            "CAPTCHA olhando a tela, e aperte Enter aqui quando terminar..."
        )
        # "input(...)" mostra essa mensagem no terminal e PAUSA a execução
        # do programa até alguém digitar algo e apertar Enter -- é assim
        # que o programa "espera" o Samuel terminar de resolver a tela
    finally:
        # "finally" garante que isso roda MESMO se algo der errado no
        # meio (ex.: o Samuel fechar a janela do Chrome na mão, ou
        # apertar Ctrl+C) -- nunca deixa o navegador aberto pra sempre por acidente
        driver.quit()
