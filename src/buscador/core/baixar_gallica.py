# -*- coding: utf-8 -*-
"""
Motor de download em lote da Gallica (Tarefa C4, redesenhada em função do
achado da Tarefa C1/C-nav1: baixar via GET/HEAD simples não funciona --
a Gallica bloqueia com um desafio anti-robô "Altcha" que só um navegador
de verdade resolve, ver core/download_gallica_navegador.py). Por isso,
diferente do desenho original do plano (streaming via requests + sha256
incremental por chunk), aqui cada item é baixado por inteiro pelo
navegador (baixar_via_navegador) e o sha256 é calculado do arquivo já
completo em disco.

Espelha DE PROPÓSITO o desenho de resiliência já comprovado em
core/backfill_gallica.py -- checkpoint retomável, catálogo permanente
mesclado (nunca reescrito do zero), e falha isolada de 1 item não derruba
o lote inteiro.
"""
import hashlib
import json
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from buscador.core.download_gallica_navegador import baixar_via_navegador
from buscador.core.escrita_atomica import salvar_json_atomico


@dataclass
class CheckpointDownload:
    # Mesmo espírito do CheckpointBackfill (core/backfill_gallica.py), mas
    # a unidade retomável aqui é 1 ark id por vez (não um lote de vários),
    # já que cada download já é sua própria operação de rede longa (o
    # navegador demora dezenas de segundos POR ITEM -- ver confirmação ao
    # vivo da C-nav8).
    total_arks: int
    proximo_indice: int = 0
    baixados: int = 0
    falhas: int = 0
    concluido: bool = False
    atualizado_em: str = ""


def carregar_ou_criar_checkpoint(caminho_json: Path, total_arks: int) -> CheckpointDownload:
    """Mesma proteção de core/backfill_gallica.py::carregar_ou_criar_checkpoint:
    só retoma de um checkpoint salvo se ele foi gravado para o MESMO
    total_arks pedido agora -- evita aplicar um "proximo_indice" calculado
    pra uma lista antiga numa lista nova de tamanho diferente (pularia ou
    reprocessaria ark ids errados em silêncio)."""
    caminho_json = Path(caminho_json)
    if caminho_json.exists():
        dados = json.loads(caminho_json.read_text(encoding="utf-8"))
        checkpoint = CheckpointDownload(**dados)
        if checkpoint.total_arks != total_arks:
            raise ValueError(
                f"O checkpoint em '{caminho_json}' foi salvo para total_arks="
                f"{checkpoint.total_arks}, mas agora foi pedido total_arks={total_arks}. "
                "Retomar silenciosamente arriscaria pular ou reprocessar ark ids errados -- "
                "use outro diretorio_job ou apague o checkpoint antigo antes de continuar."
            )
        return checkpoint
    checkpoint = CheckpointDownload(total_arks=total_arks)
    salvar_checkpoint(checkpoint, caminho_json)
    return checkpoint


def salvar_checkpoint(checkpoint: CheckpointDownload, caminho_json: Path) -> None:
    """Grava o checkpoint de forma atômica (mesma técnica de
    core/escrita_atomica.py usada em todo o resto do projeto)."""
    checkpoint.atualizado_em = datetime.now(timezone.utc).isoformat()
    salvar_json_atomico(asdict(checkpoint), caminho_json)


def _sha256_arquivo(caminho: Path) -> str:
    """Calcula o sha256 de um arquivo já completo em disco, lendo em
    blocos de 1MB -- nunca carrega o arquivo inteiro (PDFs de dezenas de
    MB) na memória de uma vez."""
    hasher = hashlib.sha256()
    with open(caminho, "rb") as arquivo:
        for bloco in iter(lambda: arquivo.read(1024 * 1024), b""):
            hasher.update(bloco)
    return hasher.hexdigest()


def baixar_um(ark_id: str, pasta_destino: Path, baixar_fct=baixar_via_navegador, timeout_segundos=None) -> dict:
    """Baixa uma obra pelo ark id, usando baixar_fct (por padrão,
    baixar_via_navegador -- injetável pra testar sem abrir navegador de
    verdade). A Gallica nomeia o arquivo baixado com o título real da obra,
    não o ark id (confirmado ao vivo nas Tarefas C-nav1/C-nav8) -- por
    isso o arquivo é renomeado pro nome canônico "<ark_id>.pdf" antes de
    calcular o sha256, pra manter o catálogo e a pasta de destino
    previsíveis independente do título de cada obra.

    timeout_segundos (opcional): repassado pra baixar_fct quando informado
    -- achado ao vivo do lote real desta tarefa: o default de
    baixar_via_navegador (ver TIMEOUT_PADRAO_SEGUNDOS em
    core/download_gallica_navegador.py) pode não bastar dependendo das
    condições de rede/tamanho do arquivo; deixar configurável aqui evita
    ficar preso a um único valor fixo pra um lote inteiro.

    Returns:
        dict com sha256, caminho_local (string), bytes e baixado_em (ISO
        8601 UTC) -- pronto pra virar uma entrada do catálogo.
    """
    pasta_destino = Path(pasta_destino)
    kwargs = {} if timeout_segundos is None else {"timeout_segundos": timeout_segundos}
    caminho_baixado = baixar_fct(ark_id, pasta_destino, **kwargs)
    caminho_final = pasta_destino / f"{ark_id}.pdf"
    if Path(caminho_baixado) != caminho_final:
        Path(caminho_baixado).replace(caminho_final)
    return {
        "sha256": _sha256_arquivo(caminho_final),
        "caminho_local": str(caminho_final),
        "bytes": caminho_final.stat().st_size,
        "baixado_em": datetime.now(timezone.utc).isoformat(),
    }


def _carregar_catalogo(caminho_catalogo: Path) -> dict:
    if caminho_catalogo.exists():
        return json.loads(caminho_catalogo.read_text(encoding="utf-8"))
    return {}


def baixar_lote(
    ark_ids,
    diretorio_job: Path,
    pasta_destino: Path,
    caminho_catalogo: Path,
    baixar_fct=baixar_via_navegador,
    dormir=time.sleep,
    progresso_fct=None,
    timeout_segundos=None,
) -> CheckpointDownload:
    """Roda ou retoma o download de uma lista inteira de ark ids, um por
    vez. Pula (sem re-baixar) qualquer ark_id que já esteja no catálogo
    com sha256 preenchido -- permite rodar de novo sobre uma lista que
    parcialmente já foi baixada antes sem duplicar trabalho. Uma falha
    isolada (navegador travou, download não completou, etc.) não derruba
    o lote inteiro: é contada em `falhas` e o item fica de fora do
    catálogo, retomável numa chamada futura.

    Ordem de gravação por item (mesmo espírito de core/backfill_gallica.py):
    catálogo primeiro, checkpoint depois -- o pior caso de uma interrupção
    é reprocessar o item que estava em andamento na hora, nunca perder um
    catálogo já salvo.

    `dormir`/`progresso_fct` seguem o mesmo padrão injetável do resto do
    projeto (testar sem esperar tempo real / sem I/O de console).
    `timeout_segundos` (opcional) é repassado pra cada chamada de
    baixar_um -- deixa configurável por lote em vez de ficar preso ao
    default fixo de baixar_via_navegador.
    """
    diretorio_job = Path(diretorio_job)
    pasta_destino = Path(pasta_destino)
    caminho_catalogo = Path(caminho_catalogo)
    diretorio_job.mkdir(parents=True, exist_ok=True)
    pasta_destino.mkdir(parents=True, exist_ok=True)

    caminho_checkpoint = diretorio_job / "checkpoint_download.json"
    checkpoint = carregar_ou_criar_checkpoint(caminho_checkpoint, len(ark_ids))
    if checkpoint.concluido:
        return checkpoint

    catalogo = _carregar_catalogo(caminho_catalogo)

    while checkpoint.proximo_indice < len(ark_ids):
        ark_id = ark_ids[checkpoint.proximo_indice]

        if ark_id in catalogo and catalogo[ark_id].get("sha256"):
            checkpoint.proximo_indice += 1
            salvar_checkpoint(checkpoint, caminho_checkpoint)
            continue

        try:
            info = baixar_um(ark_id, pasta_destino, baixar_fct=baixar_fct, timeout_segundos=timeout_segundos)
        except Exception as erro:
            # Erro de infraestrutura de 1 item (navegador travou, download
            # não completou, rede caiu no meio) -- não interrompe o lote;
            # o item fica de fora do catálogo, retomável depois. Exceções
            # que NÃO herdam de Exception (ex.: KeyboardInterrupt) não são
            # capturadas aqui de propósito -- devem propagar de verdade.
            print(f"Falha ao baixar {ark_id}: {erro!r}")
            checkpoint.falhas += 1
            checkpoint.proximo_indice += 1
            salvar_checkpoint(checkpoint, caminho_checkpoint)
            if progresso_fct is not None:
                progresso_fct(checkpoint)
            continue

        catalogo[ark_id] = info
        salvar_json_atomico(catalogo, caminho_catalogo)
        checkpoint.baixados += 1
        checkpoint.proximo_indice += 1
        salvar_checkpoint(checkpoint, caminho_checkpoint)
        if progresso_fct is not None:
            progresso_fct(checkpoint)

    checkpoint.concluido = True
    salvar_checkpoint(checkpoint, caminho_checkpoint)
    return checkpoint
