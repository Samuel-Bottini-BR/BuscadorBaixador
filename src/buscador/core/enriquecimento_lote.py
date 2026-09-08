# -*- coding: utf-8 -*-
"""Motor da Etapa 2: verifica link + traduz cada item coletado pela Etapa 1,
em paralelo (como o verificar_links.py ja faz na raiz do projeto), em
lotes. Cada lote confirmado vira uma planilha .xlsx (revisao humana, com
cor/dropdown -- ver core/planilha.py) e entra num CSV acumulado (dado leve,
pra importar em outro programa depois). Retomavel: um lote ja processado
(segundo o checkpoint) e pulado."""
import concurrent.futures as cf
import csv
import json
import math
import os
from dataclasses import asdict, dataclass

from buscador.core.enriquecimento import enriquecer_item
from buscador.core.planilha import COLUNAS as COLUNAS_PLANILHA
from buscador.core.planilha import gerar_planilha
from buscador.core.traducao import traduzir

LOTE_TAMANHO_PADRAO = 20_000
WORKERS_PADRAO = 40

# So os idiomas que os adaptadores realmente produzem (ver traducao.py).
# Aquecer cada um em serie, ANTES de abrir o pool de threads, evita que
# varias threads tentem instalar o mesmo pacote do argostranslate ao mesmo
# tempo -- o cache de pacotes instalados desse modulo nao tem lock.
_IDIOMA_CAMPO_EXTRA = "idioma_origem"


@dataclass
class CheckpointEnriquecimento:
    total_itens: int
    lote_tamanho: int
    proximo_lote: int = 0
    atualizado_em: str = ""


def carregar_ou_criar_checkpoint(caminho_json, total_itens, lote_tamanho) -> CheckpointEnriquecimento:
    if caminho_json.exists():
        dados = json.loads(caminho_json.read_text(encoding="utf-8"))
        return CheckpointEnriquecimento(**dados)
    checkpoint = CheckpointEnriquecimento(total_itens=total_itens, lote_tamanho=lote_tamanho)
    salvar_checkpoint(checkpoint, caminho_json)
    return checkpoint


def salvar_checkpoint(checkpoint: CheckpointEnriquecimento, caminho_json) -> None:
    caminho_json.parent.mkdir(parents=True, exist_ok=True)
    caminho_tmp = caminho_json.with_suffix(caminho_json.suffix + ".tmp")
    caminho_tmp.write_text(json.dumps(asdict(checkpoint), ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(caminho_tmp, caminho_json)


def enriquecer_em_lotes(itens, diretorio_job, lote_tamanho=LOTE_TAMANHO_PADRAO,
                         workers=WORKERS_PADRAO, progresso_fct=None):
    diretorio_job.mkdir(parents=True, exist_ok=True)
    caminho_checkpoint = diretorio_job / "checkpoint_enriquecimento.json"
    caminho_csv_enriquecido = diretorio_job / "itens_enriquecidos.csv"
    checkpoint = carregar_ou_criar_checkpoint(caminho_checkpoint, len(itens), lote_tamanho)
    total_lotes = math.ceil(len(itens) / lote_tamanho) if itens else 0

    _pre_aquecer_traducao(itens)

    with _EscritorCsvEnriquecido(caminho_csv_enriquecido) as escritor_csv:
        for indice in range(checkpoint.proximo_lote, total_lotes):
            lote = itens[indice * lote_tamanho: (indice + 1) * lote_tamanho]
            caminho_planilha = diretorio_job / f"planilha_lote_{indice + 1:04d}.xlsx"

            with cf.ThreadPoolExecutor(max_workers=workers) as executor:
                lote_enriquecido = list(executor.map(enriquecer_item, lote))

            gerar_planilha(lote_enriquecido, caminho_planilha)
            escritor_csv.escrever_itens(lote_enriquecido)
            checkpoint.proximo_lote = indice + 1
            salvar_checkpoint(checkpoint, caminho_checkpoint)
            if progresso_fct is not None:
                progresso_fct(checkpoint, total_lotes)

    return checkpoint


def _pre_aquecer_traducao(itens):
    idiomas = {item.extra.get(_IDIOMA_CAMPO_EXTRA) for item in itens if item.extra.get(_IDIOMA_CAMPO_EXTRA)}
    for idioma in idiomas:
        traduzir("teste", idioma_origem=idioma)


class _EscritorCsvEnriquecido:
    """Grava o resultado final (ja verificado e traduzido) em CSV, lote por
    lote -- as mesmas colunas do .xlsx, sem cor/dropdown, pensado pra
    importar em outro programa (planilha, banco de dados, etc.)."""

    def __init__(self, caminho_csv):
        arquivo_novo = not caminho_csv.exists() or caminho_csv.stat().st_size == 0
        caminho_csv.parent.mkdir(parents=True, exist_ok=True)
        self._arquivo = open(caminho_csv, "a", newline="", encoding="utf-8")
        self._escritor = csv.DictWriter(self._arquivo, fieldnames=COLUNAS_PLANILHA)
        if arquivo_novo:
            self._escritor.writeheader()
            self._sincronizar()

    def escrever_itens(self, itens):
        for item in itens:
            self._escritor.writerow({coluna: getattr(item, coluna) for coluna in COLUNAS_PLANILHA})
        self._sincronizar()

    def _sincronizar(self):
        self._arquivo.flush()
        os.fsync(self._arquivo.fileno())

    def fechar(self):
        self._arquivo.close()

    def __enter__(self):
        return self

    def __exit__(self, tipo_erro, erro, traceback):
        self.fechar()
