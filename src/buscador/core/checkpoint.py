# -*- coding: utf-8 -*-
"""
"Checkpoint" (ponto de checagem/salvamento) é o mecanismo que guarda o
progresso de uma coleta longa (a Etapa 1 da Gallica, que pode levar horas
ou dias) pra poder retomar de onde parou se o programa for interrompido --
por qualquer motivo: você fechou o terminal, o computador reiniciou, deu
erro no meio. Ver CLAUDE.md, seção sobre mapear o catálogo inteiro da
Gallica, pra mais contexto de por que isso importa tanto aqui.
"""
import hashlib  # cria um "hash" -- um código curto e único calculado a partir de um texto
import json  # formato de arquivo/texto pra guardar dados estruturados (o mesmo usado pra configurações de muitos programas)
import os
import re
from dataclasses import asdict, dataclass  # dataclass: "caixinha" de dados; asdict: transforma essa caixinha num dicionário comum
from datetime import datetime, timezone
from typing import Optional  # "Optional[int]" quer dizer "ou é um número inteiro, ou é None (vazio)"


class ConsultaDivergenteError(ValueError):
    """A consulta salva no checkpoint e diferente da que foi pedida agora --
    nunca retoma silenciosamente com a consulta errada."""
    # Herda de ValueError (um erro já existente do Python pra "valor
    # inválido") em vez de Exception direto -- assim, quem quiser pode
    # capturar tanto esse erro específico quanto qualquer ValueError em geral.


@dataclass
class Checkpoint:
    # Cada checkpoint salvo guarda essas informações. Os campos com "="
    # têm um valor padrão (usado se não for informado na hora de criar).
    consulta: str  # a busca que está sendo coletada (ex.: 'dc.type all "monographie"')
    tamanho_pagina: int  # quantos itens são pedidos por vez à API
    proximo_start_record: int = 1  # de onde continuar a busca na próxima vez (ver adapters/gallica.py)
    total_registros_api: Optional[int] = None  # quantos itens a API disse que essa busca tem no total (só descobre na primeira página)
    itens_gravados: int = 0  # quantos já foram salvos até agora
    concluido: bool = False  # True quando a coleta inteira já terminou
    atualizado_em: str = ""  # data/hora da última vez que este checkpoint foi salvo


def slug_consulta(consulta: str) -> str:
    """Nome de pasta legivel a partir da consulta: pedaco legivel da propria
    consulta + hash curto (o hash e o que garante que duas consultas
    diferentes nunca vao usar a mesma pasta por engano)."""
    # "slug" é um texto convertido pra um formato seguro de usar em nome de
    # pasta/arquivo (só letra minúscula, número e hífen).
    pedaco = re.sub(r"[^a-z0-9]+", "-", consulta.lower()).strip("-")[:40] or "consulta"
    # transforma a consulta em texto seguro pra nome de pasta, cortando nos primeiros 40 caracteres
    hash_curto = hashlib.sha1(consulta.encode("utf-8")).hexdigest()[:10]
    # "sha1" calcula um código único a partir do texto da consulta -- duas
    # consultas MUITO parecidas (que dariam o mesmo "pedaço" legível
    # cortado) ainda teriam hash diferente, então nunca colidem na mesma pasta
    return f"{pedaco}-{hash_curto}"


def carregar_ou_criar(caminho_json, consulta, tamanho_pagina) -> Checkpoint:
    """Se ja existe um checkpoint salvo pra essa consulta, retoma dele. Se
    nao existe, cria um novo do zero (comecando na pagina 1)."""
    if caminho_json.exists():
        dados = json.loads(caminho_json.read_text(encoding="utf-8"))
        checkpoint = Checkpoint(**dados)
        # "Checkpoint(**dados)" cria um Checkpoint novo usando cada chave
        # do dicionário "dados" como um parâmetro nomeado -- um jeito
        # rápido de reconstruir o objeto a partir do que foi lido do JSON.
        if checkpoint.consulta != consulta:
            # trava de segurança: se o checkpoint salvo é de uma consulta
            # DIFERENTE da que estamos pedindo agora, para tudo em vez de
            # continuar por engano com o progresso errado
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
    # salva primeiro num arquivo "*.tmp" (temporário), não no arquivo
    # definitivo direto -- técnica pra nunca deixar o arquivo de verdade
    # pela metade se o programa travar bem no meio da escrita
    caminho_tmp.write_text(
        json.dumps(asdict(checkpoint), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    # "asdict(checkpoint)" transforma a "caixinha" Checkpoint num
    # dicionário comum; "json.dumps" transforma esse dicionário em texto
    # no formato JSON, prontinho pra salvar num arquivo
    os.replace(caminho_tmp, caminho_json)
    # "os.replace" troca o arquivo definitivo pelo temporário numa
    # operação só, que o sistema operacional garante que não fica pela
    # metade -- ou troca tudo de uma vez, ou (se der erro) não troca nada
