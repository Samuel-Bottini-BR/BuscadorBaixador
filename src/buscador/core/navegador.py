# -*- coding: utf-8 -*-
"""
Navegador automatizado, usando a biblioteca SeleniumBase -- controla um
Chrome de verdade por código, então roda JavaScript de verdade (diferente
do ClienteEducado, que só lê o HTML cru). Por isso resolve tanto "site só
mostra conteúdo depois de rodar JavaScript" quanto "site pede login" e
"apareceu CAPTCHA".

Usa um perfil de Chrome de verdade -- um dos que aparecem no seletor
"Quem está usando o Chrome?" do próprio navegador do Samuel, não uma pasta
separada e escondida. Isso porque, na prática (testado ao vivo em
16/09/2026), uma pasta de perfil isolada e desconhecida do Chrome normal
confundia o Samuel na hora de logar (janela sem histórico/favorito
nenhum, fácil de misturar com pop-up do próprio Chrome). Com um perfil de
verdade, o login pode ser feito pela interface normal do Chrome (fora da
automação também, se precisar), e a automação só reaproveita esse mesmo
perfil depois.

Limite técnico importante: um perfil de Chrome só pode estar em uso por
um processo de cada vez -- se o perfil escolhido estiver aberto numa janela
normal do Chrome, a automação não consegue usá-lo ao mesmo tempo (o
Chrome recusa). Feche a janela normal desse perfil antes de rodar a
automação com ele.
"""
import json
import os
from pathlib import Path

from seleniumbase import Driver

# ! NUNCA usar os parâmetros uc / uc_cdp / uc_sub do SeleniumBase (Driver())
# ! -- eles ligam o chamado "UC Mode" / "CDP Mode", feitos especificamente
# ! pra disfarçar a automação e enganar sistemas de detecção de robô. Isso é
# ! proibido neste projeto (CLAUDE.md, seção 8.1, mesma regra do caso
# ! zvdd.de na seção 12). Não é negociável, mesmo que esses parâmetros
# ! estejam disponíveis a uma linha de distância no pacote instalado.


def pasta_chrome_real() -> Path:
    """Caminho da pasta "User Data" do Chrome de verdade instalado no
    Windows -- onde ficam todos os perfis normais do usuário (os que
    aparecem no seletor "Quem está usando o Chrome?")."""
    return Path(os.environ["LOCALAPPDATA"]) / "Google" / "Chrome" / "User Data"


def _mapa_perfis(pasta_user_data: Path) -> dict:
    """Le o arquivo "Local State" que o Chrome mantem na raiz da pasta
    User Data -- ele guarda, entre outras coisas, o nome visivel de cada
    perfil (o que aparece no seletor) e em qual pasta ("Default",
    "Profile 1", "Profile 2"...) cada um fica guardado de verdade.
    Devolve um dicionario {nome_visivel: nome_da_pasta}."""
    caminho = pasta_user_data / "Local State"
    dados = json.loads(caminho.read_text(encoding="utf-8"))
    info = dados.get("profile", {}).get("info_cache", {})
    return {meta.get("name"): pasta for pasta, meta in info.items()}


def resolver_perfil(nome_visivel: str, pasta_user_data: Path | None = None) -> str:
    """Acha a pasta real (ex. "Profile 3") a partir do nome que aparece no
    seletor de perfis do Chrome (ex. "Automacao"). Levanta um erro claro,
    listando os perfis que existem de verdade, se nao achar -- em vez de
    um erro tecnico confuso do Chrome mais na frente."""
    pasta_user_data = pasta_user_data or pasta_chrome_real()
    mapa = _mapa_perfis(pasta_user_data)
    if nome_visivel not in mapa:
        existentes = ", ".join(sorted(nome for nome in mapa if nome))
        raise ValueError(
            f"Não achei um perfil do Chrome chamado '{nome_visivel}'. "
            f"Perfis existentes: {existentes}. Crie o perfil no Chrome "
            "primeiro (seletor de perfis -> Adicionar)."
        )
    return mapa[nome_visivel]


def abrir_navegador(nome_perfil: str, headless: bool = True) -> Driver:
    """Abre o Chrome usando o perfil de verdade com esse nome (login/
    cookies/etc. persistem sozinhos, o proprio Chrome cuida disso, igual
    quando voce usa o perfil normalmente). headless=True roda invisivel
    (coleta automatica); headless=False abre a janela (para o Samuel
    resolver login/CAPTCHA na mao, pela interface normal do Chrome)."""
    pasta_user_data = pasta_chrome_real()
    pasta_perfil = resolver_perfil(nome_perfil, pasta_user_data)
    # ! NUNCA passar uc=True, uc_cdp=True nem uc_sub=True aqui -- ver aviso
    # ! no topo do arquivo. Só os parâmetros normais de automação (sem disfarce).
    return Driver(
        headless=headless,
        user_data_dir=str(pasta_user_data),
        chromium_arg=f"--profile-directory={pasta_perfil}",
        # "chromium_arg" repassa um argumento de linha de comando direto
        # pro Chrome -- "--profile-directory" e' o jeito do proprio Chrome
        # de dizer "dentro dessa pasta User Data, use ESSE perfil especifico"
    )


def resolver_na_mao(nome_perfil: str, url: str) -> None:
    """Abre uma janela visivel na url, espera o Samuel resolver login e/ou
    CAPTCHA olhando a tela (pela interface normal do Chrome, no perfil
    escolhido), e fecha assim que ele apertar Enter no terminal. A sessao
    fica salva automaticamente no perfil (ver abrir_navegador) -- nao
    precisa fazer mais nada depois disso."""
    driver = abrir_navegador(nome_perfil, headless=False)  # headless=False -> janela visível de verdade
    try:
        driver.get(url)  # navega até a página pedida
        input(
            f"Uma janela do Chrome abriu, usando o perfil '{nome_perfil}'. "
            "Resolva login e/ou CAPTCHA olhando a tela, e aperte Enter aqui "
            "quando terminar..."
        )
        # "input(...)" mostra essa mensagem no terminal e PAUSA a execução
        # do programa até alguém digitar algo e apertar Enter -- é assim
        # que o programa "espera" o Samuel terminar de resolver a tela
    finally:
        # "finally" garante que isso roda MESMO se algo der errado no
        # meio (ex.: o Samuel fechar a janela do Chrome na mão, ou
        # apertar Ctrl+C) -- nunca deixa o navegador aberto pra sempre por acidente
        driver.quit()
