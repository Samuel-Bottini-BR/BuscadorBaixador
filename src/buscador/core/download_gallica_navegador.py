# -*- coding: utf-8 -*-
"""
Tarefa C-nav1 (spike): tenta baixar o PDF de uma obra da Gallica usando um
navegador de verdade (via core/navegador.py), em vez do ClienteEducado/
requests simples que a Tarefa C1 já confirmou ao vivo que NÃO passa pelo
desafio anti-robô "Altcha" (prova de trabalho via JavaScript) no caminho
`<url-base>.pdf` -- ver `core/download_gallica.py` e o relatório da
Tarefa C1.

A pergunta que este módulo responde (ver o brief completo em
.superpowers/sdd/.../task-Cnav1-brief.md): um Chrome de verdade, controlado
por `seleniumbase` mas SEM nenhum modo de disfarce anti-detecção (nunca
`uc`/`uc_cdp`/`uc_sub` -- proibido, CLAUDE.md §8.1, mesmo aviso no topo de
`core/navegador.py`), roda o JavaScript da página normalmente e passa pelo
desafio sozinho -- do jeito que uma prova de trabalho é desenhada pra
deixar passar? Isso não é burlar o CAPTCHA: é só um navegador honesto
fazendo o que navegadores honestos fazem.

## Pesquisa feita antes de escrever este código (passo 1 do brief)

`seleniumbase.Driver()` (a função usada por `abrir_navegador`, ver
core/navegador.py) **não tem** nenhum parâmetro `downloads_folder` (nem
nome parecido) -- conferido lendo a assinatura real de
`seleniumbase.plugins.driver_manager.Driver()` no pacote instalado
(`.venv/Lib/site-packages/seleniumbase/plugins/driver_manager.py`), não
adivinhado. A pasta de download do Chrome é decidida internamente pelo
próprio SeleniumBase, fixa em
`seleniumbase.core.download_helper.get_downloads_folder()` --
`<pasta atual do processo>/downloaded_files`, calculada uma única vez
quando o pacote é importado, sem jeito de escolher outra pasta por
parâmetro do `Driver()`.

Por isso este módulo configura a pasta de download **depois** de o
navegador já estar aberto, usando o Chrome DevTools Protocol (CDP) --
`driver.execute_cdp_cmd("Page.setDownloadBehavior", {...})` --, uma
funcionalidade padrão e documentada do próprio Selenium/Chrome pra
redirecionar onde os downloads são salvos (o próprio SeleniumBase usa esse
mesmo comando internamente, ver `core/browser_launcher.py`). Isso não é
disfarce de automação nenhum -- é o equivalente a escolher "salvar em" numa
caixa de diálogo de download; não muda em nada como o navegador se
apresenta pro site nem como ele resolve o desafio Altcha.
"""
import time
from pathlib import Path

from buscador.core.download_gallica import descobrir_url_download
from buscador.core.http_educado import ClienteEducado
from buscador.core.navegador import abrir_navegador

USER_AGENT = (
    "BuscadorBaixador-InstitutoSaoBento/0.1 "
    "(uso não comercial, preservação de obras; contato: artesacra.quotidianus@gmail.com)"
)

# Extensão que o Chrome usa pro arquivo temporário enquanto um download
# ainda está em andamento (some sozinha quando o download termina, viram o
# nome final). Um arquivo com essa extensão NÃO conta como "download
# pronto" -- ver esperar_novo_arquivo.
SUFIXO_DOWNLOAD_PARCIAL = ".crdownload"

TIMEOUT_PADRAO_SEGUNDOS = 60.0
INTERVALO_PADRAO_SEGUNDOS = 1.0


class DownloadNaoConcluidoError(Exception):
    """Levantado quando nenhum arquivo novo e completo apareceu na pasta de
    destino dentro do tempo limite -- sinal de que o navegador não
    conseguiu concluir o download (ex.: o desafio anti-robô não passou
    sozinho, o Chrome renderizou o PDF na tela em vez de baixar, ou
    qualquer outra coisa inesperada aconteceu). Nunca finge sucesso."""


def montar_url_pdf(url_base: str) -> str:
    """Monta a URL de download direto do PDF a partir da URL-base do
    documento devolvida por `descobrir_url_download` -- o mesmo padrão
    `<base>.pdf` que a Tarefa C1 confirmou ao vivo estar bloqueado por
    HTTP simples (e que esta tarefa testa se um navegador de verdade
    consegue passar)."""
    return url_base.rstrip("/") + ".pdf"


def _listar_arquivos(pasta_destino: Path) -> set:
    """Devolve o conjunto de arquivos (Path) que existem agora dentro de
    pasta_destino -- usado como "antes"/"depois" pra descobrir o que é
    novo. Se a pasta ainda não existir, devolve um conjunto vazio (em vez
    de dar erro) -- útil pra checar o "antes" antes mesmo de garantir que
    a pasta foi criada."""
    if not pasta_destino.exists():
        return set()
    return {item for item in pasta_destino.iterdir() if item.is_file()}


def esperar_novo_arquivo(
    pasta_destino: Path,
    arquivos_antes: set,
    timeout_segundos: float = TIMEOUT_PADRAO_SEGUNDOS,
    intervalo_segundos: float = INTERVALO_PADRAO_SEGUNDOS,
) -> Path:
    """Espera até aparecer, dentro de pasta_destino, um arquivo COMPLETO
    (não um `.crdownload` parcial) que não estava em arquivos_antes --
    faz polling (checa de tempos em tempos) até o timeout estourar. Essa
    lógica é isolada de qualquer coisa do Selenium de propósito, pra dar
    pra testar sem abrir navegador nenhum (ver
    tests/test_download_gallica_navegador.py).

    Args:
        pasta_destino: pasta onde o navegador deveria estar salvando o download.
        arquivos_antes: conjunto de Path que já existiam na pasta antes do
            download começar (ver _listar_arquivos).
        timeout_segundos: quanto tempo esperar no total antes de desistir.
        intervalo_segundos: quanto tempo esperar entre uma checagem e outra.

    Returns:
        O Path do primeiro arquivo novo e completo encontrado.

    Raises:
        DownloadNaoConcluidoError: se nenhum arquivo novo e completo
            aparecer dentro do timeout.
    """
    limite = time.monotonic() + timeout_segundos
    while True:
        atuais = _listar_arquivos(pasta_destino)
        novos = atuais - arquivos_antes
        completos = sorted(
            (item for item in novos if item.suffix != SUFIXO_DOWNLOAD_PARCIAL),
            key=lambda item: item.name,
        )
        if completos:
            return completos[0]
        if time.monotonic() >= limite:
            nomes_atuais = sorted(item.name for item in atuais)
            raise DownloadNaoConcluidoError(
                f"Nenhum arquivo novo e completo apareceu em {pasta_destino} "
                f"depois de {timeout_segundos:.0f}s de espera -- o navegador "
                "provavelmente não concluiu o download (o desafio anti-robô "
                "pode não ter passado sozinho, o Chrome pode ter aberto o "
                "PDF na tela em vez de baixar, ou outra coisa inesperada "
                f"aconteceu). Arquivos atualmente na pasta: {nomes_atuais or '(nenhum)'}"
            )
        time.sleep(intervalo_segundos)


def baixar_via_navegador(
    ark_id: str,
    pasta_destino: Path,
    indice_pagina: int = 1,
    headless: bool = True,
    timeout_segundos: float = TIMEOUT_PADRAO_SEGUNDOS,
) -> Path:
    """Tenta baixar o PDF de uma página de uma obra da Gallica usando um
    navegador de verdade (spike da Tarefa C-nav1 -- ver docstring do
    módulo).

    Passos:
    1. Acha a URL-base do documento via `descobrir_url_download` (rápido,
       não precisa de navegador -- usa um `ClienteEducado` próprio).
    2. Abre um Chrome isolado via `abrir_navegador('gallica', ...)` (reusa
       core/navegador.py tal e qual, sem nenhum parâmetro de disfarce).
    3. Configura, via CDP, esse Chrome pra salvar downloads em
       pasta_destino (ver docstring do módulo -- Driver() não tem
       parâmetro pra isso).
    4. Navega até `<url-base>.pdf` (o padrão que a Tarefa C1 confirmou
       bloqueado por HTTP simples).
    5. Espera um arquivo novo aparecer em pasta_destino (polling).

    Args:
        ark_id: identificador canônico da obra (ex.: "bpt6k6382082m").
        pasta_destino: pasta onde o PDF deve ser salvo (é criada se não existir).
        indice_pagina: número da página dentro da obra (1 = primeira).
        headless: False abre a janela do Chrome visível (pra observar o
            que acontece de verdade); True roda invisível.
        timeout_segundos: quanto tempo esperar o download terminar antes
            de desistir e levantar erro.

    Returns:
        O Path do arquivo baixado.

    Raises:
        DownloadNaoConcluidoError: se nenhum arquivo novo aparecer dentro
            do timeout -- nunca finge sucesso.
    """
    pasta_destino = Path(pasta_destino)
    pasta_destino.mkdir(parents=True, exist_ok=True)

    cliente = ClienteEducado(USER_AGENT)
    url_base = descobrir_url_download(ark_id, cliente, indice_pagina=indice_pagina)
    url_pdf = montar_url_pdf(url_base)

    arquivos_antes = _listar_arquivos(pasta_destino)

    driver = abrir_navegador("gallica", headless=headless, external_pdf=True)
    try:
        # Redireciona onde ESSE navegador salva downloads -- ver docstring
        # do módulo sobre por que isso é feito via CDP e não por parâmetro
        # do Driver(). "allow" quer dizer "baixe de verdade" (em vez de
        # "deny", que bloquearia, ou deixar o padrão do Chrome perguntar).
        driver.execute_cdp_cmd(
            "Page.setDownloadBehavior",
            {"behavior": "allow", "downloadPath": str(pasta_destino)},
        )
        driver.get(url_pdf)
        return esperar_novo_arquivo(pasta_destino, arquivos_antes, timeout_segundos=timeout_segundos)
    finally:
        # Mesmo padrão de resolver_na_mao (core/navegador.py): fecha o
        # navegador sempre, mesmo se algo der errado no meio.
        driver.quit()
