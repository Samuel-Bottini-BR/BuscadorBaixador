# -*- coding: utf-8 -*-
"""
Navegador automatizado, usando a biblioteca SeleniumBase -- controla um
Chrome de verdade por código, então roda JavaScript de verdade (diferente
do ClienteEducado, que só lê o HTML cru). Por isso resolve tanto "site só
mostra conteúdo depois de rodar JavaScript" quanto "site pede login" e
"apareceu CAPTCHA".

Usa um perfil de Chrome **isolado**, numa pasta própria (uma por nome de
perfil, em sessoes_navegador/<nome>/) -- não um perfil de verdade do
Chrome pessoal do Samuel. Chegamos a tentar usar um perfil de verdade
(testado ao vivo em 16/09/2026), mas o Chrome tem um "cadeado de instância
única" na pasta raiz inteira (User Data), não por perfil -- então, com o
Chrome pessoal do Samuel sempre aberto (ele usa o tempo todo), o Chrome
recusa abrir um segundo processo independente apontando pra essa mesma
pasta raiz, mesmo pedindo um perfil diferente
("SessionNotCreatedException: Unable to set user_data_dir while starting
Chrome"). Uma pasta separada tem sua própria "raiz" só dela, então roda ao
mesmo tempo que o Chrome pessoal sem esse conflito.

Login/cookies/etc. persistem sozinhos dentro dessa pasta entre execuções
(o próprio Chrome cuida disso) -- não precisamos escrever código pra
salvar/carregar isso na mão.

# ! NUNCA usar os parâmetros uc / uc_cdp / uc_sub do SeleniumBase (Driver())
# ! -- eles ligam o chamado "UC Mode" / "CDP Mode", feitos especificamente
# ! pra disfarçar a automação e enganar sistemas de detecção de robô. Isso é
# ! proibido neste projeto (CLAUDE.md, seção 8.1, mesma regra do caso
# ! zvdd.de na seção 12). Não é negociável, mesmo que esses parâmetros
# ! estejam disponíveis a uma linha de distância no pacote instalado.
"""
from pathlib import Path

from seleniumbase import Driver

# Pasta onde cada "perfil" (um nome lógico -- normalmente um site, mas
# pode ser qualquer nome) ganha sua própria subpasta isolada de dados do
# Chrome. Nunca é o Chrome pessoal do Samuel.
PASTA_SESSOES = Path(__file__).resolve().parent.parent.parent.parent / "sessoes_navegador"


def caminho_perfil(nome_perfil: str) -> Path:
    """Devolve a pasta de perfil isolado de um nome específico (ainda que
    ela não exista no disco ainda -- só calcula o caminho)."""
    return PASTA_SESSOES / nome_perfil


def abrir_navegador(nome_perfil: str, headless: bool = True) -> Driver:
    """Abre um Chrome com a pasta isolada desse nome (login/cookies/etc
    persistem sozinhos entre execucoes). headless=True roda invisivel
    (coleta automatica); headless=False abre a janela (para o Samuel
    resolver login/CAPTCHA na mao).

    IMPORTANTE ao usar o modo visivel: a janela que abre e' NOVA e
    ISOLADA -- sem historico, sem favorito, sem login nenhum do seu
    Chrome pessoal. Ignore qualquer pop-up do proprio Chrome sobre "fazer
    login no Chrome" ou sincronizar conta -- isso nao e' o site, e' o
    navegador. Os campos de login do SITE aparecem na pagina em si."""
    perfil = caminho_perfil(nome_perfil)
    perfil.mkdir(parents=True, exist_ok=True)
    # ! NUNCA passar uc=True, uc_cdp=True nem uc_sub=True aqui -- ver aviso
    # ! no topo do arquivo. Só os parâmetros normais de automação (sem disfarce).
    return Driver(headless=headless, user_data_dir=str(perfil))


def resolver_na_mao(nome_perfil: str, url: str) -> None:
    """Abre uma janela visivel na url, espera o Samuel resolver login e/ou
    CAPTCHA olhando a tela, e fecha assim que ele apertar Enter no terminal.
    A sessao fica salva automaticamente na pasta desse perfil (ver
    abrir_navegador) -- nao precisa fazer mais nada depois disso."""
    driver = abrir_navegador(nome_perfil, headless=False)  # headless=False -> janela visível de verdade
    try:
        driver.get(url)  # navega até a página pedida
        input(
            f"Uma janela NOVA do Chrome abriu (perfil isolado '{nome_perfil}', "
            "sem nada do seu Chrome pessoal). Resolva login e/ou CAPTCHA "
            "olhando a tela -- ignore qualquer pop-up do proprio Chrome sobre "
            "conta/sincronizacao -- e aperte Enter aqui quando terminar..."
        )
        # "input(...)" mostra essa mensagem no terminal e PAUSA a execução
        # do programa até alguém digitar algo e apertar Enter -- é assim
        # que o programa "espera" o Samuel terminar de resolver a tela
    finally:
        # "finally" garante que isso roda MESMO se algo der errado no
        # meio (ex.: o Samuel fechar a janela do Chrome na mão, ou
        # apertar Ctrl+C) -- nunca deixa o navegador aberto pra sempre por acidente
        driver.quit()
