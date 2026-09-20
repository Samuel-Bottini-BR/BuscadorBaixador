# -*- coding: utf-8 -*-
# tests/test_jobs_motor.py
import json as json_mod
import os
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

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

    # o fallback perde a garantia de "sobreviver ao fechamento da sessao": tem que avisar
    with pytest.warns(RuntimeWarning, match="desacoplar"):
        processo = jobs_motor._lancar_destacado(["qualquer"])

    assert processo.pid == 4242
    assert len(chamadas) == 2
    assert chamadas[0] & subprocess.CREATE_BREAKAWAY_FROM_JOB
    assert not chamadas[1] & subprocess.CREATE_BREAKAWAY_FROM_JOB
    assert chamadas[1] & subprocess.DETACHED_PROCESS


def test_lancar_destacado_nao_avisa_nada_quando_o_breakaway_e_aceito(monkeypatch, recwarn):
    chamadas = []

    class ProcessoFalso:
        pid = 4242

    def popen_falso(comando, creationflags=0, **kwargs):
        chamadas.append(creationflags)
        return ProcessoFalso()

    monkeypatch.setattr(subprocess, "Popen", popen_falso)

    processo = jobs_motor._lancar_destacado(["qualquer"])

    assert processo.pid == 4242
    assert len(chamadas) == 1  # aceitou de primeira, sem fallback
    assert len(recwarn) == 0  # e sem nenhum aviso


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


def test_pid_esta_vivo_na_duvida_diz_que_esta_vivo_quando_o_tasklist_nao_abre(monkeypatch):
    # falha segura: se nao da pra perguntar ao Windows, dar o job por MORTO seria
    # perigoso (o job vira 'interrompido', o 'parar' vira no-op e o 'retomar'
    # lanca um SEGUNDO executor no mesmo checkpoint); dar por vivo so adia a
    # decisao -- o 'parar' resolve depois pela prova de identidade
    def run_que_nao_acha_o_tasklist(*args, **kwargs):
        raise FileNotFoundError("tasklist")
    monkeypatch.setattr(jobs_motor.subprocess, "run", run_que_nao_acha_o_tasklist)

    assert jobs_motor.pid_esta_vivo(1234) is True


def test_pid_esta_vivo_na_duvida_diz_que_esta_vivo_quando_o_tasklist_estoura_o_tempo(monkeypatch):
    def run_que_estoura_o_tempo(*args, **kwargs):
        raise subprocess.TimeoutExpired("tasklist", 15)
    monkeypatch.setattr(jobs_motor.subprocess, "run", run_que_estoura_o_tempo)

    assert jobs_motor.pid_esta_vivo(1234) is True


def test_pid_esta_vivo_na_duvida_diz_que_esta_vivo_quando_o_tasklist_sai_com_erro(monkeypatch):
    class ResultadoComErro:
        returncode = 1
        stdout = b""
        stderr = b"ERRO: algo deu errado"
    monkeypatch.setattr(jobs_motor.subprocess, "run", lambda *args, **kwargs: ResultadoComErro())

    assert jobs_motor.pid_esta_vivo(1234) is True


def test_pid_esta_vivo_aguenta_bytes_que_o_cp1252_nao_decodifica(monkeypatch):
    # \x81 e um byte que o cp1252 nao define: decodificar com ele (text=True) daria
    # UnicodeDecodeError -- e o console do Windows pode usar outra codepage (ex.: cp850).
    # O resultado segue a regra de sempre: o numero do PID aparece no texto?
    class ResultadoComPid:
        returncode = 0
        stdout = b"python.exe                   1234 Console                    1     45.000 K \x81\r\n"
        stderr = b""
    monkeypatch.setattr(jobs_motor.subprocess, "run", lambda *args, **kwargs: ResultadoComPid())
    assert jobs_motor.pid_esta_vivo(1234) is True

    class ResultadoSemPid:
        returncode = 0
        stdout = b"INFORMA\x80\x81ES: nenhuma tarefa em execu\x81\x82o correspondente aos crit\x82rios\r\n"
        stderr = b""
    monkeypatch.setattr(jobs_motor.subprocess, "run", lambda *args, **kwargs: ResultadoSemPid())
    assert jobs_motor.pid_esta_vivo(1234) is False


def test_pid_esta_vivo_passa_timeout_e_nao_abre_janela_ao_chamar_o_tasklist(monkeypatch):
    class ResultadoSemPid:
        returncode = 0
        stdout = b""
        stderr = b""
    argumentos_recebidos = {}

    def run_falso(*args, **kwargs):
        argumentos_recebidos.update(kwargs)
        return ResultadoSemPid()
    monkeypatch.setattr(jobs_motor.subprocess, "run", run_falso)

    jobs_motor.pid_esta_vivo(1234)

    assert argumentos_recebidos["timeout"] == jobs_motor.TIMEOUT_TASKLIST_SEGUNDOS  # sem limite, um tasklist travado congelaria o status
    assert argumentos_recebidos["creationflags"] & subprocess.CREATE_NO_WINDOW  # sem piscar janela de terminal
    assert not argumentos_recebidos.get("text")  # bytes puros, decodificados com errors="replace"


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


def test_descrever_progresso_cai_pro_log_quando_o_checkpoint_esta_truncado(tmp_path, monkeypatch):
    # progresso e so cortesia de exibicao: um checkpoint pela metade nao pode derrubar o 'status'
    monkeypatch.setattr(jobs_motor, "SAIDAS", tmp_path / "saidas")
    pasta_checkpoint = tmp_path / "saidas" / "gallica_crawl" / slug_consulta("consulta")
    pasta_checkpoint.mkdir(parents=True)
    (pasta_checkpoint / "checkpoint.json").write_text('{"consulta": ', encoding="utf-8")
    caminho_log = tmp_path / "log.txt"
    caminho_log.write_text("linha do log\n", encoding="utf-8")
    job = JobRegistrado(id="j1", modulo="gallica_crawl", argv=["consulta"], pid=1,
                         estado="rodando", log_path=str(caminho_log))

    assert jobs_motor.descrever_progresso(job) == "log: linha do log"


def test_descrever_progresso_cai_pro_log_quando_o_checkpoint_tem_campo_desconhecido(tmp_path, monkeypatch):
    # checkpoint de outra versao do programa, com um campo que o Checkpoint atual nao conhece
    monkeypatch.setattr(jobs_motor, "SAIDAS", tmp_path / "saidas")
    pasta_checkpoint = tmp_path / "saidas" / "gallica_crawl" / slug_consulta("consulta")
    pasta_checkpoint.mkdir(parents=True)
    (pasta_checkpoint / "checkpoint.json").write_text(json_mod.dumps({
        "consulta": "consulta", "tamanho_pagina": 50, "proximo_start_record": 51,
        "total_registros_api": 200, "itens_gravados": 50, "concluido": False,
        "atualizado_em": "2026-09-17T00:00:00+00:00", "campo_novo": 1,
    }), encoding="utf-8")
    caminho_log = tmp_path / "log.txt"
    caminho_log.write_text("linha do log\n", encoding="utf-8")
    job = JobRegistrado(id="j1", modulo="gallica_crawl", argv=["consulta"], pid=1,
                         estado="rodando", log_path=str(caminho_log))

    assert jobs_motor.descrever_progresso(job) == "log: linha do log"


def test_descrever_progresso_cai_pro_log_quando_lote_tamanho_e_zero(tmp_path, monkeypatch):
    # 'gallica_enriquecer --lote-tamanho 0' deixa esse checkpoint em disco: dividir por zero
    # ao calcular o total de lotes nao pode derrubar o 'status'
    monkeypatch.setattr(jobs_motor, "SAIDAS", tmp_path / "saidas")
    pasta_checkpoint = tmp_path / "saidas" / "gallica_crawl" / "meu-job"
    pasta_checkpoint.mkdir(parents=True)
    (pasta_checkpoint / "checkpoint_enriquecimento.json").write_text(json_mod.dumps({
        "total_itens": 100, "lote_tamanho": 0, "proximo_lote": 1, "atualizado_em": "x",
    }), encoding="utf-8")
    caminho_log = tmp_path / "log.txt"
    caminho_log.write_text("linha do log\n", encoding="utf-8")
    job = JobRegistrado(id="j1", modulo="gallica_enriquecer", argv=["meu-job"], pid=1,
                         estado="rodando", log_path=str(caminho_log))

    assert jobs_motor.descrever_progresso(job) == "log: linha do log"


def test_descrever_progresso_cai_pro_log_quando_o_checkpoint_esta_ilegivel(tmp_path, monkeypatch):
    # no Windows, um arquivo que outro processo esta trocando naquele instante nao abre
    # (PermissionError); o checkpoint aqui esta valido, quem falha e a leitura
    monkeypatch.setattr(jobs_motor, "SAIDAS", tmp_path / "saidas")
    pasta_checkpoint = tmp_path / "saidas" / "gallica_crawl" / slug_consulta("consulta")
    pasta_checkpoint.mkdir(parents=True)
    (pasta_checkpoint / "checkpoint.json").write_text(json_mod.dumps({
        "consulta": "consulta", "tamanho_pagina": 50, "proximo_start_record": 51,
        "total_registros_api": 200, "itens_gravados": 50, "concluido": False,
        "atualizado_em": "2026-09-17T00:00:00+00:00",
    }), encoding="utf-8")
    caminho_log = tmp_path / "log.txt"
    caminho_log.write_text("linha do log\n", encoding="utf-8")
    job = JobRegistrado(id="j1", modulo="gallica_crawl", argv=["consulta"], pid=1,
                         estado="rodando", log_path=str(caminho_log))
    leitura_original = Path.read_text

    def leitura_negada(self, *args, **kwargs):
        if self.name == "checkpoint.json":
            raise PermissionError("negado")
        return leitura_original(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", leitura_negada)

    assert jobs_motor.descrever_progresso(job) == "log: linha do log"


def test_descrever_progresso_diz_que_nao_ha_informacao_quando_o_log_esta_ilegivel(tmp_path, monkeypatch):
    # log_path apontando pra uma pasta: abrir como arquivo dispara OSError
    monkeypatch.setattr(jobs_motor, "SAIDAS", tmp_path / "saidas")
    job = JobRegistrado(id="j1", modulo="cli", argv=[], pid=1, estado="rodando",
                         log_path=str(tmp_path))

    assert jobs_motor.descrever_progresso(job) == "sem informacao de progresso ainda"


def test_descrever_progresso_usa_o_log_quando_o_modulo_e_conhecido_mas_ainda_nao_ha_checkpoint(tmp_path, monkeypatch):
    # e o estado de todo job nos primeiros segundos: o comando ainda nao gravou o checkpoint
    monkeypatch.setattr(jobs_motor, "SAIDAS", tmp_path / "saidas")
    caminho_log = tmp_path / "log.txt"
    caminho_log.write_text("linha do log\n", encoding="utf-8")
    job = JobRegistrado(id="j1", modulo="gallica_crawl", argv=["consulta"], pid=1,
                         estado="rodando", log_path=str(caminho_log))

    assert jobs_motor.descrever_progresso(job) == "log: linha do log"


def _esperar_o_job_terminar(id_job, caminho_registro, segundos=20):
    prazo = time.time() + segundos
    estado = "rodando"
    while time.time() < prazo and estado == "rodando":
        time.sleep(0.3)
        estado = [j for j in carregar_registro(caminho_registro) if j.id == id_job][0].estado
    return estado


def test_retomar_job_inicia_um_job_novo_com_mesmo_modulo_e_argv(tmp_path, monkeypatch):
    caminho_registro = tmp_path / "registro.json"
    monkeypatch.setitem(jobs_motor.MODULOS_PERMITIDOS, "echo_teste", "tests.fixtures.job_fake")
    monkeypatch.setattr(jobs_motor, "PASTA_JOBS", tmp_path / "jobs")
    original = jobs_motor.iniciar_job("echo_teste", ["0"], caminho_registro)
    assert _esperar_o_job_terminar(original.id, caminho_registro) == "concluido"

    retomado = jobs_motor.retomar_job(original.id, caminho_registro)

    assert retomado.id != original.id
    assert retomado.modulo == "echo_teste"
    assert retomado.argv == ["0"]
    _esperar_o_job_terminar(retomado.id, caminho_registro)  # nao deixa executor pra tras


def test_retomar_job_com_id_inexistente_da_erro(tmp_path):
    caminho_registro = tmp_path / "registro.json"
    salvar_registro([], caminho_registro)

    with pytest.raises(ValueError):
        jobs_motor.retomar_job("nao-existe", caminho_registro)


def test_retomar_job_recusa_se_ja_existe_job_identico_rodando(tmp_path):
    caminho_registro = tmp_path / "registro.json"
    base = dict(modulo="cli", argv=["a", "b"], log_path=str(tmp_path / "log.txt"))
    parado = JobRegistrado(id="job-parado", pid=0, estado="parado", **base)
    rodando = JobRegistrado(id="job-rodando", pid=os.getpid(), estado="rodando", **base)
    salvar_registro([parado, rodando], caminho_registro)

    with pytest.raises(RuntimeError):
        jobs_motor.retomar_job("job-parado", caminho_registro)

    assert len(carregar_registro(caminho_registro)) == 2  # nao lancou nada


def test_retomar_job_ignora_job_identico_que_na_verdade_ja_morreu(tmp_path, monkeypatch):
    monkeypatch.setitem(jobs_motor.MODULOS_PERMITIDOS, "echo_teste", "tests.fixtures.job_fake")
    monkeypatch.setattr(jobs_motor, "PASTA_JOBS", tmp_path / "jobs")
    caminho_registro = tmp_path / "registro.json"
    base = dict(modulo="echo_teste", argv=["0"], log_path=str(tmp_path / "log.txt"))
    parado = JobRegistrado(id="job-parado", pid=0, estado="parado", **base)
    fantasma = JobRegistrado(id="job-fantasma", pid=999999, estado="rodando", **base)
    salvar_registro([parado, fantasma], caminho_registro)

    novo = jobs_motor.retomar_job("job-parado", caminho_registro)

    assert novo.id not in ("job-parado", "job-fantasma")
    estados = {job.id: job.estado for job in carregar_registro(caminho_registro)}
    assert estados["job-fantasma"] == "interrompido"
    _esperar_o_job_terminar(novo.id, caminho_registro)  # nao deixa executor pra tras
