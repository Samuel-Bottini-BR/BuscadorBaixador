# -*- coding: utf-8 -*-
from buscador import gallica_crawl
from buscador.core.checkpoint import ConsultaDivergenteError, slug_consulta

CONSULTA = 'dc.type all "monographie"'


class _CheckpointFalso:
    itens_gravados = 42
    total_registros_api = None


def _fake_coletar_capturando(chamadas):
    def coletar(consulta, diretorio_job, tamanho_pagina, max_registros_alvo,
                cooldown_429_segundos, progresso_fct=None):
        chamadas.append(dict(
            consulta=consulta, diretorio_job=diretorio_job, tamanho_pagina=tamanho_pagina,
            max_registros_alvo=max_registros_alvo, cooldown_429_segundos=cooldown_429_segundos,
            progresso_fct=progresso_fct,
        ))
        return _CheckpointFalso()
    return coletar


def test_main_deriva_a_pasta_do_job_a_partir_da_consulta(tmp_path, monkeypatch):
    monkeypatch.setattr(gallica_crawl, "DIRETORIO_COLETAS", tmp_path)
    chamadas = []
    monkeypatch.setattr(gallica_crawl, "coletar", _fake_coletar_capturando(chamadas))

    codigo = gallica_crawl.main([CONSULTA])

    assert codigo == 0
    assert chamadas[0]["diretorio_job"] == tmp_path / slug_consulta(CONSULTA)
    assert chamadas[0]["max_registros_alvo"] == 10_000_000
    assert chamadas[0]["cooldown_429_segundos"] == gallica_crawl.COOLDOWN_429_PADRAO_SEGUNDOS
    assert chamadas[0]["progresso_fct"] is not None


def test_job_explicito_usa_esse_nome_de_pasta(tmp_path, monkeypatch):
    monkeypatch.setattr(gallica_crawl, "DIRETORIO_COLETAS", tmp_path)
    chamadas = []
    monkeypatch.setattr(gallica_crawl, "coletar", _fake_coletar_capturando(chamadas))

    gallica_crawl.main([CONSULTA, "--job", "meu-job"])

    assert chamadas[0]["diretorio_job"] == tmp_path / "meu-job"


def test_cooldown_em_minutos_e_convertido_para_segundos(tmp_path, monkeypatch):
    monkeypatch.setattr(gallica_crawl, "DIRETORIO_COLETAS", tmp_path)
    chamadas = []
    monkeypatch.setattr(gallica_crawl, "coletar", _fake_coletar_capturando(chamadas))

    gallica_crawl.main([CONSULTA, "--cooldown-429-minutos", "5"])

    assert chamadas[0]["cooldown_429_segundos"] == 300


def test_consulta_divergente_mostra_mensagem_amigavel_e_retorna_1(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(gallica_crawl, "DIRETORIO_COLETAS", tmp_path)

    def coletar_que_falha(*args, **kwargs):
        raise ConsultaDivergenteError("consulta diferente da salva")
    monkeypatch.setattr(gallica_crawl, "coletar", coletar_que_falha)

    codigo = gallica_crawl.main([CONSULTA])

    assert codigo == 1
    assert "consulta diferente da salva" in capsys.readouterr().out


def test_reiniciar_sem_confirmacao_cancela_e_nao_apaga(tmp_path, monkeypatch):
    monkeypatch.setattr(gallica_crawl, "DIRETORIO_COLETAS", tmp_path)
    diretorio_job = tmp_path / slug_consulta(CONSULTA)
    diretorio_job.mkdir(parents=True)
    (diretorio_job / "checkpoint.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr("builtins.input", lambda _: "nao")
    chamadas = []
    monkeypatch.setattr(gallica_crawl, "coletar", _fake_coletar_capturando(chamadas))

    codigo = gallica_crawl.main([CONSULTA, "--reiniciar"])

    assert codigo == 1
    assert chamadas == []
    assert diretorio_job.exists()


def test_reiniciar_com_confirmacao_apaga_e_continua(tmp_path, monkeypatch):
    monkeypatch.setattr(gallica_crawl, "DIRETORIO_COLETAS", tmp_path)
    diretorio_job = tmp_path / slug_consulta(CONSULTA)
    diretorio_job.mkdir(parents=True)
    (diretorio_job / "checkpoint.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr("builtins.input", lambda _: "sim")
    chamadas = []
    monkeypatch.setattr(gallica_crawl, "coletar", _fake_coletar_capturando(chamadas))

    codigo = gallica_crawl.main([CONSULTA, "--reiniciar"])

    assert codigo == 0
    assert len(chamadas) == 1
    assert not (diretorio_job / "checkpoint.json").exists()


def test_reiniciar_quando_pasta_nao_existe_nao_pede_confirmacao(tmp_path, monkeypatch):
    monkeypatch.setattr(gallica_crawl, "DIRETORIO_COLETAS", tmp_path)

    def input_que_nao_deveria_ser_chamado(_):
        raise AssertionError("nao deveria pedir confirmacao se a pasta nem existe")
    monkeypatch.setattr("builtins.input", input_que_nao_deveria_ser_chamado)
    chamadas = []
    monkeypatch.setattr(gallica_crawl, "coletar", _fake_coletar_capturando(chamadas))

    codigo = gallica_crawl.main([CONSULTA, "--reiniciar"])

    assert codigo == 0
    assert len(chamadas) == 1
