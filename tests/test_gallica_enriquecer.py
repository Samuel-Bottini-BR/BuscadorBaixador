# -*- coding: utf-8 -*-
from buscador import gallica_enriquecer
from buscador.core.coleta_csv import EscritorCsvIncremental
from buscador.core.enriquecimento_lote import CheckpointEnriquecimento


def _criar_csv_de_entrada(diretorio_job, quantidade=3):
    diretorio_job.mkdir(parents=True)
    from buscador.adapters.base import Item
    itens = [Item(titulo_original=f"Livro {i}", link=f"https://exemplo.com/{i}",
                   extra={"idioma_origem": "fr", "tipo_doc": "monographie"})
             for i in range(quantidade)]
    with EscritorCsvIncremental(diretorio_job / "itens.csv") as escritor:
        escritor.escrever_pagina(itens)


def test_main_falha_com_mensagem_amigavel_se_job_nao_existe(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(gallica_enriquecer, "DIRETORIO_COLETAS", tmp_path)

    codigo = gallica_enriquecer.main(["job-inexistente"])

    assert codigo == 1
    saida = capsys.readouterr().out
    assert "Não deu para continuar" in saida
    assert "gallica_crawl" in saida


def test_main_carrega_o_csv_e_chama_enriquecer_em_lotes(tmp_path, monkeypatch):
    monkeypatch.setattr(gallica_enriquecer, "DIRETORIO_COLETAS", tmp_path)
    _criar_csv_de_entrada(tmp_path / "meu-job", quantidade=3)

    chamadas = []

    def fake_enriquecer_em_lotes(itens, diretorio_job, lote_tamanho, workers, progresso_fct=None):
        chamadas.append(dict(itens=itens, diretorio_job=diretorio_job,
                              lote_tamanho=lote_tamanho, workers=workers))
        return CheckpointEnriquecimento(total_itens=len(itens), lote_tamanho=lote_tamanho, proximo_lote=1)

    monkeypatch.setattr(gallica_enriquecer, "enriquecer_em_lotes", fake_enriquecer_em_lotes)

    codigo = gallica_enriquecer.main(["meu-job"])

    assert codigo == 0
    assert len(chamadas[0]["itens"]) == 3
    assert chamadas[0]["diretorio_job"] == tmp_path / "meu-job"
    assert chamadas[0]["lote_tamanho"] == gallica_enriquecer.LOTE_TAMANHO_PADRAO
    assert chamadas[0]["workers"] == gallica_enriquecer.WORKERS_PADRAO


def test_main_aceita_lote_tamanho_e_workers_customizados(tmp_path, monkeypatch):
    monkeypatch.setattr(gallica_enriquecer, "DIRETORIO_COLETAS", tmp_path)
    _criar_csv_de_entrada(tmp_path / "meu-job", quantidade=3)

    chamadas = []

    def fake_enriquecer_em_lotes(itens, diretorio_job, lote_tamanho, workers, progresso_fct=None):
        chamadas.append(dict(lote_tamanho=lote_tamanho, workers=workers))
        return CheckpointEnriquecimento(total_itens=len(itens), lote_tamanho=lote_tamanho, proximo_lote=1)

    monkeypatch.setattr(gallica_enriquecer, "enriquecer_em_lotes", fake_enriquecer_em_lotes)

    gallica_enriquecer.main(["meu-job", "--lote-tamanho", "500", "--workers", "10"])

    assert chamadas[0]["lote_tamanho"] == 500
    assert chamadas[0]["workers"] == 10
