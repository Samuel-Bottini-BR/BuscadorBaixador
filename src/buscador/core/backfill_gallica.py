# -*- coding: utf-8 -*-
"""
Motor do "backfill" da Gallica: para os ark ids que o cruzamento com a
Lista 1 (o índice SRU oficial, "monographie") NÃO conseguiu casar (Tarefa
A3), busca ao vivo na própria Gallica -- em LOTES de ark ids de cada vez,
não um por um -- os metadados que faltam (autor, ano, domínio público,
idioma). Um ark id não bater não é erro: normalmente é porque a obra é de
um tipo fora do escopo "monographie" do índice oficial (periódico,
fascículo, etc.), mas ainda existe na Gallica.

Espelha DE PROPÓSITO o desenho de resiliência já comprovado ao vivo em
core/coleta_gallica.py::coletar -- mesma ordem de gravação (resultado
primeiro, checkpoint depois) e mesma estrutura de decisão de erro (429 ->
cooldown e recomeça; resposta vazia inesperada -> cooldown menor e
recomeça; erro de rede/5xx -> cooldown de infraestrutura e recomeça; 4xx
que não seja 429 -> propaga, não é recuperável sozinho). A diferença é que
aqui a unidade retomável é um LOTE de ark ids (uma consulta CQL por lote),
não uma página de uma busca contínua -- por isso esse tratamento de erro é
uma cópia adaptada, não uma chamada compartilhada com coleta_gallica.py
(decisão já tomada: abstrair agora seria mais risco que ganho).
"""
import json
import math
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone

import requests

from buscador.adapters.gallica import (
    GallicaAdapter,
    RespostaVaziaInesperadaError,
    construir_consulta_lote_ark_ids,
)
from buscador.core.chaves_gallica import extrair_ark_id
from buscador.core.escrita_atomica import salvar_json_atomico

# Mesmos números-palpite de core/coleta_gallica.py (ver comentários lá pra
# contexto de onde vieram) -- reaproveitados aqui porque o comportamento da
# API é o mesmo, só a unidade retomável (lote em vez de página) muda.
COOLDOWN_429_PADRAO_SEGUNDOS = 10 * 60
COOLDOWN_LOTE_VAZIO_PADRAO_SEGUNDOS = 30
COOLDOWN_INFRA_PADRAO_SEGUNDOS = 60


@dataclass
class CheckpointBackfill:
    # A "caixinha" de progresso deste backfill -- parecida com o Checkpoint
    # de core/checkpoint.py e o CheckpointEnriquecimento de
    # core/enriquecimento_lote.py, mas aqui o progresso é "em que LOTE de
    # ark ids eu parei", e guarda também as contagens de achado/não-achado
    # (só informativo, pra acompanhar o andamento sem reabrir o resultado).
    total_arks: int
    tamanho_lote: int
    proximo_lote: int = 0
    encontrados: int = 0
    nao_encontrados: int = 0
    concluido: bool = False
    atualizado_em: str = ""


def carregar_ou_criar_checkpoint(caminho_json, total_arks, tamanho_lote) -> CheckpointBackfill:
    """Se já existe um checkpoint salvo nesse caminho, retoma dele -- MAS só
    se a chamada atual pedir os MESMOS total_arks/tamanho_lote que o
    checkpoint salvo tem gravados. Isso importa porque, diferente de uma
    consulta CQL (que ou é a mesma string ou não é), aqui "proximo_lote" é
    só um número de deslocamento (offset) dentro de uma LISTA de ark ids --
    se essa lista for regerada com tamanho diferente (ex.: a tarefa A4
    rodar de novo e mudar arks_faltantes.json) e o backfill for chamado de
    novo apontando pro MESMO diretorio_job sem limpar o checkpoint antigo,
    retomar silenciosamente aplicaria esse offset (calculado pra lista
    ANTIGA) na lista NOVA -- pulando um pedaço inteiro dela sem erro
    nenhum, e o job ainda terminaria com concluido=True. Levanta ValueError
    em vez disso (mesma intenção protetora de
    core/checkpoint.py::ConsultaDivergenteError, mas sem replicar a classe
    de erro específica dele -- aqui um ValueError simples com uma mensagem
    clara já basta). Se não existe checkpoint salvo ainda, cria um novo do
    zero (começando no lote 0)."""
    if caminho_json.exists():
        dados = json.loads(caminho_json.read_text(encoding="utf-8"))
        checkpoint = CheckpointBackfill(**dados)
        if checkpoint.total_arks != total_arks or checkpoint.tamanho_lote != tamanho_lote:
            raise ValueError(
                f"O checkpoint em '{caminho_json}' foi salvo para total_arks="
                f"{checkpoint.total_arks}, tamanho_lote={checkpoint.tamanho_lote}, mas agora "
                f"foi pedido total_arks={total_arks}, tamanho_lote={tamanho_lote}. Retomar "
                "silenciosamente arriscaria pular ou reprocessar ark ids errados -- use outro "
                "diretorio_job ou apague o checkpoint antigo antes de continuar."
            )
        return checkpoint
    checkpoint = CheckpointBackfill(total_arks=total_arks, tamanho_lote=tamanho_lote)
    salvar_checkpoint(checkpoint, caminho_json)
    return checkpoint


def salvar_checkpoint(checkpoint: CheckpointBackfill, caminho_json) -> None:
    """Grava o checkpoint de forma atômica via escrita_atomica.salvar_json_atomico
    (a mesma técnica de arquivo temporário + os.replace usada em
    core/checkpoint.py::salvar, já generalizada nesse módulo)."""
    checkpoint.atualizado_em = datetime.now(timezone.utc).isoformat()
    salvar_json_atomico(asdict(checkpoint), caminho_json)


def _carregar_resultado(caminho_resultado):
    if caminho_resultado.exists():
        return json.loads(caminho_resultado.read_text(encoding="utf-8"))
    return {}


def backfill(ark_ids, diretorio_job, tamanho_lote=50, cliente=None, dormir=time.sleep, progresso_fct=None):
    """Roda ou retoma o backfill de uma lista inteira de ark ids, lote por
    lote. Por lote confirmado: reescreve resultado_backfill.json por
    inteiro (com TODOS os resultados já conhecidos, não só o lote atual) e
    SÓ DEPOIS avança e salva o checkpoint -- nessa ordem, o pior caso de uma
    interrupção é repetir 1 lote inteiro na próxima chamada (idempotente:
    reprocessar o mesmo lote de novo só sobrescreve as mesmas entradas com
    o mesmo resultado, nunca perde nada já salvo). Um ark id pedido que não
    aparece nos itens devolvidos pela Gallica vira "nao_encontrado" -- isso
    é um resultado NORMAL (a obra pode ser de um tipo fora do escopo do
    índice oficial), não um erro.

    Tratamento de erro por lote (mesma estrutura de decisão de
    coleta_gallica.py::coletar, adaptada de página pra lote): se um 429
    sobreviver às tentativas do ClienteEducado, pausa por
    COOLDOWN_429_PADRAO_SEGUNDOS e recomeça do mesmo lote. Se vier uma
    resposta vazia inesperada (RespostaVaziaInesperadaError -- falha
    temporária da Gallica, não o fim real da busca), pausa por
    COOLDOWN_LOTE_VAZIO_PADRAO_SEGUNDOS e recomeça do mesmo lote. Se a
    infraestrutura falhar (rede: timeout/erro de conexão; ou servidor:
    5xx), pausa por COOLDOWN_INFRA_PADRAO_SEGUNDOS e recomeça do mesmo
    lote. Só um 4xx que NÃO seja 429 propaga de verdade -- indica problema
    na nossa própria requisição, que tentar de novo pra sempre não
    resolve."""
    # "dormir=time.sleep" e "progresso_fct=None": mesmo motivo de
    # coleta_gallica.py -- permitir testar sem esperar tempo real de
    # verdade e sem obrigar I/O de console.
    diretorio_job.mkdir(parents=True, exist_ok=True)
    caminho_checkpoint = diretorio_job / "checkpoint_backfill.json"
    caminho_resultado = diretorio_job / "resultado_backfill.json"
    checkpoint = carregar_ou_criar_checkpoint(caminho_checkpoint, len(ark_ids), tamanho_lote)
    if checkpoint.concluido:
        return checkpoint  # já tinha terminado antes -- nada a fazer, nenhuma chamada à API

    resultado = _carregar_resultado(caminho_resultado)
    total_lotes = math.ceil(len(ark_ids) / tamanho_lote) if ark_ids else 0

    while checkpoint.proximo_lote < total_lotes:
        indice = checkpoint.proximo_lote
        lote = ark_ids[indice * tamanho_lote: (indice + 1) * tamanho_lote]
        try:
            quantidade_encontrada = _processar_lote(lote, resultado, cliente, tamanho_lote)
        except requests.HTTPError as erro:
            # "HTTPError" é o erro que a biblioteca requests levanta quando
            # a resposta veio com um código de "deu errado".
            codigo = erro.response.status_code if erro.response is not None else None
            if codigo == 429:
                print(f"429 persistente no lote {indice}; pausando "
                      f"{COOLDOWN_429_PADRAO_SEGUNDOS}s antes de tentar de novo...")
                dormir(COOLDOWN_429_PADRAO_SEGUNDOS)
                continue  # volta pro início do "while" -- tenta o MESMO lote de novo
            if codigo is not None and codigo >= 500:
                print(f"Erro do servidor da Gallica ({codigo}) no lote {indice}; pausando "
                      f"{COOLDOWN_INFRA_PADRAO_SEGUNDOS}s antes de tentar de novo...")
                dormir(COOLDOWN_INFRA_PADRAO_SEGUNDOS)
                continue
            raise  # 4xx que não é 429: problema na nossa requisição, não adianta tentar de novo
        except RespostaVaziaInesperadaError as erro:
            print(f"{erro} Pausando {COOLDOWN_LOTE_VAZIO_PADRAO_SEGUNDOS}s antes de tentar de novo...")
            dormir(COOLDOWN_LOTE_VAZIO_PADRAO_SEGUNDOS)
            continue
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as erro:
            print(f"Falha de rede ({erro.__class__.__name__}) no lote {indice}; pausando "
                  f"{COOLDOWN_INFRA_PADRAO_SEGUNDOS}s antes de tentar de novo...")
            dormir(COOLDOWN_INFRA_PADRAO_SEGUNDOS)
            continue

        # lote processado com sucesso: grava o resultado PRIMEIRO...
        salvar_json_atomico(resultado, caminho_resultado)
        # ...e SÓ DEPOIS avança e salva o checkpoint -- essa ordem é o que
        # garante que uma interrupção no pior caso repete 1 lote, nunca
        # perde um resultado já salvo (ver docstring desta função)
        checkpoint.proximo_lote = indice + 1
        checkpoint.encontrados += quantidade_encontrada
        checkpoint.nao_encontrados += len(lote) - quantidade_encontrada
        salvar_checkpoint(checkpoint, caminho_checkpoint)
        if progresso_fct is not None:
            progresso_fct(checkpoint)  # chama a função de mostrar progresso na tela, se foi passada uma

    checkpoint.concluido = True
    salvar_checkpoint(checkpoint, caminho_checkpoint)
    # reescreve o resultado por completude mesmo se nenhum lote rodou (ex.:
    # ark_ids vazio) -- assim resultado_backfill.json sempre existe depois
    # de uma chamada que não retornou cedo por já estar concluído
    salvar_json_atomico(resultado, caminho_resultado)
    return checkpoint


def _processar_lote(lote_ark_ids, resultado, cliente, tamanho_lote):
    """Busca UM lote de ark ids na Gallica (uma consulta CQL só, via
    construir_consulta_lote_ark_ids) e escreve o resultado de cada ark id
    pedido diretamente no dict "resultado" (em memória -- quem chama decide
    quando gravar em disco). Só mexe em "resultado" depois de já ter
    coletado todos os itens devolvidos com sucesso: se a busca falhar no
    meio, nenhuma entrada deste lote é escrita, então uma nova tentativa
    depois começa limpa, sem entrada parcial. Devolve quantos ark ids deste
    lote foram encontrados."""
    consulta = construir_consulta_lote_ark_ids(lote_ark_ids)
    adapter = GallicaAdapter(consulta, cliente=cliente, max_resultados=tamanho_lote, tamanho_pagina=tamanho_lote)
    itens_por_ark_id = {}
    for item in adapter.iter_itens():
        ark_id = extrair_ark_id(item.link)
        if ark_id in lote_ark_ids:
            # "in" numa lista pequena (no máximo tamanho_lote) é barato o
            # suficiente aqui -- não precisa de um set só pra isso
            itens_por_ark_id[ark_id] = item

    quantidade_encontrada = 0
    for ark_id in lote_ark_ids:
        item = itens_por_ark_id.get(ark_id)
        if item is not None:
            resultado[ark_id] = {
                "status": "encontrado",
                "autor": item.autor,
                "ano": item.ano,
                "dominio_publico": item.dominio_publico,
                "idioma_origem": item.extra.get("idioma_origem"),
            }
            quantidade_encontrada += 1
        else:
            # ark id pedido que não apareceu nos itens devolvidos -- normal
            # (ver docstring do módulo), não um erro
            resultado[ark_id] = {
                "status": "nao_encontrado",
                "autor": None,
                "ano": None,
                "dominio_publico": None,
                "idioma_origem": None,
            }
    return quantidade_encontrada
