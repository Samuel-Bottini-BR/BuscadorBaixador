# -*- coding: utf-8 -*-
"""Guarda o progresso de uma coleta longa (Etapa 1 da Gallica) para poder
retomar de onde parou se o programa for interrompido -- ver CLAUDE.md,
secao sobre mapear o catalogo inteiro da Gallica."""
import hashlib
import json
import os
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Optional


class ConsultaDivergenteError(ValueError):
    """A consulta salva no checkpoint e diferente da que foi pedida agora --
    nunca retoma silenciosamente com a consulta errada."""


@dataclass
class Checkpoint:
    consulta: str
    tamanho_pagina: int
    proximo_start_record: int = 1
    total_registros_api: Optional[int] = None
    itens_gravados: int = 0
    concluido: bool = False
    atualizado_em: str = ""


def slug_consulta(consulta: str) -> str:
    """Nome de pasta legivel a partir da consulta: pedaco legivel da propria
    consulta + hash curto (o hash e o que garante que duas consultas
    diferentes nunca vao usar a mesma pasta por engano)."""
    pedaco = re.sub(r"[^a-z0-9]+", "-", consulta.lower()).strip("-")[:40] or "consulta"
    hash_curto = hashlib.sha1(consulta.encode("utf-8")).hexdigest()[:10]
    return f"{pedaco}-{hash_curto}"


def carregar_ou_criar(caminho_json, consulta, tamanho_pagina) -> Checkpoint:
    """Se ja existe um checkpoint salvo pra essa consulta, retoma dele. Se
    nao existe, cria um novo do zero (comecando na pagina 1)."""
    if caminho_json.exists():
        dados = json.loads(caminho_json.read_text(encoding="utf-8"))
        checkpoint = Checkpoint(**dados)
        if checkpoint.consulta != consulta:
            raise ConsultaDivergenteError(
                f"O checkpoint em '{caminho_json}' foi salvo para a consulta "
                f"'{checkpoint.consulta}', mas agora foi pedida '{consulta}'. "
                "Use outro --job ou apague o checkpoint antigo antes de continuar."
            )
        return checkpoint
    checkpoint = Checkpoint(consulta=consulta, tamanho_pagina=tamanho_pagina)
    salvar(checkpoint, caminho_json)
    return checkpoint


def salvar(checkpoint: Checkpoint, caminho_json) -> None:
    """Grava em um arquivo temporario e so depois troca pelo definitivo --
    assim, se o programa for morto no meio da gravacao, o checkpoint antigo
    (ainda valido) nunca fica corrompido."""
    checkpoint.atualizado_em = datetime.now(timezone.utc).isoformat()
    caminho_json.parent.mkdir(parents=True, exist_ok=True)
    caminho_tmp = caminho_json.with_suffix(caminho_json.suffix + ".tmp")
    caminho_tmp.write_text(
        json.dumps(asdict(checkpoint), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    os.replace(caminho_tmp, caminho_json)
