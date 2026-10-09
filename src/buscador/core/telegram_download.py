# -*- coding: utf-8 -*-
"""
Pastas, escolha e download dos arquivos de um tópico do Telegram.

Quem LISTA é o Telethon (core/telegram_busca.py). Quem BAIXA continua sendo
o tdl, pelo scripts/telegram/baixar_topico.sh -- este módulo prepara tudo
para ele e acompanha o andamento:

- onde fica cada coisa (pasta_alvo, caminho_lista, pasta_arquivos...):
    saidas/telegram/topico_<id>/            (grupo com tópicos)
    saidas/telegram/chat_<id do grupo>/     (grupo/conversa sem tópicos)
  dentro de cada uma: a lista (<nome>_lista_busca.json), a lista só com os
  marcados, o log das rodadas e a pasta arquivos/;
- o que já foi baixado (ids_baixados): o tdl salva "<nº da mensagem>_<nome>",
  então o número no começo do nome diz qual mensagem já veio;
- a tabela de escolha (linhas_da_lista) e a lista dos marcados (filtrar_lista);
- iniciar o download em segundo plano sem travar a tela, sem deixar começar
  um segundo download do mesmo tópico (arquivo download.pid);
- os repetidos: só é cópia se o conteúdo for IDÊNTICO (impressão digital
  SHA-256). As cópias vão TODAS para repetidos/, lado a lado. Nada é apagado.

Todas as funções recebem as pastas por parâmetro -- nos testes, uma pasta
temporária; sem internet e sem tdl de verdade.
"""
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from buscador.core.config_sites import CAMINHO_PADRAO
from buscador.core.escrita_atomica import salvar_json_atomico

RAIZ_PROJETO = CAMINHO_PADRAO.parent
SCRIPT_BAIXAR = RAIZ_PROJETO / "scripts" / "telegram" / "baixar_topico.sh"
SCRIPT_PLANILHA = RAIZ_PROJETO / "scripts" / "telegram" / "planilha_topico.py"

# Onde o Git Bash costuma ficar no Windows (o baixar_topico.sh é um script
# de bash; no Windows quem roda bash é o Git for Windows).
BASH_WINDOWS = [
    Path(r"C:\Program Files\Git\bin\bash.exe"),
    Path(r"C:\Program Files (x86)\Git\bin\bash.exe"),
    Path(os.environ.get("LOCALAPPDATA", r"C:\Users\Default\AppData\Local")) / "Programs" / "Git" / "bin" / "bash.exe",
]

# Últimas linhas que o baixar_topico.sh escreve no log quando termina.
FINAIS_DO_LOG = ("COMPLETO", "SEM PROGRESSO", "LIMITE DE RODADAS")


# --- onde fica cada coisa ---------------------------------------------------

def nome_alvo(chat_id: int, topico_id: int | None) -> str:
    """"topico_783" (grupo com tópicos) ou "chat_2136545743" (sem tópicos).
    O padrão topico_<id> é o mesmo que o telegram.bat já usa."""
    return f"topico_{topico_id}" if topico_id is not None else f"chat_{chat_id}"


def pasta_alvo(base: Path, chat_id: int, topico_id: int | None) -> Path:
    return base / nome_alvo(chat_id, topico_id)


def caminho_lista(pasta: Path) -> Path:
    """A lista completa vinda da busca do Telegram (formato do tdl)."""
    return pasta / f"{pasta.name}_lista_busca.json"


def caminho_marcados(pasta: Path) -> Path:
    """A lista só com o que foi marcado para baixar (é o que o tdl recebe)."""
    return pasta / f"{pasta.name}_marcados.json"


def caminho_log(pasta: Path) -> Path:
    return pasta / "rodadas.log"


def caminho_pid(pasta: Path) -> Path:
    return pasta / "download.pid"


def pasta_arquivos(pasta: Path) -> Path:
    return pasta / "arquivos"


# --- o que já está baixado ----------------------------------------------------

def _id_do_nome(nome: str) -> int | None:
    """"60824_Apparatus.pdf" -> 60824 (como o tdl salva);
    "Apparatus - msg 60824.pdf" -> 60824 (como fica em repetidos/)."""
    if nome.endswith(".tmp"):
        return None  # download pela metade -- ainda não conta
    if m := re.match(r"(\d+)_", nome):
        return int(m.group(1))
    if m := re.search(r" - msg (\d+)(\.[^.\s]*)?$", nome):
        return int(m.group(1))
    return None


def ids_baixados(pasta_arq: Path) -> set[int]:
    """Números das mensagens cujo arquivo já está na pasta (inclusive os que
    foram para repetidos/)."""
    ids = set()
    for raiz in (pasta_arq, pasta_arq / "repetidos"):
        if raiz.is_dir():
            for p in raiz.iterdir():
                if p.is_file() and (i := _id_do_nome(p.name)) is not None:
                    ids.add(i)
    return ids


def ler_lista(caminho: Path) -> dict:
    return json.loads(caminho.read_text(encoding="utf-8"))


def situacao(pasta: Path, rodando: bool = False) -> str:
    """Resumo em uma palavra para a tabela de tópicos:
    "baixando", "baixado", "baixado em parte (x de y)", "lista pronta" ou
    "não listado"."""
    if rodando:
        return "baixando"
    lista = caminho_lista(pasta)
    baixados = ids_baixados(pasta_arquivos(pasta))
    if lista.exists():
        if not baixados:
            return "lista pronta"
        ids = {m["id"] for m in ler_lista(lista)["messages"]}
        if ids <= baixados:
            return "baixado"
        return f"baixado em parte ({len(ids & baixados)} de {len(ids)})"
    return "baixado" if baixados else "não listado"


# --- a tabela de escolha --------------------------------------------------------

# Tipo curto de cada arquivo (para o filtro da tela). Mesma ideia dos grupos
# do planilha_topico.py: primeiro pela extensão, depois pelo tipo MIME.
TIPOS = [
    ("PDF", {"pdf"}, ("application/pdf",)),
    ("EPUB/MOBI", {"epub", "mobi", "azw", "azw3", "fb2"}, ("application/epub",)),
    ("DJVU", {"djvu", "djv"}, ("image/vnd.djvu",)),
    ("DOC/TXT", {"doc", "docx", "odt", "rtf", "txt"}, ("application/msword", "text/")),
    ("RAR/ZIP", {"zip", "rar", "7z", "tar", "gz"},
     ("application/zip", "application/rar", "application/x-rar", "application/x-7z", "application/vnd.rar")),
    ("Vídeo", {"mp4", "mkv", "avi", "mov", "webm"}, ("video/",)),
    ("Áudio", {"mp3", "m4a", "ogg", "opus", "wav", "flac"}, ("audio/",)),
    ("Imagem", {"jpg", "jpeg", "png", "gif", "tif", "tiff"}, ("image/",)),
]


def tipo_arquivo(nome: str, mime: str) -> str:
    ext = os.path.splitext(nome or "")[1].lower().lstrip(".")
    for rotulo, extensoes, _ in TIPOS:
        if ext in extensoes:
            return rotulo
    for rotulo, _, mimes in TIPOS:
        if any((mime or "").startswith(m) for m in mimes):
            return rotulo
    return "Outros"


def _documento(mensagem: dict) -> dict:
    return ((mensagem.get("raw") or {}).get("Media") or {}).get("Document") or {}


def linhas_da_lista(lista: dict, baixados: set[int]) -> list[dict]:
    """Uma linha por arquivo, pronta para a tabela da tela.
    Já vem marcado para baixar tudo o que ainda NÃO está na pasta."""
    linhas = []
    for m in lista["messages"]:
        doc = _documento(m)
        ja = m["id"] in baixados
        linhas.append({
            "baixar": not ja,
            "id": m["id"],
            "arquivo": m.get("file", ""),
            "tipo": tipo_arquivo(m.get("file", ""), doc.get("MimeType", "")),
            "tamanho_mb": round(int(doc.get("Size") or 0) / 1024**2, 1),
            "data": datetime.fromtimestamp(m["date"]).strftime("%d/%m/%Y") if m.get("date") else "",
            "ja_baixado": ja,
        })
    return linhas


def tamanhos_por_id(lista: dict) -> dict[int, int]:
    return {m["id"]: int(_documento(m).get("Size") or 0) for m in lista["messages"]}


def filtrar_lista(lista: dict, ids) -> dict:
    """A mesma lista (mesmo formato, com o "raw"), só com as mensagens
    escolhidas -- é o arquivo que o baixar_topico.sh recebe."""
    ids = set(ids)
    return {"id": lista["id"], "messages": [m for m in lista["messages"] if m["id"] in ids]}


def gravar_marcados(lista: dict, ids, pasta: Path) -> Path:
    destino = caminho_marcados(pasta)
    pasta.mkdir(parents=True, exist_ok=True)
    salvar_json_atomico(filtrar_lista(lista, ids), destino)
    return destino


def progresso(pasta: Path) -> dict | None:
    """Quanto do último download (a lista de marcados) já está na pasta.
    Sem lista de marcados -> None."""
    marcados = caminho_marcados(pasta)
    if not marcados.exists():
        return None
    tamanhos = tamanhos_por_id(ler_lista(marcados))
    prontos = ids_baixados(pasta_arquivos(pasta)) & set(tamanhos)
    return {
        "baixados": len(prontos), "total": len(tamanhos),
        "bytes_baixados": sum(tamanhos[i] for i in prontos),
        "bytes_total": sum(tamanhos.values()),
    }


def ultimas_linhas(caminho: Path, n: int = 8) -> list[str]:
    if not caminho.exists():
        return []
    linhas = caminho.read_text(encoding="utf-8", errors="replace").splitlines()
    return linhas[-n:]


# --- o processo de download ----------------------------------------------------

# Processos iniciados por ESTE aplicativo (pid -> Popen). Serve para saber
# com certeza se ainda estão rodando (e para o sistema "recolher" os que
# terminaram). Se o app for fechado e aberto de novo, o dicionário começa
# vazio e usamos o jeito do sistema operacional (processo_vivo).
_PROCESSOS: dict[int, subprocess.Popen] = {}


def processo_vivo(pid: int) -> bool | None:
    """True = rodando, False = terminou, None = não deu para saber."""
    if pid in _PROCESSOS:
        return _PROCESSOS[pid].poll() is None
    if os.name == "nt":
        try:
            saida = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
                capture_output=True, text=True, timeout=10,
            ).stdout
        except (OSError, subprocess.SubprocessError):
            return None
        # Linha do tipo: "bash.exe","1234",... -- confere o número E que é
        # um bash (o Windows reaproveita números de processos que acabaram).
        return f'"{pid}"' in saida and "bash" in saida.lower()
    try:
        os.kill(pid, 0)  # sinal 0 = "só confere se existe", não faz nada
    except ProcessLookupError:
        return False
    except PermissionError:
        return True  # existe, só é de outro usuário
    except OSError:
        return None
    return True


def download_rodando(pasta: Path) -> bool | None:
    """Há um download deste tópico rodando? Lê o download.pid da pasta.
    O log dizer que terminou (COMPLETO etc.) também vale como "não"."""
    arquivo = caminho_pid(pasta)
    if not arquivo.exists():
        return False
    try:
        pid = int(arquivo.read_text(encoding="utf-8").strip())
    except ValueError:
        return None
    if pid in _PROCESSOS:  # iniciado por este app: aqui temos certeza
        return _PROCESSOS[pid].poll() is None
    ultimas = ultimas_linhas(caminho_log(pasta), 1)
    if ultimas and ultimas[0].startswith(FINAIS_DO_LOG):
        return False
    return processo_vivo(pid)


def achar_bash() -> Path | None:
    """Onde está o bash. No Windows, só o do Git for Windows (o "bash" do
    System32 é o do WSL, que não enxerga os caminhos do mesmo jeito)."""
    if os.name == "nt":
        return next((p for p in BASH_WINDOWS if p.exists()), None)
    achado = shutil.which("bash")
    return Path(achado) if achado else None


def _caminho_para_bash(caminho: Path) -> str:
    """D:\\pasta\\x -> D:/pasta/x (o Git Bash aceita barras normais)."""
    return Path(caminho).resolve().as_posix()


def montar_comando(bash: Path, lista: Path, destino: Path, log: Path,
                   script: Path = SCRIPT_BAIXAR) -> list[str]:
    return [str(bash), _caminho_para_bash(script), _caminho_para_bash(lista),
            _caminho_para_bash(destino), _caminho_para_bash(log)]


def iniciar_download(pasta: Path, bash: Path, script: Path = SCRIPT_BAIXAR,
                     ambiente_extra: dict | None = None) -> int:
    """Dispara o baixar_topico.sh em SEGUNDO PLANO com a lista de marcados
    e devolve o número do processo (PID). A tela não fica travada: dá para
    fechar a aba e voltar depois -- o andamento é lido da pasta.

    Recusa (RuntimeError) se já houver um download deste tópico rodando,
    ou se não der para ter certeza de que o anterior acabou."""
    rodando = download_rodando(pasta)
    if rodando:
        raise RuntimeError("Já existe um download deste tópico rodando.")
    if rodando is None:
        raise RuntimeError(
            "Não consegui conferir se o download anterior deste tópico ainda está "
            f"rodando. Se tiver certeza de que acabou, apague o arquivo {caminho_pid(pasta)}."
        )
    lista = caminho_marcados(pasta)
    if not lista.exists():
        raise RuntimeError("Marque os arquivos e grave a lista antes de baixar.")
    destino = pasta_arquivos(pasta)
    destino.mkdir(parents=True, exist_ok=True)
    log = caminho_log(pasta)
    # Uma linha no log já marca que começou (assim o "COMPLETO" de uma vez
    # anterior não é confundido com o fim DESTE download).
    with open(log, "a", encoding="utf-8") as f:
        f.write(f"{datetime.now():%H:%M} iniciado pelo aplicativo\n")
    # O script usa o MESMO Python deste aplicativo (variável PY).
    ambiente = {**os.environ, "PY": _caminho_para_bash(Path(sys.executable)),
                **(ambiente_extra or {})}
    comando = montar_comando(bash, lista, destino, log, script)
    if os.name == "nt":
        pid = _iniciar_independente_windows(comando, ambiente, pasta)
    else:
        saida = open(pasta / "download_saida.log", "a", encoding="utf-8")
        processo = subprocess.Popen(
            comando, stdout=saida, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
            env=ambiente, cwd=str(pasta), start_new_session=True,
        )
        saida.close()  # o processo filho tem a cópia dele; a nossa pode fechar
        _PROCESSOS[processo.pid] = processo
        pid = processo.pid
    caminho_pid(pasta).write_text(str(pid), encoding="utf-8")
    return pid


def _iniciar_independente_windows(comando: list[str], ambiente: dict, pasta: Path) -> int:
    """Inicia o download de um jeito que SOBREVIVE a fechar a janela preta do app.

    Problema real (09/10/2026): o download começou, baixou 54 arquivos e
    morreu quando o Samuel fechou a janela. O Windows Terminal coloca tudo o
    que nasce dele numa "caixa" (job) e, ao fechar, mata a caixa inteira.

    Tentativa 1: pedir para o processo SAIR da caixa (CREATE_BREAKAWAY_FROM_JOB).
    Tentativa 2 (se o Windows não deixar sair): pedir ao próprio Windows
    (serviço WMI) que crie o processo -- aí ele nasce fora da caixa."""
    flags = (subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW
             | subprocess.CREATE_BREAKAWAY_FROM_JOB)
    saida = open(pasta / "download_saida.log", "a", encoding="utf-8")
    try:
        processo = subprocess.Popen(
            comando, stdout=saida, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
            env=ambiente, cwd=str(pasta), creationflags=flags,
        )
        saida.close()
        _PROCESSOS[processo.pid] = processo
        return processo.pid
    except OSError:
        saida.close()
    # Tentativa 2: WMI. O comando vai num .ps1 (evita confusão de aspas).
    linha = subprocess.list2cmdline(comando)
    script = pasta / "download_iniciar.ps1"
    script.write_text(
        "$r = Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{\n"
        f"  CommandLine = @'\n{linha}\n'@\n"
        f"  CurrentDirectory = @'\n{pasta}\n'@\n"
        "}\n"
        "Write-Output $r.ProcessId\n",
        encoding="utf-8",
    )
    resultado = subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script)],
        capture_output=True, text=True, timeout=60,
    )
    try:
        return int(resultado.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        raise RuntimeError(
            "Não consegui iniciar o download em segundo plano. "
            f"Detalhes: {resultado.stderr.strip()[:500]}"
        ) from None


def comando_planilha(lista: Path, saida: Path, chat_id: int, topico_id: int | None,
                     nome: str, nome_grupo: str) -> list[str]:
    """python planilha_topico.py <lista> <saida.xlsx> <tópico> <nome> <chat> <grupo>
    (tópico 0 = conversa sem tópicos)."""
    return [sys.executable, str(SCRIPT_PLANILHA), str(lista), str(saida),
            str(topico_id or 0), nome, str(chat_id), nome_grupo]


# --- repetidos (SHA-256) -------------------------------------------------------

def sha256(caminho: Path, bloco: int = 1024 * 1024) -> str:
    """A "impressão digital" do conteúdo: arquivos com o mesmo SHA-256 têm
    exatamente os mesmos bytes. Lê aos pedaços (arquivos de vários GB)."""
    h = hashlib.sha256()
    with open(caminho, "rb") as f:
        while pedaco := f.read(bloco):
            h.update(pedaco)
    return h.hexdigest()


def achar_repetidos(pasta_arq: Path) -> list[list[Path]]:
    """Grupos de arquivos com conteúdo IDÊNTICO na pasta (sem olhar dentro
    de repetidos/). Mesmo nome e mesmo tamanho NÃO bastam -- só o SHA-256.
    Para não calcular à toa, só compara arquivos de tamanho igual."""
    if not pasta_arq.is_dir():
        return []
    por_tamanho = defaultdict(list)
    for p in pasta_arq.iterdir():
        if p.is_file() and not p.name.endswith(".tmp"):
            por_tamanho[p.stat().st_size].append(p)
    grupos = []
    for candidatos in por_tamanho.values():
        if len(candidatos) < 2:
            continue
        por_hash = defaultdict(list)
        for p in candidatos:
            por_hash[sha256(p)].append(p)
        grupos += [sorted(g) for g in por_hash.values() if len(g) > 1]
    return sorted(grupos)


def nome_em_repetidos(nome: str) -> str:
    """"60824_Apparatus.pdf" -> "Apparatus - msg 60824.pdf" (os dois de
    cada par ficam lado a lado na pasta, em ordem alfabética)."""
    m = re.match(r"(\d+)_(.*)", nome)
    if not m:
        return nome
    msg, resto = m.groups()
    base, ext = os.path.splitext(resto)
    return f"{base} - msg {msg}{ext}"


def mover_repetidos(grupos: list[list[Path]], pasta_arq: Path) -> list[tuple[Path, Path]]:
    """Move TODOS os arquivos de cada grupo de idênticos para repetidos/.
    Nunca apaga e nunca escreve por cima: se o nome já existir lá, pula."""
    destino_pasta = pasta_arq / "repetidos"
    destino_pasta.mkdir(exist_ok=True)
    movidos = []
    for grupo in grupos:
        for origem in grupo:
            destino = destino_pasta / nome_em_repetidos(origem.name)
            if destino.exists() or not origem.exists():
                continue
            origem.rename(destino)
            movidos.append((origem, destino))
    return movidos
