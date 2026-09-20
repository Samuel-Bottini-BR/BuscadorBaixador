# -*- coding: utf-8 -*-
# tests/test_jobs_executor.py
from buscador.core import jobs_executor
from buscador.core.jobs_registro import JobRegistrado, carregar_registro, salvar_registro


def _job_de_teste(caminho_log, id="job-1"):
    return JobRegistrado(
        id=id, modulo="cli", argv=[], pid=1234, estado="rodando", log_path=str(caminho_log),
    )


def test_main_devolve_0_e_repassa_id_e_registro_quando_o_job_termina_bem(tmp_path, monkeypatch):
    caminho_registro = tmp_path / "registro.json"
    chamadas = []
    monkeypatch.setattr(
        jobs_executor, "executar_job", lambda id_job, registro: chamadas.append((id_job, registro))
    )

    codigo = jobs_executor.main(["job-1", str(caminho_registro)])

    assert codigo == 0
    assert chamadas == [("job-1", caminho_registro)]


def test_main_grava_o_traceback_no_log_e_marca_erro_quando_o_executar_job_levanta(tmp_path, monkeypatch):
    # o caso mais plausivel: a coleta de horas terminou bem e e o atualizar_job FINAL
    # que estoura (trava do registro). O executor roda sem terminal (stderr vai pro
    # nada), entao sem isso o job morria em silencio e ficava "interrompido".
    caminho_registro = tmp_path / "registro.json"
    caminho_log = tmp_path / "log.txt"
    caminho_log.write_text("saida do comando que terminou bem\n", encoding="utf-8")
    salvar_registro([_job_de_teste(caminho_log)], caminho_registro)

    def executar_job_que_estoura(id_job, registro):
        raise TimeoutError("nao consegui a trava do registro")
    monkeypatch.setattr(jobs_executor, "executar_job", executar_job_que_estoura)

    codigo = jobs_executor.main(["job-1", str(caminho_registro)])

    assert codigo == 1
    log = caminho_log.read_text(encoding="utf-8")
    assert "saida do comando que terminou bem" in log  # nao apagou o que o comando ja tinha escrito
    assert "Traceback" in log
    assert "nao consegui a trava do registro" in log
    assert carregar_registro(caminho_registro)[0].estado == "erro"


def test_main_recria_a_pasta_do_log_apagada_para_deixar_o_traceback(tmp_path, monkeypatch):
    # "pasta de log apagada" e uma das causas de o executar_job estourar (o open do log falha)
    caminho_registro = tmp_path / "registro.json"
    caminho_log = tmp_path / "pasta-apagada" / "log.txt"
    salvar_registro([_job_de_teste(caminho_log)], caminho_registro)

    def executar_job_que_estoura(id_job, registro):
        raise FileNotFoundError("a pasta do log sumiu")
    monkeypatch.setattr(jobs_executor, "executar_job", executar_job_que_estoura)

    codigo = jobs_executor.main(["job-1", str(caminho_registro)])

    assert codigo == 1
    assert "a pasta do log sumiu" in caminho_log.read_text(encoding="utf-8")
    assert carregar_registro(caminho_registro)[0].estado == "erro"


def test_main_engole_e_devolve_1_se_nem_o_registro_da_pra_ler(tmp_path, monkeypatch):
    # sem o registro nao ha como achar o log nem marcar o estado: o executor nao pode
    # levantar uma SEGUNDA excecao por cima da primeira
    caminho_registro = tmp_path / "registro.json"
    caminho_registro.write_text("{", encoding="utf-8")

    def executar_job_que_estoura(id_job, registro):
        raise RuntimeError("falhou")
    monkeypatch.setattr(jobs_executor, "executar_job", executar_job_que_estoura)

    assert jobs_executor.main(["job-1", str(caminho_registro)]) == 1


def test_main_devolve_1_se_o_id_nao_existe_no_registro(tmp_path):
    # sem monkeypatch: o executar_job de verdade levanta ValueError (job nao encontrado)
    caminho_registro = tmp_path / "registro.json"
    salvar_registro([], caminho_registro)

    assert jobs_executor.main(["nao-existe", str(caminho_registro)]) == 1
