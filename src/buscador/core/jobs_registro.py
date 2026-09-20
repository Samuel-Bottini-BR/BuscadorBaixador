# -*- coding: utf-8 -*-
"""
O "registro de jobs" e a lista de todas as tarefas que o motor ja
iniciou -- rodando ou nao. Fica guardado num unico arquivo JSON
(jobs/registro.json), com o mesmo cuidado de escrita atomica que
core/checkpoint.py ja usa (grava num .tmp e so depois troca pelo arquivo
de verdade), pra nunca ficar corrompido se o programa for interrompido no
meio de uma gravacao.

Como o registro é lido e escrito por vários processos em paralelo, usa-se
um arquivo .lock para coordenar acesso (quem faz ler→modificar→salvar segura
a trava enquanto trabalha) e retry logic pra Windows, que às vezes nega
acesso momentaneamente.
"""
import contextlib
import json
import os
import time
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

CAMINHO_PADRAO = Path(__file__).resolve().parent.parent.parent.parent / "jobs" / "registro.json"
# sobe de src/buscador/core/ ate a raiz do projeto, depois entra em jobs/

TIMEOUT_TRAVA_SEGUNDOS = 10.0    # quanto tempo esperar pela trava antes de desistir
TRAVA_VELHA_SEGUNDOS = 5.0       # trava mais velha que isso é abandonada (dono morreu); DEVE ser < TIMEOUT
TENTATIVAS_WINDOWS = 10          # tentativas quando o Windows nega acesso momentaneamente
ESPERA_ENTRE_TENTATIVAS = 0.05   # segundos entre tentativas


def _com_tentativas(funcao):
    """Executa uma função, tentando novamente se o Windows negar acesso
    momentaneamente (PermissionError). Útil para leitura/escrita de arquivos
    que outro processo tem aberto por um instante."""
    for tentativa in range(TENTATIVAS_WINDOWS):
        try:
            return funcao()
        except PermissionError:
            if tentativa < TENTATIVAS_WINDOWS - 1:
                time.sleep(ESPERA_ENTRE_TENTATIVAS)
            else:
                raise


@contextlib.contextmanager
def trava_registro(caminho: Path = CAMINHO_PADRAO):
    """Context manager que garante acesso exclusivo ao arquivo de registro.

    Cria um arquivo .lock e só um processo consegue fazer isso por vez; os
    outros esperam. Trata travas antigas (processo morreu) como abandonadas.
    Quem faz ler→modificar→salvar DEVE segurar essa trava, pra evitar que
    dois processos sobrescrevam as mudanças um do outro:

        with trava_registro(caminho):
            jobs = carregar_registro(caminho)
            # modificar jobs
            salvar_registro(jobs, caminho)

    IMPORTANTE: Esta trava NÃO é reentrante. Dentro de `with trava_registro()`,
    chame `carregar_registro`/`salvar_registro` diretamente. Se chamar
    `adicionar_job()` ou `atualizar_job()` (que pegam a trava sozinhos), ficará
    preso num deadlock até o TimeoutError.

    Levanta TimeoutError se esperar mais de TIMEOUT_TRAVA_SEGUNDOS.
    """
    trava = caminho.with_suffix(caminho.suffix + ".lock")
    trava.parent.mkdir(parents=True, exist_ok=True)

    inicio = time.monotonic()
    while True:
        try:
            # Tenta criar o arquivo .lock. Só UM processo consegue (os outros
            # recebem FileExistsError ou PermissionError no Windows).
            fd = os.open(trava, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.close(fd)
            break  # Conseguiu a trava!
        except (FileExistsError, PermissionError):
            # Trava já existe. Pode ser:
            # 1) Outro processo tem (espera)
            # 2) Processo morreu e deixou a trava pra trás (remove)
            try:
                age = time.time() - trava.stat().st_mtime
                if age > TRAVA_VELHA_SEGUNDOS:
                    # Trava abandonada, remove
                    try:
                        trava.unlink()
                    except OSError:
                        pass  # Pode ter sido outro processo removendo também
                    continue  # Tenta novamente
            except OSError:
                pass  # stat falhou, ignora (outro processo pode estar mexendo)

            # Verifica timeout
            if time.monotonic() - inicio > TIMEOUT_TRAVA_SEGUNDOS:
                raise TimeoutError(
                    f"Não consegui a trava de {trava} após {TIMEOUT_TRAVA_SEGUNDOS}s"
                )

            # Espera e tenta novamente
            time.sleep(ESPERA_ENTRE_TENTATIVAS)

    try:
        yield
    finally:
        # Libera a trava
        try:
            trava.unlink()
        except FileNotFoundError:
            pass  # Alguém já removeu, tudo bem


@dataclass
class JobRegistrado:
    id: str
    modulo: str  # "cli" | "gallica_crawl" | "gallica_enriquecer"
    argv: list[str]
    pid: int
    estado: str  # "rodando" | "concluido" | "erro" | "parado" | "interrompido"
    log_path: str
    iniciado_em: str = ""
    atualizado_em: str = ""
    alvo: str = ""
    # o modulo Python de verdade que o executor roda (ex.: "buscador.gallica_crawl").
    # Gravado aqui porque o executor e um processo separado: so enxerga o que
    # esta em disco, nunca a memoria de quem iniciou o job.


def novo_id(modulo: str) -> str:
    """Gera um identificador legivel e unico pra um job novo: nome do
    modulo + um pedaco curto e aleatorio (evita colisao entre dois jobs
    do mesmo modulo iniciados quase ao mesmo tempo)."""
    return f"{modulo}-{uuid.uuid4().hex[:8]}"


def carregar_registro(caminho: Path = CAMINHO_PADRAO) -> list[JobRegistrado]:
    """Le a lista de jobs do disco. Se o arquivo ainda nao existe
    (primeira vez que o motor roda), devolve lista vazia em vez de erro.

    Usa retry logic pra evitar PermissionError quando outro processo tem o
    arquivo aberto momentaneamente no Windows."""
    if not caminho.exists():
        return []
    conteudo = _com_tentativas(lambda: caminho.read_text(encoding="utf-8"))
    dados = json.loads(conteudo)
    return [JobRegistrado(**item) for item in dados["jobs"]]


def salvar_registro(jobs: list[JobRegistrado], caminho: Path = CAMINHO_PADRAO) -> None:
    """Grava a lista inteira de jobs, num arquivo temporario primeiro e so
    depois troca pelo definitivo -- mesma tecnica de core/checkpoint.py,
    pra nunca deixar o registro pela metade se o programa for interrompido
    bem no meio da escrita.

    Usa um nome temporário único POR ESCRITOR (processo) pra evitar colisão
    com outros processos escrevendo ao mesmo tempo, e retry logic pra Windows.
    Quem chama DEVE estar dentro de 'with trava_registro(caminho):' pra
    coordenar com outros leitores/escritores."""
    caminho.parent.mkdir(parents=True, exist_ok=True)
    # Nome único por escritor: registo.json.<pid>.<uuid-curto>.tmp
    caminho_tmp = caminho.with_name(
        f"{caminho.name}.{os.getpid()}.{uuid.uuid4().hex[:8]}.tmp"
    )
    try:
        conteudo = {"jobs": [asdict(job) for job in jobs]}
        caminho_tmp.write_text(
            json.dumps(conteudo, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        _com_tentativas(lambda: os.replace(caminho_tmp, caminho))
    except Exception:
        # Se algo deu errado, tenta limpar o temporário antes de deixar o erro subir
        try:
            caminho_tmp.unlink()
        except FileNotFoundError:
            pass
        raise


def adicionar_job(job: JobRegistrado, caminho: Path = CAMINHO_PADRAO) -> None:
    """Le o registro atual, acrescenta um job novo, e salva de volta.

    Coordena com outros processos via trava pra evitar perda de atualizações."""
    with trava_registro(caminho):
        jobs = carregar_registro(caminho)
        jobs.append(job)
        salvar_registro(jobs, caminho)


def atualizar_job(id: str, caminho: Path = CAMINHO_PADRAO, **mudancas) -> JobRegistrado:
    """Le o registro, atualiza os campos informados (em **mudancas) do job
    com esse id, salva de volta, e devolve o job ja atualizado. Levanta
    ValueError se nenhum job tiver esse id.

    Coordena com outros processos via trava pra evitar perda de atualizações.
    A trava é liberada mesmo se ValueError for levantada."""
    with trava_registro(caminho):
        jobs = carregar_registro(caminho)
        for job in jobs:
            if job.id == id:
                for chave, valor in mudancas.items():
                    setattr(job, chave, valor)
                job.atualizado_em = datetime.now(timezone.utc).isoformat()
                salvar_registro(jobs, caminho)
                return job
        raise ValueError(f"Nenhum job encontrado com id '{id}'")
