# -*- coding: utf-8 -*-
# tests/test_jobs_registro.py
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from buscador.core import jobs_registro
from buscador.core.jobs_registro import (
    JobRegistrado,
    adicionar_job,
    atualizar_job,
    carregar_registro,
    novo_id,
    salvar_registro,
    trava_registro,
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

    # Verifica que não sobrou nenhum arquivo .tmp (nomes agora são por-escritor)
    assert list(tmp_path.glob("*.tmp")) == []


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


def test_varios_processos_atualizando_ao_mesmo_tempo_nao_corrompem_nem_perdem_atualizacoes(tmp_path):
    """Testa concorrência: 3 processos atualizando o mesmo registro em paralelo.

    Cada processo faz 30 atualizações, alterando o PID. No final, todos os
    jobs devem ter pid=30 (nenhuma atualização foi perdida), e não deve
    sobrar nenhum arquivo .tmp nem .lock."""
    caminho = tmp_path / "registro.json"

    # Prepara registro com 3 jobs
    salvar_registro(
        [
            _job_de_teste("j0"),
            _job_de_teste("j1"),
            _job_de_teste("j2"),
        ],
        caminho,
    )

    # Script que roda em cada subprocess: 30 atualizações de PID
    SCRIPT = (
        "import sys\n"
        "from pathlib import Path\n"
        "from buscador.core.jobs_registro import atualizar_job\n"
        "caminho = Path(sys.argv[1])\n"
        "for n in range(1, 31):\n"
        "    atualizar_job(sys.argv[2], caminho, pid=n)\n"
    )

    # Lança 3 processos em paralelo
    processos = []
    for job_id in ["j0", "j1", "j2"]:
        p = subprocess.Popen(
            [sys.executable, "-c", SCRIPT, str(caminho), job_id],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        processos.append(p)

    # Espera todos terminarem
    for p in processos:
        returncode = p.wait()
        assert returncode == 0, f"Subprocess falhou com return code {returncode}"

    # Verifica resultado
    jobs = carregar_registro(caminho)
    assert len(jobs) == 3
    for job in jobs:
        assert job.pid == 30, f"Job {job.id} deveria ter pid=30, mas tem {job.pid}"

    # Verifica que não sobrou .tmp nem .lock
    assert list(tmp_path.glob("*.tmp")) == []
    assert list(tmp_path.glob("*.lock")) == []


def test_trava_velha_e_abandonada_e_ignorada(tmp_path):
    """Testa que uma trava antiga (processo morreu) é removida automaticamente."""
    caminho = tmp_path / "registro.json"
    trava = caminho.with_suffix(caminho.suffix + ".lock")

    # Prepara registro válido
    salvar_registro([_job_de_teste()], caminho)

    # Cria um arquivo .lock antigo (120 segundos atrás)
    antigo = time.time() - 120
    trava.touch()
    import os as _os
    _os.utime(trava, (antigo, antigo))

    # atualizar_job deve funcionar normalmente e remover a trava antiga
    atualizado = atualizar_job("job-teste", caminho, estado="concluido")

    assert atualizado.estado == "concluido"
    assert not trava.exists()


def test_trava_recente_de_outro_processo_estoura_timeout(tmp_path, monkeypatch):
    """Testa que trava recente de outro processo causa TimeoutError."""
    caminho = tmp_path / "registro.json"
    trava = caminho.with_suffix(caminho.suffix + ".lock")

    # Prepara registro válido
    salvar_registro([_job_de_teste()], caminho)

    # Cria um arquivo .lock recente (simula outro processo segurando a trava)
    trava.touch()

    # Reduz timeout pra não ter que esperar 10 segundos
    monkeypatch.setattr(jobs_registro, "TIMEOUT_TRAVA_SEGUNDOS", 0.2)

    # atualizar_job deve falhar com TimeoutError
    with pytest.raises(TimeoutError):
        atualizar_job("job-teste", caminho, estado="concluido")


def test_trava_velha_que_nao_da_pra_remover_estoura_timeout_em_vez_de_girar_pra_sempre(tmp_path, monkeypatch):
    """Trava velha (dono morreu) que o unlink NUNCA consegue apagar -- antivirus
    ou indexador segurando o arquivo, ou o .lock virou uma pasta. O laco tem que
    cair na checagem de timeout (e no sleep); antes, o `continue` pulava as duas
    coisas e o laco girava sem parar, sem nunca levantar TimeoutError."""
    caminho = tmp_path / "registro.json"
    trava = caminho.with_suffix(caminho.suffix + ".lock")
    salvar_registro([_job_de_teste()], caminho)

    # trava com 120 s de idade: bem mais velha que TRAVA_VELHA_SEGUNDOS
    antigo = time.time() - 120
    trava.touch()
    os.utime(trava, (antigo, antigo))

    monkeypatch.setattr(jobs_registro, "TIMEOUT_TRAVA_SEGUNDOS", 0.3)

    chamadas = {"unlink": 0}
    unlink_original = Path.unlink

    def unlink_sempre_negado(self, *args, **kwargs):
        if self.name.endswith(".lock"):
            chamadas["unlink"] += 1
            # Rede de seguranca do teste: sem o conserto o laco gira sem parar,
            # chamando o unlink sem intervalo. Com o conserto, cada volta dorme
            # 0,05 s e o timeout de 0,3 s encerra tudo em poucas voltas.
            assert chamadas["unlink"] < 200, "laco ocupado: unlink chamado sem parar e sem timeout"
            raise PermissionError("Acesso negado")
        return unlink_original(self, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", unlink_sempre_negado)

    with pytest.raises(TimeoutError):
        atualizar_job("job-teste", caminho, estado="concluido")


def test_trava_velha_e_menor_que_o_timeout():
    """Invariante que o laco de trava_registro assume: uma trava abandonada
    tem que ser detectada ANTES de quem espera desistir por timeout. (Efeito
    colateral conhecido: um `with trava_registro()` aninhado espera ~5 s e depois
    remove a trava do proprio chamador -- por isso a regra 'nao aninhe'.)"""
    assert jobs_registro.TRAVA_VELHA_SEGUNDOS < jobs_registro.TIMEOUT_TRAVA_SEGUNDOS


def test_trava_e_liberada_mesmo_quando_ha_erro_dentro(tmp_path):
    """Testa que a trava é liberada mesmo quando ValueError é levantada."""
    caminho = tmp_path / "registro.json"
    trava = caminho.with_suffix(caminho.suffix + ".lock")

    # Prepara registro válido
    salvar_registro([_job_de_teste()], caminho)

    # Tenta atualizar job que não existe (vai levantar ValueError)
    with pytest.raises(ValueError):
        atualizar_job("nao-existe", caminho, estado="concluido")

    # Verifica que a trava foi liberada
    assert not trava.exists()


def test_trava_trata_permission_error_do_windows_como_trava_ocupada(tmp_path, monkeypatch):
    """Testa que PermissionError durante aquisição de trava é tratado como
    'trava ocupada', não como erro fatal.

    Simula o comportamento do Windows: os.open() levanta PermissionError
    quando outro processo tem o arquivo .lock aberto momentaneamente. O código
    deve tratar isso igual a FileExistsError e tentar novamente."""
    caminho = tmp_path / "registro.json"

    # Prepara registro válido
    salvar_registro([_job_de_teste()], caminho)

    # Guarda a função original de os.open
    original_os_open = os.open
    call_count = {"lock": 0}

    def os_open_com_permission_error(*args, **kwargs):
        """Wrapper que levanta PermissionError nas 2 primeiras vezes
        que é chamado com um path terminado em .lock."""
        if len(args) > 0 and str(args[0]).endswith(".lock"):
            call_count["lock"] += 1
            if call_count["lock"] <= 2:
                raise PermissionError("Acesso negado")
        return original_os_open(*args, **kwargs)

    # Substitui os.open globalmente
    monkeypatch.setattr("os.open", os_open_com_permission_error)

    # atualizar_job deve funcionar (vai fazer retry depois do PermissionError)
    atualizado = atualizar_job("job-teste", caminho, estado="concluido")

    assert atualizado.estado == "concluido"
    assert carregar_registro(caminho)[0].estado == "concluido"
    # Verifica que os.open foi chamado pelo menos 3 vezes (.lock)
    # (2 vezes com erro + 1 vez com sucesso)
    assert call_count["lock"] >= 3
