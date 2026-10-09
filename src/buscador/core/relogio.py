# -*- coding: utf-8 -*-
"""
Confere se o relógio do PC está certo -- e acerta, no Windows.

Por que existe: em 09/10/2026 o download parou sem aviso porque o relógio do
PC estava ~47 s atrasado. O tdl (que baixa do Telegram) recusa as mensagens
do servidor quando a diferença passa de ~30 s ("bad message id ... created
too far in future"). O Telethon corrige sozinho; o tdl não.

Como mede: pergunta a hora para um site confiável (o cabeçalho "Date" que
todo servidor web devolve) e compara com a hora do PC. Precisão de ~1 s,
suficiente aqui.
"""
import email.utils
import subprocess
import time
from pathlib import Path

import httpx

from buscador.core.registro_erros import PASTA_LOGS

SITES_DE_HORA = ("https://www.google.com", "https://www.cloudflare.com", "https://web.telegram.org")
LIMITE_SEGUNDOS = 10  # acima disso, avisamos (o tdl quebra a partir de ~30 s)

# Script que acerta o relógio do Windows (precisa de administrador): liga o
# serviço de horário (e deixa automático), aponta para o ntp.br (oficial do
# Brasil) com a Microsoft de reserva, e força a sincronização agora.
SCRIPT_ACERTAR = """\
Set-Service w32time -StartupType Automatic
Start-Service w32time
w32tm /config /manualpeerlist:"a.st1.ntp.br,0x9 time.windows.com,0x9" /syncfromflags:manual /update
w32tm /resync /force
"""


def diferenca_do_relogio(sites=SITES_DE_HORA, cliente=None) -> float | None:
    """Quantos segundos o relógio do PC está ADIANTADO (positivo) ou
    ATRASADO (negativo) em relação à hora certa. None se não deu para medir
    (sem internet)."""
    cliente = cliente or httpx.Client(timeout=10, follow_redirects=False)
    for site in sites:
        try:
            antes = time.time()
            resposta = cliente.head(site)
            depois = time.time()
            data = resposta.headers.get("date")
            if not data:
                continue
            hora_certa = email.utils.parsedate_to_datetime(data).timestamp()
            # o servidor anotou a hora em algum momento entre "antes" e "depois";
            # o cabeçalho corta os milissegundos, por isso somamos 0,5 s
            hora_pc = (antes + depois) / 2
            return round(hora_pc - (hora_certa + 0.5), 1)
        except (httpx.HTTPError, ValueError, TypeError):
            continue
    return None


def relogio_ok(diferenca: float | None, limite: float = LIMITE_SEGUNDOS) -> bool:
    """True se a diferença é pequena (ou se não deu para medir -- nesse caso
    não travamos nada, só seguimos)."""
    return diferenca is None or abs(diferenca) <= limite


def descrever(diferenca: float | None) -> str:
    if diferenca is None:
        return "Não consegui conferir o relógio (sem internet?)."
    if abs(diferenca) <= LIMITE_SEGUNDOS:
        return f"Relógio do PC certo (diferença de {abs(diferenca):.0f} s)."
    sentido = "atrasado" if diferenca < 0 else "adiantado"
    return f"O relógio do PC está {abs(diferenca):.0f} s {sentido}. Isso trava o download do Telegram."


def acertar_relogio_windows(pasta: Path = PASTA_LOGS) -> bool:
    """Grava SCRIPT_ACERTAR num arquivo .ps1 e roda como administrador. O
    Windows mostra a pergunta "Deseja permitir...?" -- basta clicar Sim.
    (Um arquivo .ps1 evita a confusão de aspas dentro de aspas.)
    Devolve False se não estiver no Windows."""
    if not hasattr(subprocess, "CREATE_NO_WINDOW"):  # só existe no Windows
        return False
    pasta.mkdir(parents=True, exist_ok=True)
    script = pasta / "acertar_relogio.ps1"
    script.write_text(SCRIPT_ACERTAR, encoding="utf-8")
    subprocess.run(
        ["powershell", "-NoProfile", "-Command",
         "Start-Process powershell -Verb RunAs -Wait -WindowStyle Hidden "
         f"-ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-File','{script}'"],
        check=False,
    )
    return True
