# -*- coding: utf-8 -*-
# tests/test_jobs_motor.py
import subprocess
import time

import pytest

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


def test_iniciar_job_marca_erro_e_repropaga_se_o_lancamento_falhar(tmp_path, monkeypatch):
    caminho_registro = tmp_path / "registro.json"
    monkeypatch.setitem(jobs_motor.MODULOS_PERMITIDOS, "echo_teste", "tests.fixtures.job_fake")
    monkeypatch.setattr(jobs_motor, "PASTA_JOBS", tmp_path / "jobs")

    def lancar_que_falha(comando):
        raise OSError("nao consegui lancar")
    monkeypatch.setattr(jobs_motor, "_lancar_destacado", lancar_que_falha)

    with pytest.raises(OSError):
        jobs_motor.iniciar_job("echo_teste", [], caminho_registro)

    jobs = carregar_registro(caminho_registro)
    assert len(jobs) == 1
    assert jobs[0].estado == "erro"


def test_executar_job_forca_saida_sem_buffer_e_em_utf8(tmp_path, monkeypatch):
    caminho_registro = tmp_path / "registro.json"
    job = JobRegistrado(
        id="job-1", modulo="cli", argv=[], pid=0, estado="rodando",
        log_path=str(tmp_path / "log.txt"), alvo="tests.fixtures.job_fake",
    )
    salvar_registro([job], caminho_registro)
    capturado = {}

    class ResultadoFalso:
        returncode = 0

    def run_falso(comando, **kwargs):
        capturado.update(kwargs)
        return ResultadoFalso()
    monkeypatch.setattr(jobs_motor.subprocess, "run", run_falso)

    jobs_motor.executar_job("job-1", caminho_registro)

    assert capturado["env"]["PYTHONUNBUFFERED"] == "1"
    assert capturado["env"]["PYTHONIOENCODING"] == "utf-8"
