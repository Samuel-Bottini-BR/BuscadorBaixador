# -*- coding: utf-8 -*-
# tests/test_jobs_motor.py
import json as json_mod
import os
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone

import pytest

from buscador.core import jobs_motor
from buscador.core.checkpoint import slug_consulta
from buscador.core.jobs_registro import JobRegistrado, atualizar_job, carregar_registro, salvar_registro


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


def test_pid_esta_vivo_verdadeiro_pro_proprio_processo_do_teste():
    assert jobs_motor.pid_esta_vivo(os.getpid()) is True


def test_pid_esta_vivo_falso_pra_pid_que_nao_existe():
    assert jobs_motor.pid_esta_vivo(999999) is False


def test_pid_esta_vivo_falso_pra_pid_zero():
    # pid 0 e o "System Idle Process" do Windows (o tasklist o lista como vivo);
    # um job recem-lancado fica com pid=0 por alguns milissegundos e o proprio
    # pid_esta_vivo nunca considera pid 0 vivo -- quem trata essa janela de
    # lancamento e o reconciliar_estados (ver os testes de "recem_lancado")
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


def test_reconciliar_nao_marca_interrompido_job_recem_lancado_com_pid_zero(tmp_path):
    caminho_registro = tmp_path / "registro.json"
    job = JobRegistrado(
        id="job-1", modulo="cli", argv=[], pid=0, estado="rodando",
        log_path=str(tmp_path / "log.txt"),
        iniciado_em=datetime.now(timezone.utc).isoformat(),
    )
    salvar_registro([job], caminho_registro)

    jobs = jobs_motor.reconciliar_estados(caminho_registro)

    assert jobs[0].estado == "rodando"


def test_reconciliar_marca_interrompido_job_com_pid_zero_antigo_ou_sem_data(tmp_path):
    caminho_registro = tmp_path / "registro.json"
    antigo = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
    jobs_antes = [
        JobRegistrado(id="velho", modulo="cli", argv=[], pid=0, estado="rodando",
                      log_path=str(tmp_path / "a.txt"), iniciado_em=antigo),
        JobRegistrado(id="sem-data", modulo="cli", argv=[], pid=0, estado="rodando",
                      log_path=str(tmp_path / "b.txt"), iniciado_em=""),
    ]
    salvar_registro(jobs_antes, caminho_registro)

    jobs = jobs_motor.reconciliar_estados(caminho_registro)

    assert [j.estado for j in jobs] == ["interrompido", "interrompido"]


def test_reconciliar_nao_marca_se_o_pid_real_foi_gravado_durante_a_checagem(tmp_path, monkeypatch):
    # o lancador grava o pid real depois do snapshot da reconciliacao;
    # como o pid mudou, o job nao pode ser marcado "interrompido"
    caminho_registro = tmp_path / "registro.json"
    job = JobRegistrado(
        id="job-1", modulo="cli", argv=[], pid=999999, estado="rodando",
        log_path=str(tmp_path / "log.txt"),
    )
    salvar_registro([job], caminho_registro)

    def pid_morto_mas_lancador_grava_o_pid_real(pid):
        atualizar_job("job-1", caminho_registro, pid=os.getpid())
        return False
    monkeypatch.setattr(jobs_motor, "pid_esta_vivo", pid_morto_mas_lancador_grava_o_pid_real)

    jobs = jobs_motor.reconciliar_estados(caminho_registro)

    assert jobs[0].estado == "rodando"
    assert jobs[0].pid == os.getpid()


def test_parar_job_marca_estado_parado_e_mata_a_arvore_inteira(tmp_path, monkeypatch):
    caminho_registro = tmp_path / "registro.json"
    arquivo_pid = tmp_path / "pid_do_comando.txt"
    monkeypatch.setitem(jobs_motor.MODULOS_PERMITIDOS, "espera_teste", "tests.fixtures.job_lento_fake")
    monkeypatch.setattr(jobs_motor, "PASTA_JOBS", tmp_path / "jobs")

    job = jobs_motor.iniciar_job("espera_teste", [str(arquivo_pid)], caminho_registro)
    pid_comando = None
    terminou_bem = False
    try:
        prazo = time.time() + 15
        while time.time() < prazo and not (arquivo_pid.exists() and arquivo_pid.read_text().strip()):
            time.sleep(0.2)
        pid_comando = int(arquivo_pid.read_text().strip())
        assert jobs_motor.pid_esta_vivo(job.pid) is True
        assert jobs_motor.pid_esta_vivo(pid_comando) is True

        parado = jobs_motor.parar_job(job.id, caminho_registro)

        assert parado.estado == "parado"
        assert jobs_motor.pid_esta_vivo(job.pid) is False
        assert jobs_motor.pid_esta_vivo(pid_comando) is False  # o comando real tambem morreu (/T)
        terminou_bem = True
    finally:
        # limpeza, so se o teste falhou no meio (os processos podem ter ficado
        # vivos) e so com PIDs que ESTE teste criou. Se tudo passou, os dois ja
        # estao mortos: matar de novo "pelo PID" poderia atingir outro programa
        # que o Windows tenha acabado de ganhar esse mesmo PID.
        if not terminou_bem:
            for pid in (job.pid, pid_comando):
                if pid:
                    subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True)


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


def test_parar_job_nao_mata_processo_com_jobs_executor_mas_de_outro_job(tmp_path):
    # simula o PID de um executor morto ter sido dado ao executor de OUTRO job
    caminho_registro = tmp_path / "registro.json"
    intruso = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(60)", "buscador.core.jobs_executor", "outro-id"]
    )
    try:
        job = JobRegistrado(
            id="job-1", modulo="cli", argv=[], pid=intruso.pid, estado="rodando",
            log_path=str(tmp_path / "log.txt"),
        )
        salvar_registro([job], caminho_registro)

        parado = jobs_motor.parar_job("job-1", caminho_registro)

        assert parado.estado == "parado"
        assert intruso.poll() is None  # tem "jobs_executor" na linha de comando, mas nao o id deste job
    finally:
        intruso.kill()
        intruso.wait()


def test_parar_job_nao_sobrescreve_estado_final_gravado_durante_a_consulta(tmp_path, monkeypatch):
    caminho_registro = tmp_path / "registro.json"
    job = JobRegistrado(
        id="job-1", modulo="cli", argv=[], pid=999999, estado="rodando",
        log_path=str(tmp_path / "log.txt"),
    )
    salvar_registro([job], caminho_registro)

    def consulta_lenta_em_que_o_executor_termina(job_consultado):
        atualizar_job("job-1", caminho_registro, estado="concluido")
        return False
    monkeypatch.setattr(jobs_motor, "_e_o_executor_do_job", consulta_lenta_em_que_o_executor_termina)

    resultado = jobs_motor.parar_job("job-1", caminho_registro)

    assert resultado.estado == "concluido"
    assert carregar_registro(caminho_registro)[0].estado == "concluido"


def test_parar_job_nao_marca_parado_se_o_taskkill_falha_e_o_processo_continua_vivo(tmp_path, monkeypatch):
    caminho_registro = tmp_path / "registro.json"
    job = JobRegistrado(
        id="job-1", modulo="cli", argv=[], pid=999999, estado="rodando",
        log_path=str(tmp_path / "log.txt"),
    )
    salvar_registro([job], caminho_registro)

    class ResultadoFalso:
        returncode = 1
    monkeypatch.setattr(jobs_motor, "_e_o_executor_do_job", lambda job_consultado: True)
    monkeypatch.setattr(jobs_motor, "pid_esta_vivo", lambda pid: True)
    monkeypatch.setattr(jobs_motor.subprocess, "run", lambda *args, **kwargs: ResultadoFalso())

    with pytest.raises(RuntimeError):
        jobs_motor.parar_job("job-1", caminho_registro)

    assert carregar_registro(caminho_registro)[0].estado == "rodando"


def test_parar_job_nao_mexe_em_nada_se_nao_consegue_confirmar_o_processo(tmp_path, monkeypatch):
    caminho_registro = tmp_path / "registro.json"
    job = JobRegistrado(
        id="job-1", modulo="cli", argv=[], pid=999999, estado="rodando",
        log_path=str(tmp_path / "log.txt"),
    )
    salvar_registro([job], caminho_registro)
    monkeypatch.setattr(jobs_motor, "_linha_de_comando", lambda pid: None)

    with pytest.raises(RuntimeError):
        jobs_motor.parar_job("job-1", caminho_registro)

    assert carregar_registro(caminho_registro)[0].estado == "rodando"


def test_parar_job_recusa_job_que_ainda_esta_sendo_lancado(tmp_path):
    caminho_registro = tmp_path / "registro.json"
    job = JobRegistrado(
        id="job-1", modulo="cli", argv=[], pid=0, estado="rodando",
        log_path=str(tmp_path / "log.txt"),
        iniciado_em=datetime.now(timezone.utc).isoformat(),
    )
    salvar_registro([job], caminho_registro)

    with pytest.raises(RuntimeError):
        jobs_motor.parar_job("job-1", caminho_registro)

    assert carregar_registro(caminho_registro)[0].estado == "rodando"


def test_linha_de_comando_aguenta_acentos_que_o_cp1252_nao_decodifica(monkeypatch):
    # \x81 e um byte que o cp1252 nao define: decodificar com ele (text=True) daria UnicodeDecodeError
    class ResultadoFalso:
        returncode = 0
        stdout = b"C:\\Users\\\x81milie\\python.exe -m buscador.core.jobs_executor job-1 reg.json\r\n"
        stderr = b""
    argumentos_recebidos = {}

    def run_falso(*args, **kwargs):
        argumentos_recebidos.update(kwargs)
        return ResultadoFalso()
    monkeypatch.setattr(jobs_motor.subprocess, "run", run_falso)

    linha = jobs_motor._linha_de_comando(1234)

    assert "jobs_executor" in linha and "job-1" in linha
    assert "timeout" in argumentos_recebidos  # sem limite de tempo, um PowerShell travado congelaria o parar_job


def test_linha_de_comando_devolve_none_quando_a_consulta_falha_ou_estoura_o_tempo(monkeypatch):
    class ResultadoComErro:
        returncode = 1
        stdout = b""
        stderr = b""
    monkeypatch.setattr(jobs_motor.subprocess, "run", lambda *args, **kwargs: ResultadoComErro())
    assert jobs_motor._linha_de_comando(1234) is None

    def run_que_estoura_o_tempo(*args, **kwargs):
        raise subprocess.TimeoutExpired("powershell", 15)
    monkeypatch.setattr(jobs_motor.subprocess, "run", run_que_estoura_o_tempo)
    assert jobs_motor._linha_de_comando(1234) is None


def test_linha_de_comando_devolve_none_se_o_wmi_der_erro_mesmo_com_codigo_zero(monkeypatch):
    # quando o Get-CimInstance falha (WMI fora do ar, acesso negado...), o PowerShell
    # sai com codigo 0, stdout vazio e o erro no stderr. Isso NAO pode virar "o
    # processo nao existe" ('') -- e "nao sei" (None).
    class ResultadoComErroDoWmi:
        returncode = 0
        stdout = b""
        stderr = b"Get-CimInstance : erro do WMI"
    monkeypatch.setattr(jobs_motor.subprocess, "run", lambda *args, **kwargs: ResultadoComErroDoWmi())
    assert jobs_motor._linha_de_comando(1234) is None

    # contraste: a consulta funcionou e nao achou o processo (codigo 0, stdout e stderr vazios)
    class ResultadoProcessoInexistente:
        returncode = 0
        stdout = b""
        stderr = b""
    monkeypatch.setattr(jobs_motor.subprocess, "run", lambda *args, **kwargs: ResultadoProcessoInexistente())
    assert jobs_motor._linha_de_comando(1234) == ""


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


def test_descrever_progresso_gallica_crawl_respeita_a_opcao_job(tmp_path, monkeypatch):
    # com --job, a pasta do checkpoint tem o nome escolhido, nao o derivado da consulta
    monkeypatch.setattr(jobs_motor, "SAIDAS", tmp_path / "saidas")
    pasta_checkpoint = tmp_path / "saidas" / "gallica_crawl" / "meu-job"
    pasta_checkpoint.mkdir(parents=True)
    (pasta_checkpoint / "checkpoint.json").write_text(json_mod.dumps({
        "consulta": "qualquer", "tamanho_pagina": 50, "proximo_start_record": 51,
        "total_registros_api": 200, "itens_gravados": 50, "concluido": False,
        "atualizado_em": "2026-09-17T00:00:00+00:00",
    }), encoding="utf-8")
    for argv in (["qualquer", "--job", "meu-job"], ["qualquer", "--job=meu-job"]):
        job = JobRegistrado(id="j1", modulo="gallica_crawl", argv=argv, pid=1,
                             estado="rodando", log_path=str(tmp_path / "log.txt"))

        progresso = jobs_motor.descrever_progresso(job)

        assert "50/200" in progresso
        assert "25.0%" in progresso


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
