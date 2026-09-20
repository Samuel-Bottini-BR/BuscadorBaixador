# -*- coding: utf-8 -*-
# tests/test_jobs_cli.py
import io
import os
import sys
import time

from buscador import jobs_cli
from buscador.core import jobs_motor
from buscador.core.jobs_registro import JobRegistrado, carregar_registro, salvar_registro


def test_status_sem_nenhum_job_mostra_mensagem_amigavel(tmp_path, capsys):
    caminho_registro = tmp_path / "registro.json"

    codigo = jobs_cli.main(["--registro", str(caminho_registro), "status"])

    assert codigo == 0
    assert "Nenhum job" in capsys.readouterr().out


def test_iniciar_e_status_de_ponta_a_ponta(tmp_path, monkeypatch, capsys):
    caminho_registro = tmp_path / "registro.json"
    monkeypatch.setitem(jobs_motor.MODULOS_PERMITIDOS, "cli", "tests.fixtures.job_fake")
    monkeypatch.setattr(jobs_motor, "PASTA_JOBS", tmp_path / "jobs")

    codigo = jobs_cli.main(["--registro", str(caminho_registro), "iniciar", "cli", "0"])
    assert codigo == 0
    assert "iniciado" in capsys.readouterr().out

    prazo = time.time() + 15
    saida_status = ""
    while time.time() < prazo:
        jobs_cli.main(["--registro", str(caminho_registro), "status"])
        saida_status = capsys.readouterr().out
        if "concluido" in saida_status:
            break
        time.sleep(0.3)

    assert "concluido" in saida_status


def test_parar_via_cli(tmp_path, capsys):
    caminho_registro = tmp_path / "registro.json"
    job = JobRegistrado(id="j1", modulo="cli", argv=[], pid=999999, estado="rodando",
                         log_path=str(tmp_path / "log.txt"))
    salvar_registro([job], caminho_registro)

    codigo = jobs_cli.main(["--registro", str(caminho_registro), "parar", "j1"])

    assert codigo == 0
    assert carregar_registro(caminho_registro)[0].estado == "parado"


def test_parar_e_retomar_com_id_inexistente_mostram_mensagem_amigavel(tmp_path, capsys):
    caminho_registro = tmp_path / "registro.json"
    salvar_registro([], caminho_registro)

    codigo_parar = jobs_cli.main(["--registro", str(caminho_registro), "parar", "nao-existe"])
    codigo_retomar = jobs_cli.main(["--registro", str(caminho_registro), "retomar", "nao-existe"])

    saida = capsys.readouterr().out
    assert codigo_parar == 1 and codigo_retomar == 1
    assert "Nao deu para parar" in saida
    assert "Nao deu para retomar" in saida


def test_iniciar_repassa_flags_do_comando_de_verdade_sem_tentar_interpreta_las(tmp_path, monkeypatch):
    # o ponto delicado do argparse.REMAINDER: o PRIMEIRO argumento repassado ja e uma opcao
    caminho_registro = tmp_path / "registro.json"
    monkeypatch.setitem(jobs_motor.MODULOS_PERMITIDOS, "cli", "tests.fixtures.job_fake")
    monkeypatch.setattr(jobs_motor, "PASTA_JOBS", tmp_path / "jobs")

    codigo = jobs_cli.main(["--registro", str(caminho_registro), "iniciar", "cli", "--adapter", "phpbb", "0"])

    assert codigo == 0
    assert carregar_registro(caminho_registro)[0].argv == ["--adapter", "phpbb", "0"]
    # espera o executor terminar pra nao deixar processo pra tras (o job_fake tenta
    # fazer int("--adapter") e levanta ValueError, entao o job termina em erro; aqui
    # isso nao importa)
    prazo = time.time() + 20
    while time.time() < prazo and carregar_registro(caminho_registro)[0].estado == "rodando":
        time.sleep(0.3)


def test_iniciar_mostra_mensagem_amigavel_se_o_lancamento_falhar(tmp_path, monkeypatch, capsys):
    caminho_registro = tmp_path / "registro.json"
    monkeypatch.setattr(jobs_motor, "PASTA_JOBS", tmp_path / "jobs")

    def lancar_que_falha(comando):
        raise OSError("nao consegui lancar")
    monkeypatch.setattr(jobs_motor, "_lancar_destacado", lancar_que_falha)

    codigo = jobs_cli.main(["--registro", str(caminho_registro), "iniciar", "cli", "0"])

    assert codigo == 1
    assert "Nao deu para iniciar" in capsys.readouterr().out


def test_retomar_mostra_mensagem_amigavel_se_o_lancamento_falhar(tmp_path, monkeypatch, capsys):
    caminho_registro = tmp_path / "registro.json"
    monkeypatch.setattr(jobs_motor, "PASTA_JOBS", tmp_path / "jobs")
    job_antigo = JobRegistrado(id="j1", modulo="cli", argv=["0"], pid=0, estado="concluido",
                                log_path=str(tmp_path / "log.txt"))
    salvar_registro([job_antigo], caminho_registro)

    def lancar_que_falha(comando):
        raise OSError("nao consegui lancar")
    monkeypatch.setattr(jobs_motor, "_lancar_destacado", lancar_que_falha)

    codigo = jobs_cli.main(["--registro", str(caminho_registro), "retomar", "j1"])

    assert codigo == 1
    assert "Nao deu para retomar" in capsys.readouterr().out
    assert [j.estado for j in carregar_registro(caminho_registro)] == ["concluido", "erro"]


def test_status_nao_quebra_com_caracteres_que_o_console_nao_suporta(tmp_path, monkeypatch):
    # o log de um job pode ter qualquer texto; o console/pipe do Windows em cp1252 nao
    # consegue imprimir tudo, e isso nao pode derrubar o status
    caminho_registro = tmp_path / "registro.json"
    caminho_log = tmp_path / "log.txt"
    caminho_log.write_text("progresso łódź\n", encoding="utf-8")
    job = JobRegistrado(id="j1", modulo="cli", argv=[], pid=os.getpid(), estado="rodando",
                         log_path=str(caminho_log))
    salvar_registro([job], caminho_registro)
    monkeypatch.setattr(sys, "stdout", io.TextIOWrapper(io.BytesIO(), encoding="cp1252"))

    codigo = jobs_cli.main(["--registro", str(caminho_registro), "status"])

    assert codigo == 0
