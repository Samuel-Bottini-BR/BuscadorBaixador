# -*- coding: utf-8 -*-
# src/buscador/core/jobs_motor.py
"""
O motor de verdade: sabe iniciar um job como processo separado do Windows,
checar se ainda esta vivo, parar, e reaproveitar o progresso salvo (via
checkpoint) pra mostrar status. Cada job roda isolado -- um travar ou
crashar nunca derruba o motor nem os outros jobs, porque nao existe
nenhum processo "supervisor" ligado o tempo todo (ver o desenho em
docs/superpowers/specs/2026-09-17-motor-de-jobs-design.md).
"""
import json
import math
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from buscador.core.checkpoint import Checkpoint, slug_consulta
from buscador.core.enriquecimento_lote import CheckpointEnriquecimento
from buscador.core.jobs_registro import (
    CAMINHO_PADRAO,
    JobRegistrado,
    adicionar_job,
    atualizar_job,
    carregar_registro,
    novo_id,
    salvar_registro,
    trava_registro,
)

RAIZ_PROJETO = Path(__file__).resolve().parent.parent.parent.parent
PASTA_JOBS = RAIZ_PROJETO / "jobs"
SAIDAS = RAIZ_PROJETO / "saidas"

MODULOS_PERMITIDOS = {
    "cli": "buscador.cli",
    "gallica_crawl": "buscador.gallica_crawl",
    "gallica_enriquecer": "buscador.gallica_enriquecer",
}
# lista fechada de proposito -- iniciar um modulo que nao esteja aqui e um
# erro claro, em vez do motor rodar qualquer comando arbitrario do sistema.
# "logar" fica de fora de proposito: ele e interativo (espera o Samuel
# apertar Enter no terminal), e um job roda sem terminal nenhum.

_FLAGS_DESTACADO = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
# DETACHED_PROCESS: o processo novo nao herda o terminal de quem o lancou;
# CREATE_NEW_PROCESS_GROUP: vira lider de um grupo proprio de processos


def _lancar_destacado(comando: list[str]) -> subprocess.Popen:
    """Lanca um processo que continua vivo mesmo se quem o lancou (o
    terminal, ou a conversa do Claude Code) for fechado -- foi exatamente
    o que faltou na coleta da Gallica que morreu junto com a sessao. Tenta
    primeiro tambem sair do "job object" do Windows de quem lancou
    (CREATE_BREAKAWAY_FROM_JOB); se o Windows negar (o pai nao permite),
    tenta de novo sem isso."""
    argumentos = dict(
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        close_fds=True,
    )
    try:
        return subprocess.Popen(
            comando, creationflags=_FLAGS_DESTACADO | subprocess.CREATE_BREAKAWAY_FROM_JOB,
            **argumentos,
        )
    except OSError:
        return subprocess.Popen(comando, creationflags=_FLAGS_DESTACADO, **argumentos)


def iniciar_job(modulo: str, argv: list[str], caminho_registro: Path = CAMINHO_PADRAO) -> JobRegistrado:
    """Inicia um job novo: cria a pasta de log dele, e lanca um processo
    "executor" (destacado, separado deste) responsavel por rodar o comando
    de verdade e atualizar o registro quando terminar. O motor guarda o PID
    desse executor -- pare-lo (parar_job) mata o executor e o comando real
    junto, porque um e processo-filho do outro."""
    if modulo not in MODULOS_PERMITIDOS:
        raise ValueError(
            f"Modulo '{modulo}' nao e um job conhecido. Opcoes: {sorted(MODULOS_PERMITIDOS)}"
        )

    id_job = novo_id(modulo)
    pasta_job = PASTA_JOBS / id_job
    pasta_job.mkdir(parents=True, exist_ok=True)
    caminho_log = pasta_job / "log.txt"

    job = JobRegistrado(
        id=id_job, modulo=modulo, argv=list(argv), pid=0, estado="rodando",
        log_path=str(caminho_log), iniciado_em=datetime.now(timezone.utc).isoformat(),
        alvo=MODULOS_PERMITIDOS[modulo],
        # o modulo Python de verdade fica gravado no registro: o executor e
        # um processo separado e so enxerga o que esta em disco
    )
    adicionar_job(job, caminho_registro)
    # grava o job no registro ANTES de lancar o processo executor porque o
    # executor le o registro assim que sobe -- se o job ainda nao estivesse
    # la, ele nao acharia nada pra executar

    try:
        processo = _lancar_destacado(
            [sys.executable, "-m", "buscador.core.jobs_executor", id_job, str(caminho_registro)]
        )
    except Exception:
        atualizar_job(id_job, caminho_registro, estado="erro")
        raise
    # se o lancamento falhar, o job ja esta no registro (gravado acima): marca
    # como "erro" pra nao sobrar um "rodando" fantasma com pid 0, e deixa a
    # excecao subir pra quem chamou saber que o job nao comecou
    return atualizar_job(id_job, caminho_registro, pid=processo.pid)


def executar_job(id_job: str, caminho_registro: Path = CAMINHO_PADRAO) -> None:
    """Roda DENTRO do processo executor (lancado por iniciar_job): executa
    o comando de verdade do job, esperando ele terminar, e atualiza o
    registro com o resultado. Nunca deve ser chamado diretamente -- so via
    'python -m buscador.core.jobs_executor <id> <registro>'."""
    jobs = {job.id: job for job in carregar_registro(caminho_registro)}
    job = jobs.get(id_job)
    if job is None:
        raise ValueError(f"Nenhum job encontrado com id '{id_job}'")

    alvo = job.alvo or MODULOS_PERMITIDOS[job.modulo]
    comando = [sys.executable, "-m", alvo, *job.argv]
    ambiente = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUNBUFFERED": "1"}
    # PYTHONIOENCODING: forca UTF-8 na saida do comando -- sem isso, o Windows
    # grava o log em cp1252 e os acentos ficam ilegiveis quando lemos o log depois.
    # PYTHONUNBUFFERED: sem isso, quando a saida vai pra um arquivo o Python a
    # guarda num buffer -- o log ficaria vazio ate o fim do job e perderia o
    # final se o job fosse morto (parar_job) antes de o buffer ser descarregado
    with open(job.log_path, "w", encoding="utf-8") as arquivo_log:
        resultado = subprocess.run(
            comando, stdout=arquivo_log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
            env=ambiente, creationflags=subprocess.CREATE_NO_WINDOW,
            # CREATE_NO_WINDOW: sem isso, o Windows abriria uma janela de
            # terminal nova pra esse comando, ja que o executor nao tem terminal
        )

    novo_estado = "concluido" if resultado.returncode == 0 else "erro"
    atualizar_job(id_job, caminho_registro, estado=novo_estado)


def pid_esta_vivo(pid: int) -> bool:
    """Pergunta pro Windows se ainda existe um processo rodando com esse
    PID. Usa 'tasklist' (comando nativo do Windows) em vez de adicionar
    uma biblioteca nova so pra isso. PID 0 (ou negativo) nunca conta como
    vivo: 0 e o "System Idle Process" do Windows, que o tasklist lista."""
    if pid <= 0:
        return False
    resultado = subprocess.run(
        ["tasklist", "/fi", f"PID eq {pid}", "/nh"],
        capture_output=True, text=True,
    )
    return str(pid) in resultado.stdout


TOLERANCIA_LANCAMENTO_SEGUNDOS = 30.0
# um job recem-lancado fica "rodando" com pid=0 por alguns milissegundos
# (iniciar_job grava o registro ANTES de lancar o executor e so grava o pid
# DEPOIS). Enquanto o job for mais novo que isso, pid=0 significa "lancando
# agora" -- nao "morto".


def _lancamento_em_andamento(job: JobRegistrado) -> bool:
    """True se o job ainda esta na janela de lancamento: o pid ainda nao foi
    gravado (0 ou negativo) E o job foi iniciado ha menos de
    TOLERANCIA_LANCAMENTO_SEGUNDOS. Sem 'iniciado_em' (vazio ou ilegivel) nao
    da pra provar que o job e recente, entao ele conta como antigo -- um pid 0
    antigo e de um lancador que morreu antes de gravar o pid."""
    if job.pid > 0:
        return False
    try:
        iniciado_em = datetime.fromisoformat(job.iniciado_em)
    except ValueError:
        return False
    if iniciado_em.tzinfo is None:
        iniciado_em = iniciado_em.replace(tzinfo=timezone.utc)
    idade = datetime.now(timezone.utc) - iniciado_em
    return idade.total_seconds() < TOLERANCIA_LANCAMENTO_SEGUNDOS


def _marcar_interrompido(id_job: str, pid_verificado: int, caminho_registro: Path) -> None:
    """Marca o job como 'interrompido' -- mas so se, DENTRO da trava do
    registro, ele ainda estiver como foi conferido: 'rodando' E com o mesmo
    pid que foi dado como morto (compare-and-set). O executor pode ter gravado
    'concluido' ou 'erro' um instante antes de o processo morrer, e o lancador
    pode ter gravado o pid real depois da conferencia; nenhum dos dois pode
    ser sobrescrito."""
    with trava_registro(caminho_registro):
        jobs = carregar_registro(caminho_registro)
        for job in jobs:
            if job.id == id_job and job.estado == "rodando" and job.pid == pid_verificado:
                job.estado = "interrompido"
                job.atualizado_em = datetime.now(timezone.utc).isoformat()
                salvar_registro(jobs, caminho_registro)
                return


def reconciliar_estados(caminho_registro: Path = CAMINHO_PADRAO) -> list[JobRegistrado]:
    """Confere, pra cada job que o registro ainda acha que esta 'rodando',
    se o processo continua vivo de verdade. Se nao estiver -- e o proprio
    executor nao tiver atualizado o estado antes de morrer (ex.: foi morto
    por fora, ou crashou sem dar tempo de atualizar) -- marca como
    'interrompido', pra nunca mostrar um job como 'rodando' quando ja
    morreu. Job recem-lancado (pid ainda 0, dentro da tolerancia de
    lancamento) e poupado. Devolve a lista ja atualizada."""
    # ideia central: o snapshot do registro e o pid_esta_vivo (lento, chama um
    # programa externo) ficam FORA da trava -- ela nao pode ser segurada
    # durante o tasklist. So a marcacao, curta, entra na trava, e la dentro
    # _marcar_interrompido confere de novo se o job continua como foi visto.
    for job in carregar_registro(caminho_registro):
        if job.estado != "rodando" or _lancamento_em_andamento(job):
            continue
        if not pid_esta_vivo(job.pid):
            _marcar_interrompido(job.id, job.pid, caminho_registro)
    return carregar_registro(caminho_registro)
