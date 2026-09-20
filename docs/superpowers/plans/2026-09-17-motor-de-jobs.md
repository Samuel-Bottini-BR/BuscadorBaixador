# Motor de Jobs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Dar ao BuscadorBaixador um motor que roda os comandos já existentes (`cli`, `gallica_crawl`, `gallica_enriquecer`) como jobs isolados e destacados da sessão, em segundo plano — iniciar sem terminal manual, ver status/progresso, parar, retomar, e ser avisado (notificação do Windows) quando um job trava esperando ação humana.

**Architecture:** Subprocessos + registro em JSON (`jobs/registro.json`), escrita atômica no mesmo padrão de `core/checkpoint.py`. Cada job é lançado através de um pequeno processo "executor" **destacado da sessão** (`python -m buscador.core.jobs_executor <id> <registro>`, com `DETACHED_PROCESS`) que roda o comando de verdade, espera terminar, e atualiza o registro sozinho — sem nenhum processo supervisor permanente. Destacar é essencial: a coleta da Gallica de 17/09 morreu junto com a sessão do Claude Code que a tinha lançado como processo filho. Ver desenho completo em `docs/superpowers/specs/2026-09-17-motor-de-jobs-design.md`.

**Tech Stack:** Python 3.11/3.12 (venv existente), `subprocess`/`tasklist`/`taskkill` nativos do Windows (sem `psutil`), `win11toast` (nova dependência, notificação nativa).

**Spec:** `docs/superpowers/specs/2026-09-17-motor-de-jobs-design.md`

## Global Constraints

- Nenhuma API paga da Anthropic em lugar nenhum do projeto (fora de escopo deste plano de qualquer forma — esse plano cobre só o motor central, não a categorização por IA).
- Windows apenas — usar `tasklist`/`taskkill` nativos, não adicionar `psutil` nem nada multiplataforma desnecessário.
- Qualquer arquivo de estado persistente (registro de jobs) usa escrita atômica: grava em `.tmp` e troca com `os.replace`, igual `core/checkpoint.py`.
- Comentários em português, estilo pedagógico já usado no projeto (explica o conceito não óbvio, não o óbvio) — todo o pacote já segue essa convenção.
- `requires-python = ">=3.11,<3.13"` (já fixado em `pyproject.toml`) — pode usar `list[str]`, `str | None`, etc.
- O comando `logar` fica **fora** do motor: ele é interativo (espera o Samuel apertar Enter no terminal) e um job roda sem terminal/stdin. O mesmo vale pra `gallica_crawl --reiniciar` (pede confirmação digitada) — não usar via motor.
- O processo executor de um job é separado do que o iniciou: qualquer informação de que o executor precise (ex.: qual módulo Python rodar) tem que estar gravada no registro em disco, nunca só em memória do processo pai.
- Este plano cobre só o **motor central** (iniciar/status/parar/retomar/notificar) reaproveitando os comandos que já existem hoje. O sistema de estágios configuráveis por job e o fluxo de categorização por IA (native → trilha → IA em cascata) ficam para um plano seguinte, construído em cima deste motor — ver nota de escopo abaixo.

## Nota de escopo (por que este plano não cobre o spec inteiro)

O spec cobre duas peças: (1) o motor de jobs em si, e (2) estágios
configuráveis por job + o fluxo de categorização por IA. A peça (2) depende
de refatorar `cli.py` pra separar mapear/verificar/traduzir em passos
independentes — um trabalho de escopo próprio, e só faz sentido depois que
o motor central (peça 1) já existe e está testado com jobs de verdade. Este
plano implementa só a peça (1). Ela sozinha já resolve o pedido original
("rodar mais de uma tarefa ao mesmo tempo, ver progresso, parar/retomar,
ser avisado quando travar") usando os comandos que já existem hoje.

---

### Task 1: Registro de jobs (armazenamento em disco)

> **Emenda (rodada de correção 1 da execução):** a revisão provou que o código deste task, do jeito escrito abaixo, corrompe o registro quando vários processos gravam juntos (o motor faz isso: quem inicia + vários executores). O `jobs_registro.py` do repositório foi endurecido — arquivo temporário único por escritor, `trava_registro` (context manager público, trava por arquivo `.lock`) e retentativa de `PermissionError` do Windows — sem mudar nenhuma assinatura abaixo. Os blocos de código deste task são o ponto de partida; **o arquivo no repositório é a versão vigente**. Detalhes em `.superpowers/sdd/2026-09-17-motor-de-jobs/task-1-fix1.md` (local, fora do git) e no commit da correção.

**Files:**
- Create: `src/buscador/core/jobs_registro.py`
- Test: `tests/test_jobs_registro.py`

**Interfaces:**
- Produces: `JobRegistrado` (dataclass: `id: str`, `modulo: str`, `argv: list[str]`, `pid: int`, `estado: str`, `log_path: str`, `iniciado_em: str = ""`, `atualizado_em: str = ""`, `alvo: str = ""` — o módulo Python de verdade que o executor roda, ex. `"buscador.gallica_crawl"`), `CAMINHO_PADRAO: Path`, `novo_id(modulo: str) -> str`, `carregar_registro(caminho: Path = CAMINHO_PADRAO) -> list[JobRegistrado]`, `salvar_registro(jobs: list[JobRegistrado], caminho: Path = CAMINHO_PADRAO) -> None`, `adicionar_job(job: JobRegistrado, caminho: Path = CAMINHO_PADRAO) -> None`, `atualizar_job(id: str, caminho: Path = CAMINHO_PADRAO, **mudancas) -> JobRegistrado` (levanta `ValueError` se o id não existir).

- [ ] **Step 1: Escrever os testes (todos de uma vez, já que são pequenos e do mesmo arquivo)**

```python
# -*- coding: utf-8 -*-
# tests/test_jobs_registro.py
import pytest

from buscador.core.jobs_registro import (
    JobRegistrado,
    adicionar_job,
    atualizar_job,
    carregar_registro,
    novo_id,
    salvar_registro,
)


def _job_de_teste(id="job-teste"):
    return JobRegistrado(
        id=id, modulo="gallica_crawl", argv=['dc.type all "monographie"'],
        pid=1234, estado="rodando", log_path="jobs/job-teste/log.txt",
        iniciado_em="2026-09-17T00:00:00+00:00", alvo="buscador.gallica_crawl",
    )


def test_carregar_registro_devolve_lista_vazia_quando_arquivo_nao_existe(tmp_path):
    caminho = tmp_path / "registro.json"
    assert carregar_registro(caminho) == []


def test_salvar_e_carregar_registro_ida_e_volta(tmp_path):
    caminho = tmp_path / "registro.json"
    salvar_registro([_job_de_teste()], caminho)

    jobs = carregar_registro(caminho)

    assert len(jobs) == 1
    assert jobs[0].id == "job-teste"
    assert jobs[0].modulo == "gallica_crawl"
    assert jobs[0].alvo == "buscador.gallica_crawl"


def test_salvar_nao_deixa_arquivo_tmp_para_tras(tmp_path):
    caminho = tmp_path / "registro.json"
    salvar_registro([_job_de_teste()], caminho)

    assert not caminho.with_suffix(".json.tmp").exists()


def test_adicionar_job_acrescenta_sem_apagar_os_que_ja_existiam(tmp_path):
    caminho = tmp_path / "registro.json"
    salvar_registro([_job_de_teste("job-1")], caminho)

    adicionar_job(_job_de_teste("job-2"), caminho)

    ids = [job.id for job in carregar_registro(caminho)]
    assert ids == ["job-1", "job-2"]


def test_atualizar_job_muda_so_os_campos_informados(tmp_path):
    caminho = tmp_path / "registro.json"
    salvar_registro([_job_de_teste("job-1")], caminho)

    atualizado = atualizar_job("job-1", caminho, estado="concluido")

    assert atualizado.estado == "concluido"
    assert atualizado.modulo == "gallica_crawl"
    assert carregar_registro(caminho)[0].estado == "concluido"


def test_atualizar_job_com_id_inexistente_da_erro(tmp_path):
    caminho = tmp_path / "registro.json"
    salvar_registro([], caminho)

    with pytest.raises(ValueError):
        atualizar_job("nao-existe", caminho)


def test_novo_id_inclui_o_nome_do_modulo_e_e_diferente_a_cada_chamada():
    id1 = novo_id("gallica_crawl")
    id2 = novo_id("gallica_crawl")

    assert id1.startswith("gallica_crawl-")
    assert id1 != id2
```

- [ ] **Step 2: Rodar os testes e confirmar que falham (o módulo ainda não existe)**

Run: `.venv\Scripts\python.exe -m pytest tests/test_jobs_registro.py -v`
Expected: `ModuleNotFoundError: No module named 'buscador.core.jobs_registro'`

- [ ] **Step 3: Implementar `jobs_registro.py`**

```python
# -*- coding: utf-8 -*-
"""
O "registro de jobs" e a lista de todas as tarefas que o motor ja
iniciou -- rodando ou nao. Fica guardado num unico arquivo JSON
(jobs/registro.json), com o mesmo cuidado de escrita atomica que
core/checkpoint.py ja usa (grava num .tmp e so depois troca pelo arquivo
de verdade), pra nunca ficar corrompido se o programa for interrompido no
meio de uma gravacao.
"""
import json
import os
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

CAMINHO_PADRAO = Path(__file__).resolve().parent.parent.parent.parent / "jobs" / "registro.json"
# sobe de src/buscador/core/ ate a raiz do projeto, depois entra em jobs/


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
    (primeira vez que o motor roda), devolve lista vazia em vez de erro."""
    if not caminho.exists():
        return []
    dados = json.loads(caminho.read_text(encoding="utf-8"))
    return [JobRegistrado(**item) for item in dados["jobs"]]


def salvar_registro(jobs: list[JobRegistrado], caminho: Path = CAMINHO_PADRAO) -> None:
    """Grava a lista inteira de jobs, num arquivo temporario primeiro e so
    depois troca pelo definitivo -- mesma tecnica de core/checkpoint.py,
    pra nunca deixar o registro pela metade se o programa for interrompido
    bem no meio da escrita."""
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho_tmp = caminho.with_suffix(caminho.suffix + ".tmp")
    conteudo = {"jobs": [asdict(job) for job in jobs]}
    caminho_tmp.write_text(json.dumps(conteudo, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(caminho_tmp, caminho)


def adicionar_job(job: JobRegistrado, caminho: Path = CAMINHO_PADRAO) -> None:
    """Le o registro atual, acrescenta um job novo, e salva de volta."""
    jobs = carregar_registro(caminho)
    jobs.append(job)
    salvar_registro(jobs, caminho)


def atualizar_job(id: str, caminho: Path = CAMINHO_PADRAO, **mudancas) -> JobRegistrado:
    """Le o registro, atualiza os campos informados (em **mudancas) do job
    com esse id, salva de volta, e devolve o job ja atualizado. Levanta
    ValueError se nenhum job tiver esse id."""
    jobs = carregar_registro(caminho)
    for job in jobs:
        if job.id == id:
            for chave, valor in mudancas.items():
                setattr(job, chave, valor)
            job.atualizado_em = datetime.now(timezone.utc).isoformat()
            salvar_registro(jobs, caminho)
            return job
    raise ValueError(f"Nenhum job encontrado com id '{id}'")
```

- [ ] **Step 4: Rodar os testes e confirmar que passam**

Run: `.venv\Scripts\python.exe -m pytest tests/test_jobs_registro.py -v`
Expected: `7 passed`

- [ ] **Step 5: Commit**

```bash
git add src/buscador/core/jobs_registro.py tests/test_jobs_registro.py
git commit -m "feat: registro de jobs em disco (jobs_registro.py)"
```

---

### Task 2: Notificação nativa do Windows

**Files:**
- Create: `src/buscador/core/jobs_notificacoes.py`
- Create: `tests/conftest.py` (silencia o aviso real do Windows em TODOS os testes — o Task 9 faz `cli.main`/`gallica_crawl.main` chamarem `avisar_windows`, e sem isso cada `pytest` abriria um balão de verdade no Windows do Samuel)
- Test: `tests/test_jobs_notificacoes.py`
- Modify: `pyproject.toml`

**Interfaces:**
- Produces: `avisar_windows(titulo: str, mensagem: str) -> None`

- [ ] **Step 1: Adicionar a dependência nova**

Em `pyproject.toml`, no array `dependencies` (depois de `"seleniumbase>=4.32",`), adicionar:

```
    "win11toast>=0.35",
```

Run: `.venv\Scripts\python.exe -m pip install -e ".[dev]"`
Expected: instala `win11toast` sem erro.

- [ ] **Step 2: Escrever o teste**

```python
# -*- coding: utf-8 -*-
# tests/test_jobs_notificacoes.py
import time

from buscador.core import jobs_notificacoes


def test_avisar_windows_chama_notify_com_titulo_e_mensagem(monkeypatch):
    chamadas = []
    monkeypatch.setattr(
        jobs_notificacoes, "notify",
        lambda titulo, mensagem: chamadas.append((titulo, mensagem)),
    )

    jobs_notificacoes.avisar_windows("Job travado", "Precisa fazer login no Internet Archive")

    assert chamadas == [("Job travado", "Precisa fazer login no Internet Archive")]


def test_avisar_windows_nao_fica_esperando_se_o_aviso_bloquear(monkeypatch):
    # o notify da biblioteca pode ficar esperando o usuario fechar o balao;
    # um job nao pode ficar pendurado por causa disso
    monkeypatch.setattr(jobs_notificacoes, "notify", lambda titulo, mensagem: time.sleep(5))
    monkeypatch.setattr(jobs_notificacoes, "ESPERA_MAXIMA_SEGUNDOS", 0.2)

    inicio = time.time()
    jobs_notificacoes.avisar_windows("Job travado", "qualquer mensagem")

    assert time.time() - inicio < 2


def test_avisar_windows_nao_propaga_erro_do_windows(monkeypatch):
    def notify_que_falha(titulo, mensagem):
        raise RuntimeError("sem suporte a notificacao")
    monkeypatch.setattr(jobs_notificacoes, "notify", notify_que_falha)

    jobs_notificacoes.avisar_windows("Job travado", "qualquer mensagem")  # nao pode levantar
```

- [ ] **Step 3: Rodar o teste e confirmar que falha**

Run: `.venv\Scripts\python.exe -m pytest tests/test_jobs_notificacoes.py -v`
Expected: `ModuleNotFoundError: No module named 'buscador.core.jobs_notificacoes'`

- [ ] **Step 4: Implementar**

```python
# -*- coding: utf-8 -*-
"""
Dispara uma notificacao nativa do Windows (o balao que aparece no canto da
tela) quando um job precisa da atencao do Samuel. Usa win11toast, que nao
precisa de nenhuma configuracao especial nem permissao de administrador.
"""
import threading

from win11toast import notify

ESPERA_MAXIMA_SEGUNDOS = 3.0


def _mostrar(titulo: str, mensagem: str) -> None:
    try:
        notify(titulo, mensagem)
    except Exception:
        # o aviso e so uma cortesia: se o Windows nao conseguir mostrar
        # (sem suporte, erro interno), o job nao pode quebrar por causa disso
        pass


def avisar_windows(titulo: str, mensagem: str) -> None:
    """Mostra uma notificacao do Windows com o titulo e a mensagem dados.
    Chamado sempre que um job entra num estado que precisa da atencao do
    Samuel (hoje: login/CAPTCHA/chave de API -- ver core/acao_humana.py).
    Roda numa thread com tempo maximo de espera: dependendo da versao, o
    notify() da biblioteca pode ficar esperando o usuario fechar o balao, e
    um job nao pode ficar pendurado indefinidamente por causa disso."""
    thread = threading.Thread(target=_mostrar, args=(titulo, mensagem), daemon=True)
    thread.start()
    thread.join(timeout=ESPERA_MAXIMA_SEGUNDOS)
```

Também criar `tests/conftest.py` (não existe hoje):

```python
# -*- coding: utf-8 -*-
# tests/conftest.py
import pytest


@pytest.fixture(autouse=True)
def _sem_aviso_real_do_windows(monkeypatch):
    """Nenhum teste deve abrir um aviso de verdade no Windows do Samuel --
    os testes que querem checar o aviso trocam o notify por conta propria
    (como test_jobs_notificacoes.py faz)."""
    monkeypatch.setattr("buscador.core.jobs_notificacoes.notify", lambda titulo, mensagem: None)
```

- [ ] **Step 5: Rodar o teste e confirmar que passa**

Run: `.venv\Scripts\python.exe -m pytest tests/test_jobs_notificacoes.py -v`
Expected: `3 passed`

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml src/buscador/core/jobs_notificacoes.py tests/conftest.py tests/test_jobs_notificacoes.py
git commit -m "feat: notificacao nativa do Windows pro motor de jobs"
```

---

### Task 3: Motor — iniciar e executar um job

> **Emenda (rodada de correção 1 da execução):** a revisão achou dois defeitos no código deste task do jeito escrito abaixo, e o `jobs_motor.py` do repositório foi corrigido: (1) se `_lancar_destacado` falhar, `iniciar_job` marca o job como `"erro"` e re-propaga a exceção (antes sobrava um job `rodando`/`pid=0` fantasma); (2) o ambiente do comando ganhou `PYTHONUNBUFFERED=1` (antes o log ficava preso no buffer até o fim do job). O arquivo de testes ganhou 2 testes (7 no total neste ponto). **O arquivo no repositório é a versão vigente.**

**Files:**
- Create: `src/buscador/core/jobs_motor.py`
- Create: `src/buscador/core/jobs_executor.py`
- Create: `tests/fixtures/job_fake.py`
- Test: `tests/test_jobs_motor.py`

**Interfaces:**
- Consumes: `JobRegistrado` (inclui o campo `alvo`), `CAMINHO_PADRAO`, `adicionar_job`, `atualizar_job`, `carregar_registro`, `novo_id` (de `buscador.core.jobs_registro`, Task 1)
- Produces: `MODULOS_PERMITIDOS: dict[str, str]`, `PASTA_JOBS: Path`, `SAIDAS: Path`, `iniciar_job(modulo: str, argv: list[str], caminho_registro: Path = CAMINHO_PADRAO) -> JobRegistrado`, `executar_job(id_job: str, caminho_registro: Path = CAMINHO_PADRAO) -> None`, `_lancar_destacado(comando: list[str]) -> subprocess.Popen`; e o ponto de entrada do processo executor: `python -m buscador.core.jobs_executor <id_job> <caminho_registro>`.

**Por que o campo `alvo` e o módulo `jobs_executor` existem (decisões de revisão do plano):** o executor roda num processo separado do que chamou `iniciar_job`, então ele não enxerga nada que um teste (ou qualquer código) tenha alterado em memória no processo pai — por isso `iniciar_job` grava no registro o módulo Python que será de fato executado (`alvo`), e o executor só lê isso. E o executor é um módulo próprio (`jobs_executor`), não um subcomando do `jobs_cli` (Task 8), pra `iniciar_job` já funcionar de ponta a ponta nesta task, sem depender de uma task futura.

- [ ] **Step 1: Criar o script fixture usado só pelos testes**

```python
# -*- coding: utf-8 -*-
# tests/fixtures/job_fake.py
"""
Script minusculo usado so pelos testes do motor de jobs
(test_jobs_motor.py, test_jobs_cli.py) -- roda rapido, imprime uma linha,
e sai com o codigo de saida pedido no primeiro argumento (0 por padrao),
sem precisar rodar nenhum modulo de verdade do buscador (que levaria
minutos/horas de verdade).
"""
import sys


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    print("job_fake rodou")
    return int(argv[0]) if argv else 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Escrever os testes**

```python
# -*- coding: utf-8 -*-
# tests/test_jobs_motor.py
import subprocess
import time

from buscador.core import jobs_motor
from buscador.core.jobs_registro import JobRegistrado, carregar_registro, salvar_registro


def test_executar_job_roda_o_comando_e_marca_concluido_quando_sai_com_sucesso(tmp_path, monkeypatch):
    caminho_registro = tmp_path / "registro.json"
    monkeypatch.setitem(jobs_motor.MODULOS_PERMITIDOS, "echo_teste", "tests.fixtures.job_fake")
    job = JobRegistrado(
        id="job-1", modulo="echo_teste", argv=[], pid=0, estado="rodando",
        log_path=str(tmp_path / "log.txt"),
    )
    salvar_registro([job], caminho_registro)

    jobs_motor.executar_job("job-1", caminho_registro)

    atualizado = carregar_registro(caminho_registro)[0]
    assert atualizado.estado == "concluido"


def test_executar_job_marca_erro_quando_comando_sai_com_falha(tmp_path, monkeypatch):
    caminho_registro = tmp_path / "registro.json"
    monkeypatch.setitem(jobs_motor.MODULOS_PERMITIDOS, "echo_teste", "tests.fixtures.job_fake")
    job = JobRegistrado(
        id="job-1", modulo="echo_teste", argv=["1"], pid=0, estado="rodando",
        log_path=str(tmp_path / "log.txt"),
    )
    salvar_registro([job], caminho_registro)

    jobs_motor.executar_job("job-1", caminho_registro)

    assert carregar_registro(caminho_registro)[0].estado == "erro"


def test_executar_job_grava_a_saida_do_comando_no_log(tmp_path, monkeypatch):
    caminho_registro = tmp_path / "registro.json"
    caminho_log = tmp_path / "log.txt"
    monkeypatch.setitem(jobs_motor.MODULOS_PERMITIDOS, "echo_teste", "tests.fixtures.job_fake")
    job = JobRegistrado(
        id="job-1", modulo="echo_teste", argv=[], pid=0, estado="rodando",
        log_path=str(caminho_log),
    )
    salvar_registro([job], caminho_registro)

    jobs_motor.executar_job("job-1", caminho_registro)

    assert "job_fake rodou" in caminho_log.read_text(encoding="utf-8")


def test_iniciar_job_de_ponta_a_ponta_o_executor_separado_roda_e_conclui(tmp_path, monkeypatch):
    caminho_registro = tmp_path / "registro.json"
    monkeypatch.setitem(jobs_motor.MODULOS_PERMITIDOS, "echo_teste", "tests.fixtures.job_fake")
    monkeypatch.setattr(jobs_motor, "PASTA_JOBS", tmp_path / "jobs")

    job = jobs_motor.iniciar_job("echo_teste", [], caminho_registro)

    assert job.pid != 0
    assert job.alvo == "tests.fixtures.job_fake"
    prazo = time.time() + 20
    estado = "rodando"
    while time.time() < prazo and estado == "rodando":
        time.sleep(0.3)
        estado = [j for j in carregar_registro(caminho_registro) if j.id == job.id][0].estado
    assert estado == "concluido"


def test_lancar_destacado_tenta_de_novo_sem_breakaway_se_o_windows_negar(monkeypatch):
    chamadas = []

    class ProcessoFalso:
        pid = 4242

    def popen_falso(comando, creationflags=0, **kwargs):
        chamadas.append(creationflags)
        if creationflags & subprocess.CREATE_BREAKAWAY_FROM_JOB:
            raise PermissionError("acesso negado")
        return ProcessoFalso()

    monkeypatch.setattr(subprocess, "Popen", popen_falso)

    processo = jobs_motor._lancar_destacado(["qualquer"])

    assert processo.pid == 4242
    assert len(chamadas) == 2
    assert chamadas[0] & subprocess.CREATE_BREAKAWAY_FROM_JOB
    assert not chamadas[1] & subprocess.CREATE_BREAKAWAY_FROM_JOB
    assert chamadas[1] & subprocess.DETACHED_PROCESS
```

- [ ] **Step 3: Rodar os testes e confirmar que falham**

Run: `.venv\Scripts\python.exe -m pytest tests/test_jobs_motor.py -v`
Expected: `ModuleNotFoundError: No module named 'buscador.core.jobs_motor'`

- [ ] **Step 4: Implementar `jobs_motor.py` (parte 1 — iniciar/executar) e `jobs_executor.py`**

```python
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
    # grava o job no registro ANTES de lancar o processo executor -- assim,
    # mesmo que o lancamento falhe, o registro nao fica com um job
    # "fantasma" que o executor nunca chegou a ver

    processo = _lancar_destacado(
        [sys.executable, "-m", "buscador.core.jobs_executor", id_job, str(caminho_registro)]
    )
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
    ambiente = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    # forca UTF-8 na saida do comando -- sem isso, o Windows grava o log em
    # cp1252 e os acentos ficam ilegiveis quando lemos o log depois
    with open(job.log_path, "w", encoding="utf-8") as arquivo_log:
        resultado = subprocess.run(
            comando, stdout=arquivo_log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
            env=ambiente, creationflags=subprocess.CREATE_NO_WINDOW,
            # CREATE_NO_WINDOW: sem isso, o Windows abriria uma janela de
            # terminal nova pra esse comando, ja que o executor nao tem terminal
        )

    novo_estado = "concluido" if resultado.returncode == 0 else "erro"
    atualizar_job(id_job, caminho_registro, estado=novo_estado)
```

```python
# -*- coding: utf-8 -*-
# src/buscador/core/jobs_executor.py
"""
Ponto de entrada do processo "executor" de um job -- lancado por
core/jobs_motor.py::iniciar_job, nunca digitado na mao. Roda o comando de
verdade do job e atualiza o registro quando ele termina:
"python -m buscador.core.jobs_executor <id_do_job> <caminho_do_registro>".
"""
import sys
from pathlib import Path

from buscador.core.jobs_motor import executar_job


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    executar_job(argv[0], Path(argv[1]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 5: Rodar os testes e confirmar que passam**

Run: `.venv\Scripts\python.exe -m pytest tests/test_jobs_motor.py -v`
Expected: `5 passed`

- [ ] **Step 6: Commit**

```bash
git add src/buscador/core/jobs_motor.py src/buscador/core/jobs_executor.py tests/fixtures/job_fake.py tests/test_jobs_motor.py
git commit -m "feat: motor de jobs -- iniciar (destacado) e executar"
```

---

### Task 4: Motor — checar PID vivo e reconciliar estados

> **Emenda (rodada de correção 1 da execução):** a revisão provou que a guarda `pid <= 0 → False` deste task fazia `reconciliar_estados` marcar `interrompido` um job recém-lançado (`rodando`/`pid=0` por alguns ms) pelo resto da execução. O `jobs_motor.py` do repositório ganhou uma tolerância de lançamento (`TOLERANCIA_LANCAMENTO_SEGUNDOS`, `_lancamento_em_andamento`) e um compare-and-set do pid em `_marcar_interrompido(id_job, pid_verificado, caminho_registro)`; o arquivo de testes ganhou 3 testes. **O arquivo no repositório é a versão vigente.**

**Files:**
- Modify: `src/buscador/core/jobs_motor.py`
- Test: `tests/test_jobs_motor.py`

**Interfaces:**
- Produces: `pid_esta_vivo(pid: int) -> bool`, `reconciliar_estados(caminho_registro: Path = CAMINHO_PADRAO) -> list[JobRegistrado]`

- [ ] **Step 1: Escrever os testes**

```python
# acrescentar em tests/test_jobs_motor.py
import os


def test_pid_esta_vivo_verdadeiro_pro_proprio_processo_do_teste():
    assert jobs_motor.pid_esta_vivo(os.getpid()) is True


def test_pid_esta_vivo_falso_pra_pid_que_nao_existe():
    assert jobs_motor.pid_esta_vivo(999999) is False


def test_pid_esta_vivo_falso_pra_pid_zero():
    # pid 0 e o "System Idle Process" do Windows (o tasklist o lista como vivo);
    # um job cujo lancamento falhou fica com pid=0 e nao pode parecer vivo
    assert jobs_motor.pid_esta_vivo(0) is False


def test_reconciliar_marca_interrompido_quando_processo_no_registro_ja_morreu(tmp_path):
    caminho_registro = tmp_path / "registro.json"
    job = JobRegistrado(
        id="job-1", modulo="cli", argv=[], pid=999999, estado="rodando",
        log_path=str(tmp_path / "log.txt"),
    )
    salvar_registro([job], caminho_registro)

    jobs = jobs_motor.reconciliar_estados(caminho_registro)

    assert jobs[0].estado == "interrompido"
    assert carregar_registro(caminho_registro)[0].estado == "interrompido"


def test_reconciliar_nao_mexe_em_job_que_continua_vivo(tmp_path):
    caminho_registro = tmp_path / "registro.json"
    job = JobRegistrado(
        id="job-1", modulo="cli", argv=[], pid=os.getpid(), estado="rodando",
        log_path=str(tmp_path / "log.txt"),
    )
    salvar_registro([job], caminho_registro)

    jobs = jobs_motor.reconciliar_estados(caminho_registro)

    assert jobs[0].estado == "rodando"


def test_reconciliar_nao_sobrescreve_estado_final_gravado_durante_a_checagem(tmp_path, monkeypatch):
    # o executor pode gravar "concluido" um instante antes de o processo morrer;
    # a reconciliacao nao pode sobrescrever isso com "interrompido"
    caminho_registro = tmp_path / "registro.json"
    job = JobRegistrado(
        id="job-1", modulo="cli", argv=[], pid=999999, estado="rodando",
        log_path=str(tmp_path / "log.txt"),
    )
    salvar_registro([job], caminho_registro)

    def pid_morto_com_executor_terminando_no_meio(pid):
        atualizar_job("job-1", caminho_registro, estado="concluido")
        return False
    monkeypatch.setattr(jobs_motor, "pid_esta_vivo", pid_morto_com_executor_terminando_no_meio)

    jobs = jobs_motor.reconciliar_estados(caminho_registro)

    assert jobs[0].estado == "concluido"
```

Adicionar `import os` e `from buscador.core.jobs_registro import atualizar_job` no topo do arquivo de teste (junto dos outros imports).

- [ ] **Step 2: Rodar e confirmar que falham**

Run: `.venv\Scripts\python.exe -m pytest tests/test_jobs_motor.py -v -k "pid_esta_vivo or reconciliar"`
Expected: `AttributeError: module 'buscador.core.jobs_motor' has no attribute 'pid_esta_vivo'`

- [ ] **Step 3: Implementar (acrescentar ao final de `jobs_motor.py`)**

```python
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


def _marcar_interrompido(id_job: str, caminho_registro: Path) -> None:
    """Marca o job como 'interrompido' -- mas so se, DENTRO da trava do
    registro, ele ainda constar como 'rodando'. O executor pode ter gravado
    'concluido' ou 'erro' um instante antes de o processo morrer, e isso nao
    pode ser sobrescrito."""
    with trava_registro(caminho_registro):
        jobs = carregar_registro(caminho_registro)
        for job in jobs:
            if job.id == id_job and job.estado == "rodando":
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
    morreu. Devolve a lista ja atualizada."""
    for job in carregar_registro(caminho_registro):
        if job.estado == "rodando" and not pid_esta_vivo(job.pid):
            _marcar_interrompido(job.id, caminho_registro)
    return carregar_registro(caminho_registro)
```

No topo do arquivo, trocar o import de `buscador.core.jobs_registro` (escrito no Task 3) pra incluir
`salvar_registro` e `trava_registro` (a trava foi acrescentada ao `jobs_registro.py` na rodada de correção do Task 1 — quem faz ler→modificar→salvar no registro tem que segurá-la):

```python
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
```

- [ ] **Step 4: Rodar e confirmar que passam**

Run: `.venv\Scripts\python.exe -m pytest tests/test_jobs_motor.py -v`
Expected: todos os testes do arquivo passando (agora 13 no total).

- [ ] **Step 5: Commit**

```bash
git add src/buscador/core/jobs_motor.py tests/test_jobs_motor.py
git commit -m "feat: motor de jobs -- checar PID vivo e reconciliar estados"
```

---

### Task 5: Motor — parar um job

> **Emenda (2 rodadas de correção da execução):** a revisão provou que o `parar_job` deste rascunho podia (1) sobrescrever `concluido`/`erro` com `parado` (snapshot → consulta lenta → gravação incondicional), (2) gravar `parado` sem ter parado nada (`taskkill` ignorado; consulta falha tratada como "não é o executor"), e que `_linha_de_comando` quebrava com acentos, sem timeout, e lia erro do WMI (código 0 + stderr) como "processo não existe". O `jobs_motor.py` do repositório é a versão vigente: `_linha_de_comando` devolve `Optional[str]` (None = "não sei"), `_e_o_executor_do_job` devolve `Optional[bool]`, `_marcar_parado` relê sob a trava, e `parar_job` levanta `RuntimeError` (nada morto, estado inalterado) quando o job ainda está sendo lançado, quando não dá pra confirmar o processo, ou quando o `taskkill` falha com o processo vivo. O fixture `job_lento_fake` grava o PID do comando real num arquivo (argv[0]) e o teste E2E verifica que a ÁRVORE morre (`/T`). **O código no repositório é a versão vigente; os blocos abaixo são o rascunho original.**

> **Por que este task é mais cuidadoso que o rascunho original (decisão de revisão do plano):** parar um job significa matar um processo pelo PID guardado no registro. Se o executor já morreu e o Windows reaproveitou aquele PID para OUTRO programa (do Samuel!), um `taskkill /F` cego mataria o programa errado. Por isso `parar_job` só mata se a linha de comando do processo for mesmo o executor DAQUELE job (contém `jobs_executor` e o id do job), e só age em jobs que o registro diz que estão `rodando`.

**Files:**
- Modify: `src/buscador/core/jobs_motor.py`
- Create: `tests/fixtures/job_lento_fake.py`
- Test: `tests/test_jobs_motor.py`

**Interfaces:**
- Consumes: `JobRegistrado`, `carregar_registro`, `atualizar_job`, `CAMINHO_PADRAO`, `pid_esta_vivo` (Tasks 1, 3, 4)
- Produces: `_linha_de_comando(pid: int) -> str`, `_e_o_executor_do_job(job: JobRegistrado) -> bool`, `parar_job(id_job: str, caminho_registro: Path = CAMINHO_PADRAO) -> JobRegistrado` (levanta `ValueError` se o id não existir; devolve o job sem mudar nada se ele não estava `rodando`; senão devolve o job já `parado`)

- [ ] **Step 1: Criar o fixture "lento" (fica rodando tempo suficiente pra dar pra testar parar de verdade)**

```python
# -*- coding: utf-8 -*-
# tests/fixtures/job_lento_fake.py
"""Script minusculo usado so pelos testes do motor de jobs -- fica rodando
por bastante tempo (bem mais que qualquer teste precisa esperar), pra dar
tempo de testar 'parar' um job que ainda esta rodando de verdade."""
import time


def main():
    time.sleep(120)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Escrever os testes**

Acrescentar `import sys` no topo de `tests/test_jobs_motor.py` (junto dos outros imports) e estes testes ao final:

```python
def test_parar_job_marca_estado_parado_e_mata_o_processo(tmp_path, monkeypatch):
    caminho_registro = tmp_path / "registro.json"
    monkeypatch.setitem(jobs_motor.MODULOS_PERMITIDOS, "espera_teste", "tests.fixtures.job_lento_fake")
    monkeypatch.setattr(jobs_motor, "PASTA_JOBS", tmp_path / "jobs")

    job = jobs_motor.iniciar_job("espera_teste", [], caminho_registro)
    time.sleep(2)  # da tempo do executor (e do comando lento) subirem de verdade
    assert jobs_motor.pid_esta_vivo(job.pid) is True

    parado = jobs_motor.parar_job(job.id, caminho_registro)

    assert parado.estado == "parado"
    assert jobs_motor.pid_esta_vivo(job.pid) is False


def test_parar_job_nao_mata_processo_que_nao_e_o_executor_do_job(tmp_path):
    # simula o Windows ter reaproveitado o PID do executor morto para outro programa
    caminho_registro = tmp_path / "registro.json"
    intruso = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    try:
        job = JobRegistrado(
            id="job-1", modulo="cli", argv=[], pid=intruso.pid, estado="rodando",
            log_path=str(tmp_path / "log.txt"),
        )
        salvar_registro([job], caminho_registro)

        parado = jobs_motor.parar_job("job-1", caminho_registro)

        assert parado.estado == "parado"
        assert intruso.poll() is None  # continua vivo: nao era o executor deste job
    finally:
        intruso.kill()
        intruso.wait()


def test_parar_job_que_ja_terminou_nao_muda_nada(tmp_path):
    caminho_registro = tmp_path / "registro.json"
    job = JobRegistrado(
        id="job-1", modulo="cli", argv=[], pid=999999, estado="concluido",
        log_path=str(tmp_path / "log.txt"),
    )
    salvar_registro([job], caminho_registro)

    resultado = jobs_motor.parar_job("job-1", caminho_registro)

    assert resultado.estado == "concluido"
    assert carregar_registro(caminho_registro)[0].estado == "concluido"


def test_parar_job_com_id_inexistente_da_erro(tmp_path):
    caminho_registro = tmp_path / "registro.json"
    salvar_registro([], caminho_registro)

    with pytest.raises(ValueError):
        jobs_motor.parar_job("nao-existe", caminho_registro)
```

- [ ] **Step 3: Rodar e confirmar que falham**

Run: `.venv\Scripts\python.exe -m pytest tests/test_jobs_motor.py -v -k parar_job`
Expected: `AttributeError: module 'buscador.core.jobs_motor' has no attribute 'parar_job'`

- [ ] **Step 4: Implementar (acrescentar ao final de `jobs_motor.py`)**

```python
def _linha_de_comando(pid: int) -> str:
    """Devolve a linha de comando do processo com esse PID ('' se ele nao
    existir ou se a consulta falhar). Usa o PowerShell (que ja vem no Windows
    10/11) em vez de uma biblioteca nova. O PID e convertido pra inteiro
    antes de entrar no comando, entao nada digitado pode virar codigo."""
    resultado = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command",
         f"(Get-CimInstance Win32_Process -Filter 'ProcessId={int(pid)}').CommandLine"],
        capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW,
    )
    return resultado.stdout.strip()


def _e_o_executor_do_job(job: JobRegistrado) -> bool:
    """True so se o processo com o PID do job e mesmo o executor DESTE job
    (a linha de comando dele contem o modulo executor e o id do job). Protege
    contra o Windows ter reaproveitado o PID de um executor morto para OUTRO
    programa: matar esse outro programa seria um desastre. Se a consulta
    falhar, devolve False -- na duvida, nao mata."""
    if job.pid <= 0:
        return False
    linha = _linha_de_comando(job.pid)
    return "jobs_executor" in linha and job.id in linha


def parar_job(id_job: str, caminho_registro: Path = CAMINHO_PADRAO) -> JobRegistrado:
    """Para um job que o registro diz que esta 'rodando': mata o executor (e,
    com ele, o comando real que roda por baixo, porque e processo-filho) --
    mas SO se o processo do PID guardado for mesmo o executor deste job -- e
    marca o job como 'parado' de proposito (diferente de 'interrompido', que
    e quando morreu sozinho). Um job que ja terminou e devolvido sem mudar
    nada. O progresso ja salvo em disco (checkpoint) nao e afetado -- rodar
    'retomar' depois continua de onde parou."""
    jobs = {job.id: job for job in carregar_registro(caminho_registro)}
    job = jobs.get(id_job)
    if job is None:
        raise ValueError(f"Nenhum job encontrado com id '{id_job}'")
    if job.estado != "rodando":
        return job

    if _e_o_executor_do_job(job):
        subprocess.run(
            ["taskkill", "/PID", str(job.pid), "/T", "/F"],
            capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW,
        )
        # "/T" mata a arvore inteira (o executor e todo processo-filho dele,
        # nao so o executor sozinho) -- "/F" forca o encerramento
    return atualizar_job(id_job, caminho_registro, estado="parado")
```

- [ ] **Step 5: Rodar e confirmar que passam**

Run: `.venv\Scripts\python.exe -m pytest tests/test_jobs_motor.py -v`
Expected: todos passando (agora 28 no total, contando os 8 testes das rodadas de correção da execução).

- [ ] **Step 6: Commit**

```bash
git add src/buscador/core/jobs_motor.py tests/fixtures/job_lento_fake.py tests/test_jobs_motor.py
git commit -m "feat: motor de jobs -- parar um job em andamento (so mata o executor do proprio job)"
```

---

### Task 6: Motor — progresso a partir dos checkpoints conhecidos

**Files:**
- Modify: `src/buscador/core/jobs_motor.py`
- Test: `tests/test_jobs_motor.py`

**Interfaces:**
- Consumes: `Checkpoint`, `slug_consulta` (de `buscador.core.checkpoint`); `CheckpointEnriquecimento` (de `buscador.core.enriquecimento_lote`)
- Produces: `descrever_progresso(job: JobRegistrado) -> str`

- [ ] **Step 1: Escrever os testes**

```python
# acrescentar em tests/test_jobs_motor.py
import json as json_mod

from buscador.core.checkpoint import slug_consulta


def test_descrever_progresso_gallica_crawl_le_o_checkpoint(tmp_path, monkeypatch):
    monkeypatch.setattr(jobs_motor, "SAIDAS", tmp_path / "saidas")
    consulta = 'dc.type all "monographie"'
    pasta_checkpoint = tmp_path / "saidas" / "gallica_crawl" / slug_consulta(consulta)
    pasta_checkpoint.mkdir(parents=True)
    (pasta_checkpoint / "checkpoint.json").write_text(json_mod.dumps({
        "consulta": consulta, "tamanho_pagina": 50, "proximo_start_record": 101,
        "total_registros_api": 1000, "itens_gravados": 100, "concluido": False,
        "atualizado_em": "2026-09-17T00:00:00+00:00",
    }), encoding="utf-8")
    job = JobRegistrado(id="j1", modulo="gallica_crawl", argv=[consulta], pid=1,
                         estado="rodando", log_path=str(tmp_path / "log.txt"))

    progresso = jobs_motor.descrever_progresso(job)

    assert "100/1000" in progresso
    assert "10.0%" in progresso


def test_descrever_progresso_gallica_enriquecer_le_o_checkpoint(tmp_path, monkeypatch):
    monkeypatch.setattr(jobs_motor, "SAIDAS", tmp_path / "saidas")
    pasta_checkpoint = tmp_path / "saidas" / "gallica_crawl" / "meu-job"
    pasta_checkpoint.mkdir(parents=True)
    (pasta_checkpoint / "checkpoint_enriquecimento.json").write_text(json_mod.dumps({
        "total_itens": 100, "lote_tamanho": 20, "proximo_lote": 2,
        "atualizado_em": "2026-09-17T00:00:00+00:00",
    }), encoding="utf-8")
    job = JobRegistrado(id="j1", modulo="gallica_enriquecer", argv=["meu-job"], pid=1,
                         estado="rodando", log_path=str(tmp_path / "log.txt"))

    assert jobs_motor.descrever_progresso(job) == "lote 2/5"


def test_descrever_progresso_usa_log_quando_nao_ha_checkpoint_conhecido(tmp_path, monkeypatch):
    monkeypatch.setattr(jobs_motor, "SAIDAS", tmp_path / "saidas")
    caminho_log = tmp_path / "log.txt"
    caminho_log.write_text("linha 1\nlinha 2 - progresso aqui\n", encoding="utf-8")
    job = JobRegistrado(id="j1", modulo="cli", argv=[], pid=1, estado="rodando",
                         log_path=str(caminho_log))

    assert jobs_motor.descrever_progresso(job) == "log: linha 2 - progresso aqui"


def test_descrever_progresso_sem_checkpoint_nem_log_avisa_isso(tmp_path, monkeypatch):
    monkeypatch.setattr(jobs_motor, "SAIDAS", tmp_path / "saidas")
    job = JobRegistrado(id="j1", modulo="cli", argv=[], pid=1, estado="rodando",
                         log_path=str(tmp_path / "nao-existe.txt"))

    assert jobs_motor.descrever_progresso(job) == "sem informacao de progresso ainda"
```

- [ ] **Step 2: Rodar e confirmar que falham**

Run: `.venv\Scripts\python.exe -m pytest tests/test_jobs_motor.py -v -k descrever_progresso`
Expected: `AttributeError: module 'buscador.core.jobs_motor' has no attribute 'descrever_progresso'`

- [ ] **Step 3: Implementar (acrescentar ao final de `jobs_motor.py`)**

```python
def _progresso_gallica_crawl(job: JobRegistrado) -> Optional[str]:
    """Le o checkpoint da Etapa 1 (coleta SRU da Gallica) pra esse job, se
    existir. A consulta e sempre o primeiro item de argv (ver
    gallica_crawl.py)."""
    if not job.argv:
        return None
    caminho = SAIDAS / "gallica_crawl" / slug_consulta(job.argv[0]) / "checkpoint.json"
    if not caminho.exists():
        return None
    checkpoint = Checkpoint(**json.loads(caminho.read_text(encoding="utf-8")))
    if checkpoint.total_registros_api:
        percentual = 100 * checkpoint.itens_gravados / checkpoint.total_registros_api
        return f"{checkpoint.itens_gravados}/{checkpoint.total_registros_api} registros ({percentual:.1f}%)"
    return f"{checkpoint.itens_gravados} registros coletados"


def _progresso_gallica_enriquecer(job: JobRegistrado) -> Optional[str]:
    """Le o checkpoint da Etapa 2 (verificar link + traduzir) pra esse job,
    se existir. O nome da pasta do job e sempre o primeiro item de argv
    (ver gallica_enriquecer.py)."""
    if not job.argv:
        return None
    caminho = SAIDAS / "gallica_crawl" / job.argv[0] / "checkpoint_enriquecimento.json"
    if not caminho.exists():
        return None
    checkpoint = CheckpointEnriquecimento(**json.loads(caminho.read_text(encoding="utf-8")))
    total_lotes = math.ceil(checkpoint.total_itens / checkpoint.lote_tamanho) if checkpoint.total_itens else 0
    return f"lote {checkpoint.proximo_lote}/{total_lotes}"


_LEITORES_DE_PROGRESSO = {
    "gallica_crawl": _progresso_gallica_crawl,
    "gallica_enriquecer": _progresso_gallica_enriquecer,
}


def descrever_progresso(job: JobRegistrado) -> str:
    """Devolve uma linha de texto com o progresso do job, do jeito mais
    informativo possivel: le o checkpoint quando o motor conhece o formato
    (gallica_crawl, gallica_enriquecer); senao, mostra a ultima linha do
    log."""
    leitor = _LEITORES_DE_PROGRESSO.get(job.modulo)
    if leitor:
        progresso = leitor(job)
        if progresso:
            return progresso
    caminho_log = Path(job.log_path)
    if caminho_log.exists():
        linhas = caminho_log.read_text(encoding="utf-8", errors="ignore").splitlines()
        if linhas:
            return f"log: {linhas[-1]}"
    return "sem informacao de progresso ainda"
```

- [ ] **Step 4: Rodar e confirmar que passam**

Run: `.venv\Scripts\python.exe -m pytest tests/test_jobs_motor.py -v`
Expected: todos passando (agora 32 no total).

- [ ] **Step 5: Commit**

```bash
git add src/buscador/core/jobs_motor.py tests/test_jobs_motor.py
git commit -m "feat: motor de jobs -- progresso a partir dos checkpoints conhecidos"
```

---

### Task 7: Motor — retomar um job

**Files:**
- Modify: `src/buscador/core/jobs_motor.py`
- Test: `tests/test_jobs_motor.py`

**Interfaces:**
- Produces: `retomar_job(id_job: str, caminho_registro: Path = CAMINHO_PADRAO) -> JobRegistrado`

- [ ] **Step 1: Escrever os testes**

```python
# acrescentar em tests/test_jobs_motor.py
def test_retomar_job_inicia_um_job_novo_com_mesmo_modulo_e_argv(tmp_path, monkeypatch):
    caminho_registro = tmp_path / "registro.json"
    monkeypatch.setitem(jobs_motor.MODULOS_PERMITIDOS, "echo_teste", "tests.fixtures.job_fake")
    monkeypatch.setattr(jobs_motor, "PASTA_JOBS", tmp_path / "jobs")
    original = jobs_motor.iniciar_job("echo_teste", ["0"], caminho_registro)

    retomado = jobs_motor.retomar_job(original.id, caminho_registro)

    assert retomado.id != original.id
    assert retomado.modulo == "echo_teste"
    assert retomado.argv == ["0"]


def test_retomar_job_com_id_inexistente_da_erro(tmp_path):
    caminho_registro = tmp_path / "registro.json"
    salvar_registro([], caminho_registro)

    with pytest.raises(ValueError):
        jobs_motor.retomar_job("nao-existe", caminho_registro)
```

- [ ] **Step 2: Rodar e confirmar que falham**

Run: `.venv\Scripts\python.exe -m pytest tests/test_jobs_motor.py -v -k retomar_job`
Expected: `AttributeError: module 'buscador.core.jobs_motor' has no attribute 'retomar_job'`

- [ ] **Step 3: Implementar (acrescentar ao final de `jobs_motor.py`)**

```python
def retomar_job(id_job: str, caminho_registro: Path = CAMINHO_PADRAO) -> JobRegistrado:
    """Inicia um job NOVO com o mesmo modulo e os mesmos argumentos de um
    job anterior (rodando ou nao) -- nao precisa de nada especial pra
    'retomar' de verdade, porque os proprios comandos (gallica_crawl,
    gallica_enriquecer) ja sabem continuar de onde pararam sozinhos, pelo
    checkpoint deles, desde que sejam chamados com a mesma consulta/job."""
    jobs = {job.id: job for job in carregar_registro(caminho_registro)}
    job_antigo = jobs.get(id_job)
    if job_antigo is None:
        raise ValueError(f"Nenhum job encontrado com id '{id_job}'")
    return iniciar_job(job_antigo.modulo, job_antigo.argv, caminho_registro)
```

- [ ] **Step 4: Rodar e confirmar que passam**

Run: `.venv\Scripts\python.exe -m pytest tests/test_jobs_motor.py -v`
Expected: todos passando (agora 34 no total).

- [ ] **Step 5: Commit**

```bash
git add src/buscador/core/jobs_motor.py tests/test_jobs_motor.py
git commit -m "feat: motor de jobs -- retomar um job"
```

---

### Task 8: Linha de comando (`jobs_cli.py`)

**Files:**
- Create: `src/buscador/jobs_cli.py`
- Test: `tests/test_jobs_cli.py`

**Interfaces:**
- Consumes: `iniciar_job`, `parar_job`, `reconciliar_estados`, `retomar_job`, `descrever_progresso` (de `buscador.core.jobs_motor`, Tasks 3-7); `CAMINHO_PADRAO` (de `buscador.core.jobs_registro`)
- Produces: `main(argv=None) -> int`

- [ ] **Step 1: Escrever os testes**

```python
# -*- coding: utf-8 -*-
# tests/test_jobs_cli.py
import time

from buscador import jobs_cli
from buscador.core import jobs_motor
from buscador.core.jobs_registro import JobRegistrado, carregar_registro, salvar_registro


def test_status_sem_nenhum_job_mostra_mensagem_amigavel(tmp_path, capsys):
    caminho_registro = tmp_path / "registro.json"

    codigo = jobs_cli.main(["--registro", str(caminho_registro), "status"])

    assert codigo == 0
    assert "Nenhum job" in capsys.readouterr().out


def test_iniciar_e_status_de_ponta_a_ponta(tmp_path, monkeypatch, capsys):
    caminho_registro = tmp_path / "registro.json"
    monkeypatch.setitem(jobs_motor.MODULOS_PERMITIDOS, "cli", "tests.fixtures.job_fake")
    monkeypatch.setattr(jobs_motor, "PASTA_JOBS", tmp_path / "jobs")

    codigo = jobs_cli.main(["--registro", str(caminho_registro), "iniciar", "cli", "0"])
    assert codigo == 0
    assert "iniciado" in capsys.readouterr().out

    prazo = time.time() + 15
    saida_status = ""
    while time.time() < prazo:
        jobs_cli.main(["--registro", str(caminho_registro), "status"])
        saida_status = capsys.readouterr().out
        if "concluido" in saida_status:
            break
        time.sleep(0.3)

    assert "concluido" in saida_status


def test_parar_via_cli(tmp_path, capsys):
    caminho_registro = tmp_path / "registro.json"
    job = JobRegistrado(id="j1", modulo="cli", argv=[], pid=999999, estado="rodando",
                         log_path=str(tmp_path / "log.txt"))
    salvar_registro([job], caminho_registro)

    codigo = jobs_cli.main(["--registro", str(caminho_registro), "parar", "j1"])

    assert codigo == 0
    assert carregar_registro(caminho_registro)[0].estado == "parado"


def test_parar_e_retomar_com_id_inexistente_mostram_mensagem_amigavel(tmp_path, capsys):
    caminho_registro = tmp_path / "registro.json"
    salvar_registro([], caminho_registro)

    codigo_parar = jobs_cli.main(["--registro", str(caminho_registro), "parar", "nao-existe"])
    codigo_retomar = jobs_cli.main(["--registro", str(caminho_registro), "retomar", "nao-existe"])

    saida = capsys.readouterr().out
    assert codigo_parar == 1 and codigo_retomar == 1
    assert "Nao deu para parar" in saida
    assert "Nao deu para retomar" in saida
```

- [ ] **Step 2: Rodar e confirmar que falham**

Run: `.venv\Scripts\python.exe -m pytest tests/test_jobs_cli.py -v`
Expected: `ModuleNotFoundError: No module named 'buscador.jobs_cli'`

- [ ] **Step 3: Implementar**

```python
# -*- coding: utf-8 -*-
"""
Ponto de entrada de linha de comando do motor de jobs -- roda quando voce
digita "python -m buscador.jobs_cli <comando>". Comandos disponiveis:
iniciar, status, parar, retomar. O trabalho de verdade fica em
core/jobs_motor.py -- este arquivo so le os argumentos e chama o motor.
"""
import argparse
from pathlib import Path

from buscador.core.jobs_motor import (
    descrever_progresso,
    iniciar_job,
    parar_job,
    reconciliar_estados,
    retomar_job,
)
from buscador.core.jobs_registro import CAMINHO_PADRAO


def _comando_iniciar(args):
    job = iniciar_job(args.modulo, args.argv, args.registro)
    print(f"Job '{job.id}' iniciado (modulo: {job.modulo}, pid: {job.pid}).")
    return 0


def _comando_status(args):
    jobs = reconciliar_estados(args.registro)
    if not jobs:
        print("Nenhum job no registro ainda.")
        return 0
    for job in jobs:
        progresso = descrever_progresso(job) if job.estado == "rodando" else ""
        linha = f"[{job.estado}] {job.id} (modulo: {job.modulo})"
        if progresso:
            linha += f" -- {progresso}"
        print(linha)
    return 0


def _comando_parar(args):
    # parar_job levanta ValueError (id inexistente) ou RuntimeError (nao deu
    # pra parar com seguranca: nada foi morto e o estado nao mudou)
    try:
        job = parar_job(args.id, args.registro)
    except (ValueError, RuntimeError) as erro:
        print(f"Nao deu para parar: {erro}")
        return 1
    print(f"Job '{job.id}': {job.estado}.")
    return 0


def _comando_retomar(args):
    try:
        job = retomar_job(args.id, args.registro)
    except ValueError as erro:
        print(f"Nao deu para retomar: {erro}")
        return 1
    print(f"Job '{args.id}' retomado como '{job.id}' (pid: {job.pid}).")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description="Motor de jobs do BuscadorBaixador.")
    parser.add_argument("--registro", default=CAMINHO_PADRAO, type=Path,
                         help="Caminho do arquivo de registro (uso interno/testes)")
    subparsers = parser.add_subparsers(dest="comando", required=True)

    p_iniciar = subparsers.add_parser("iniciar", help="Inicia um job novo")
    p_iniciar.add_argument("modulo", choices=["cli", "gallica_crawl", "gallica_enriquecer"])
    p_iniciar.add_argument("argv", nargs=argparse.REMAINDER,
                            help="Argumentos passados pro comando de verdade (ex.: --adapter phpbb)")
    # REMAINDER (nao "*") e essencial aqui -- com "*" o argparse tentaria
    # interpretar algo como "--adapter" como uma opcao DESTE parser (que
    # nao existe) e falharia, em vez de simplesmente repassar pro comando
    # real. REMAINDER pega tudo que sobrar depois de "modulo", sem tentar
    # interpretar nada.
    p_iniciar.set_defaults(funcao=_comando_iniciar)

    p_status = subparsers.add_parser("status", help="Mostra todos os jobs e o progresso deles")
    p_status.set_defaults(funcao=_comando_status)

    p_parar = subparsers.add_parser("parar", help="Para um job em andamento")
    p_parar.add_argument("id")
    p_parar.set_defaults(funcao=_comando_parar)

    p_retomar = subparsers.add_parser("retomar", help="Inicia de novo um job (mesmo modulo/argumentos)")
    p_retomar.add_argument("id")
    p_retomar.set_defaults(funcao=_comando_retomar)

    args = parser.parse_args(argv)
    return args.funcao(args)


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Rodar e confirmar que passam**

Run: `.venv\Scripts\python.exe -m pytest tests/test_jobs_cli.py -v`
Expected: `4 passed`

- [ ] **Step 5: Commit**

```bash
git add src/buscador/jobs_cli.py tests/test_jobs_cli.py
git commit -m "feat: linha de comando do motor de jobs (jobs_cli.py)"
```

---

### Task 9: Notificação real quando um job trava esperando ação humana

**Files:**
- Modify: `src/buscador/cli.py`
- Modify: `src/buscador/gallica_crawl.py`
- Modify: `tests/test_cli.py`
- Modify: `tests/test_gallica_crawl.py`

**Interfaces:**
- Consumes: `avisar_windows` (de `buscador.core.jobs_notificacoes`, Task 2)

- [ ] **Step 1: Escrever o teste em `tests/test_cli.py`**

Acrescentar, depois de `test_main_acao_humana_necessaria_mostra_aviso_amigavel`:

```python
def test_main_acao_humana_necessaria_dispara_notificacao_windows(monkeypatch):
    chamadas = []
    monkeypatch.setattr(cli, "construir_adapter", lambda nome, url: AdapterFakePrecisaChave(url))
    monkeypatch.setattr(cli, "avisar_windows", lambda titulo, mensagem: chamadas.append((titulo, mensagem)))

    cli.main(["https://grand-sud-medieval.fr/forum/viewtopic.php?f=14&t=1", "--adapter", "phpbb"])

    assert len(chamadas) == 1
    titulo, mensagem = chamadas[0]
    assert "tal-site" in mensagem
    assert "cadastre-se" in mensagem
```

- [ ] **Step 2: Rodar e confirmar que falha**

Run: `.venv\Scripts\python.exe -m pytest tests/test_cli.py -v -k dispara_notificacao`
Expected: `AttributeError: <module 'buscador.cli'> does not have the attribute 'avisar_windows'`

- [ ] **Step 3: Modificar `cli.py`**

No topo do arquivo, junto dos outros imports de `buscador.core`, acrescentar:

```python
from buscador.core.jobs_notificacoes import avisar_windows
```

No bloco `except AcaoHumanaNecessaria as erro:` dentro de `main()` (por volta da linha 120-126), trocar:

```python
    except AcaoHumanaNecessaria as erro:
        # Sinal especial (ver core/acao_humana.py): o programa precisa que
        # o Samuel faça algo (conseguir uma chave, logar, resolver um
        # CAPTCHA) antes de continuar. Mostra a instrução e para de forma
        # limpa -- rodar o comando de novo depois resolve.
        print(formatar_aviso(erro))
        return 1
```

por:

```python
    except AcaoHumanaNecessaria as erro:
        # Sinal especial (ver core/acao_humana.py): o programa precisa que
        # o Samuel faça algo (conseguir uma chave, logar, resolver um
        # CAPTCHA) antes de continuar. Mostra a instrução, dispara uma
        # notificação do Windows (pra avisar mesmo sem ninguém olhando o
        # terminal), e para de forma limpa -- rodar o comando de novo
        # depois resolve.
        aviso = formatar_aviso(erro)
        print(aviso)
        avisar_windows("BuscadorBaixador precisa de ajuda", aviso)
        return 1
```

- [ ] **Step 4: Rodar e confirmar que passa**

Run: `.venv\Scripts\python.exe -m pytest tests/test_cli.py -v`
Expected: todos os testes do arquivo passando (o existente e o novo).

- [ ] **Step 5: Escrever o teste em `tests/test_gallica_crawl.py`**

Já existe `test_acao_humana_necessaria_mostra_aviso_e_preserva_progresso` (perto do final do
arquivo) testando esse mesmo caminho sem checar notificação. Acrescentar um teste novo logo
depois dele, no mesmo estilo:

```python
def test_acao_humana_necessaria_dispara_notificacao_windows(tmp_path, monkeypatch):
    monkeypatch.setattr(gallica_crawl, "DIRETORIO_COLETAS", tmp_path)

    def coletar_que_precisa_de_login(*args, **kwargs):
        raise AcaoHumanaNecessaria(TIPO_LOGIN, "precisa logar em tal-site", site="tal-site")
    monkeypatch.setattr(gallica_crawl, "coletar", coletar_que_precisa_de_login)

    chamadas = []
    monkeypatch.setattr(gallica_crawl, "avisar_windows", lambda titulo, mensagem: chamadas.append((titulo, mensagem)))

    gallica_crawl.main([CONSULTA])

    assert len(chamadas) == 1
    titulo, mensagem = chamadas[0]
    assert "precisa logar em tal-site" in mensagem
```

- [ ] **Step 6: Rodar e confirmar que o teste novo falha**

Run: `.venv\Scripts\python.exe -m pytest tests/test_gallica_crawl.py -v -k dispara_notificacao`
Expected: `AttributeError: <module 'buscador.gallica_crawl'> does not have the attribute 'avisar_windows'`

- [ ] **Step 7: Modificar `gallica_crawl.py`**

No topo do arquivo, acrescentar:

```python
from buscador.core.jobs_notificacoes import avisar_windows
```

No bloco `except AcaoHumanaNecessaria as erro:` dentro de `main()` (por volta da linha 106-113), trocar:

```python
    except AcaoHumanaNecessaria as erro:
        # sinal especial (ver core/acao_humana.py): precisa que o Samuel
        # faça algo antes de continuar. Como o progresso já está salvo em
        # disco (checkpoint + CSV), não se perde nada -- só avisa onde
        # está, pra ele rodar o mesmo comando de novo depois de resolver.
        print(formatar_aviso(erro))
        print(f"O progresso ja salvo continua em {diretorio_job} -- rode este comando de novo depois de resolver.")
        return 1
```

por:

```python
    except AcaoHumanaNecessaria as erro:
        # sinal especial (ver core/acao_humana.py): precisa que o Samuel
        # faça algo antes de continuar. Como o progresso já está salvo em
        # disco (checkpoint + CSV), não se perde nada -- só avisa onde
        # está (e dispara notificação do Windows), pra ele rodar o mesmo
        # comando de novo depois de resolver.
        aviso = formatar_aviso(erro)
        print(aviso)
        print(f"O progresso ja salvo continua em {diretorio_job} -- rode este comando de novo depois de resolver.")
        avisar_windows("BuscadorBaixador precisa de ajuda", aviso)
        return 1
```

- [ ] **Step 8: Rodar a suíte inteira e confirmar que nada quebrou**

Run: `.venv\Scripts\python.exe -m pytest -q`
Expected: todos os testes passando (contagem anterior + os novos deste plano).

- [ ] **Step 9: Commit**

```bash
git add src/buscador/cli.py src/buscador/gallica_crawl.py tests/test_cli.py tests/test_gallica_crawl.py
git commit -m "feat: notificacao real do Windows quando um job trava esperando acao humana"
```

---

### Task 10: Empacotamento — `.bat`, `.gitignore`

**Files:**
- Create: `jobs.bat`
- Modify: `.gitignore`

**Interfaces:** nenhuma (só empacotamento, sem código novo)

- [ ] **Step 1: Criar `jobs.bat`** (mesmo padrão de `gallica_crawl.bat`)

```bat
@echo off
chcp 65001 >nul
echo Preparando o ambiente (so na primeira vez pode demorar um pouco)...
"%~dp0.venv\Scripts\python.exe" -m pip install -e "%~dp0" --quiet
"%~dp0.venv\Scripts\python.exe" -m buscador.jobs_cli %*
echo.
pause
```

- [ ] **Step 2: Acrescentar ao `.gitignore`**

No final do arquivo, acrescentar:

```
# Registro e logs do motor de jobs (estado local, nao pertence ao repositorio)
jobs/
```

- [ ] **Step 3: Testar manualmente que o `.bat` funciona**

Rodar `jobs.bat status` a partir do Explorer (duplo clique) ou `jobs.bat status` no terminal —
deve mostrar "Nenhum job no registro ainda." sem erro.

- [ ] **Step 4: Commit**

```bash
git add jobs.bat .gitignore
git commit -m "chore: lançador .bat e .gitignore do motor de jobs"
```

---

## Verificação final (depois de todas as tasks)

- [ ] Rodar a suíte inteira: `.venv\Scripts\python.exe -m pytest -q` — deve passar sem falhas.
- [ ] Teste manual de ponta a ponta com um job de verdade e curto:
  `jobs.bat iniciar cli "https://grand-sud-medieval.fr/forum/viewtopic.php?f=14&t=9264" --adapter phpbb`
  seguido de `jobs.bat status` (repetir até aparecer `concluido`) — confirma que o motor
  consegue rodar e terminar um job real do jeito que o Samuel vai usar no dia a dia.
- [ ] Teste manual de parar/retomar: iniciar `gallica_crawl` com uma consulta pequena,
  `jobs.bat parar <id>` no meio, confirmar que o checkpoint em `saidas/gallica_crawl/.../checkpoint.json`
  não foi corrompido, depois `jobs.bat retomar <id>` e confirmar que continua de onde parou.
