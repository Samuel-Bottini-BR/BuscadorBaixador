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
