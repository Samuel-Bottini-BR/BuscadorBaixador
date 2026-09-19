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
