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


def abrir_navegador(
    nome_perfil: str,
    headless: bool = True,
    external_pdf: bool = False,
    escondida: bool = False,
) -> Driver:
    """Abre um Chrome com a pasta isolada desse nome (login/cookies/etc
    persistem sozinhos entre execucoes). headless=True roda invisivel
    (coleta automatica); headless=False abre a janela (para o Samuel
    resolver login/CAPTCHA na mao).

    external_pdf=True desliga o visualizador de PDF embutido do Chrome
    (equivale a `plugins.always_open_pdf_externally` nas configurações do
    Chrome) -- sem isso, o Chrome ABRE o PDF na tela em vez de baixar o
    arquivo pra pasta de destino. Default False preserva o comportamento
    de sempre (ex.: quem loga no Internet Archive via logar.py/
    resolver_na_mao não quer nem precisa disso).

    escondida=True (default False) resolve um problema descoberto na
    cadeia de tarefas C-nav1 a C-nav6 (ver relatórios em
    .superpowers/sdd/vamos-colocar-essas-coisas-federated-cherny/): a
    Gallica usa um desafio anti-robô ("Altcha", prova de trabalho via
    JavaScript) que só passa com uma janela REAL do Chrome (headless=True
    já foi testado ao vivo e falha -- o Chrome headless se identifica como
    tal e/ou não passa no desafio). Só que uma janela real de verdade na
    tela do Samuel toda vez que uma coleta automática roda é inaceitável.
    A solução tem DUAS peças, cada uma resolvendo um problema diferente
    que a C-nav5 descobriu ao testar ao vivo:

    1. POSIÇÃO FORA DA TELA (`window_position="-32000,-32000"`, técnica
       confirmada objetivamente pela C-nav5 via win32gui/win32api -- a
       janela abre genuinamente fora dos limites da tela virtual do
       Windows, nunca aparece pro Samuel, mas continua sendo uma janela
       "real" do ponto de vista do Chrome -- headless=False). A C-nav5
       testou essa técnica sozinha (sem a peça 2 abaixo) e viu que ela
       NÃO bastava: o download travava do mesmo jeito que headless=True já
       travava. A causa provável (documentada na C-nav5 e confirmada
       parcialmente na C-nav6): o Chromium tem um mecanismo interno de
       "occlusion tracker" que desacelera JavaScript (setTimeout/
       requestAnimationFrame) de janelas que ele julga "fora da tela" --
       o que atrapalha o desafio Altcha de terminar a tempo. Por isso
       "fora da tela" sozinho não resolve; precisa da peça 2.
    2. FLAG `--disable-backgrounding-occluded-windows` (passada via
       `chromium_arg`, parâmetro real do seleniumbase.Driver confirmado
       lendo `inspect.signature(Driver)` contra o pacote instalado --
       não é `chromium_arg` inventado). Essa flag desliga exatamente o
       "occlusion tracker" mencionado acima (é a flag oficial documentada
       pelo próprio Google Chrome/chrome-launcher pra esse fim, ver
       relatório da C-nav6). ANTES de usar essa flag, a C-nav6 fez uma
       verificação ética específica (Fase 1, com página de teste NEUTRA,
       sem nenhuma rede envolvida): a flag muda `document.visibilityState`
       ou `document.hidden` -- ou seja, faz o JavaScript da PRÓPRIA
       PÁGINA (o site) achar que a aba está visível quando não está? A
       resposta, testada ao vivo duas vezes e confirmada via win32gui +
       inspeção do processo real do Chrome (Win32_Process): NÃO. Com ou
       sem a flag, uma janela minimizada continua reportando
       `document.hidden == True` pro JavaScript da página -- a flag só
       evita desperdício de CPU/renderização internamente, nunca mente
       pro site sobre visibilidade. Por isso essa flag passa no mesmo
       padrão ético do resto do projeto (nunca disfarçar automação pro
       site -- CLAUDE.md §8.1): ela é só uma configuração de desempenho
       local do Chrome, igual escolher "não animar abas em segundo
       plano", e não um disfarce.

    A C-nav5 testou as duas técnicas de esconder (fora da tela E
    minimizar) separadamente, sem a flag, e as duas falharam do mesmo
    jeito -- por isso este parâmetro usa POSIÇÃO FORA DA TELA (não
    `minimize_window()`): é a técnica que a C-nav5 mediu como igualmente
    robusta pra esconder e que fica pronta desde a criação do Driver
    (`minimize_window()` exigiria uma chamada extra depois de abrir, com
    uma pequena janela de tempo em que a janela aparece real na tela antes
    de minimizar). A combinação final (fora da tela + a flag) nunca foi
    confirmada com um download real bem-sucedido contra a Gallica (a
    C-nav6 ficou bloqueada por um rate-limit 429 do próprio site antes de
    conseguir testar) -- ver o relatório da C-nav7 para o status dessa
    confirmação ao vivo, que continua pendente.

    default False preserva o comportamento de sempre pra quem já chama
    esta função hoje sem esse parâmetro (ex.: logar.py/resolver_na_mao,
    que abre uma janela visível DE PROPÓSITO pro Samuel resolver login/
    CAPTCHA na mão -- escondê-la seria contraproducente).

    IMPORTANTE ao usar o modo visivel: a janela que abre e' NOVA e
    ISOLADA -- sem historico, sem favorito, sem login nenhum do seu
    Chrome pessoal. Ignore qualquer pop-up do proprio Chrome sobre "fazer
    login no Chrome" ou sincronizar conta -- isso nao e' o site, e' o
    navegador. Os campos de login do SITE aparecem na pagina em si."""
    perfil = caminho_perfil(nome_perfil)
    perfil.mkdir(parents=True, exist_ok=True)
    # ! NUNCA passar uc=True, uc_cdp=True nem uc_sub=True aqui -- ver aviso
    # ! no topo do arquivo. Só os parâmetros normais de automação (sem disfarce).
    kwargs = dict(headless=headless, user_data_dir=str(perfil), external_pdf=external_pdf)
    if escondida:
        # Ver docstring acima (parâmetro escondida) pra explicação completa
        # de por que essas duas peças, juntas, resolvem "esconder a janela
        # sem travar o download" -- posição fora da tela (C-nav5) + flag de
        # anti-throttling (C-nav6, já confirmada ética: não muda o que o
        # site observa sobre visibilidade).
        kwargs["window_position"] = "-32000,-32000"
        kwargs["chromium_arg"] = "--disable-backgrounding-occluded-windows"
    return Driver(**kwargs)


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
