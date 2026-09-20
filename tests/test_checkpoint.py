# -*- coding: utf-8 -*-
import json
import time

import pytest

from buscador.core import checkpoint as modulo
from buscador.core.checkpoint import (
    Checkpoint,
    ConsultaDivergenteError,
    carregar_ou_criar,
    salvar,
    slug_consulta,
)


def test_cria_checkpoint_novo_quando_arquivo_nao_existe(tmp_path):
    caminho = tmp_path / "checkpoint.json"
    checkpoint = carregar_ou_criar(caminho, 'dc.type all "monographie"', tamanho_pagina=50)

    assert checkpoint.consulta == 'dc.type all "monographie"'
    assert checkpoint.tamanho_pagina == 50
    assert checkpoint.proximo_start_record == 1
    assert checkpoint.concluido is False
    assert caminho.exists()  # ja grava no disco na primeira vez


def test_carrega_checkpoint_existente_do_disco(tmp_path):
    caminho = tmp_path / "checkpoint.json"
    original = carregar_ou_criar(caminho, "minha consulta", tamanho_pagina=50)
    original.proximo_start_record = 251
    original.itens_gravados = 250
    salvar(original, caminho)

    retomado = carregar_ou_criar(caminho, "minha consulta", tamanho_pagina=50)

    assert retomado.proximo_start_record == 251
    assert retomado.itens_gravados == 250


def test_consulta_diferente_gera_erro_em_vez_de_retomar_errado(tmp_path):
    caminho = tmp_path / "checkpoint.json"
    carregar_ou_criar(caminho, "consulta A", tamanho_pagina=50)

    with pytest.raises(ConsultaDivergenteError):
        carregar_ou_criar(caminho, "consulta B", tamanho_pagina=50)


def test_salvar_nao_deixa_arquivo_tmp_para_tras(tmp_path):
    caminho = tmp_path / "checkpoint.json"
    checkpoint = Checkpoint(consulta="x", tamanho_pagina=50)

    salvar(checkpoint, caminho)

    assert caminho.exists()
    assert not caminho.with_suffix(".json.tmp").exists()
    conteudo = json.loads(caminho.read_text(encoding="utf-8"))
    assert conteudo["consulta"] == "x"


def test_salvar_tenta_de_novo_quando_o_windows_nega_o_os_replace_por_um_instante(tmp_path, monkeypatch):
    # enquanto um leitor (o 'status' lendo o checkpoint) tem o arquivo aberto, o
    # os.replace do escritor falha com PermissionError [WinError 5] no Windows; sem
    # tentar de novo, isso mataria uma coleta de horas por causa de um instante de azar
    caminho = tmp_path / "checkpoint.json"
    salvar(Checkpoint(consulta="x", tamanho_pagina=50, itens_gravados=1), caminho)  # versao antiga
    replace_original = modulo.os.replace
    tentativas = []

    def replace_negado_nas_duas_primeiras_vezes(origem, destino):
        tentativas.append(1)
        if len(tentativas) <= 2:
            raise PermissionError("[WinError 5] Acesso negado")
        return replace_original(origem, destino)
    monkeypatch.setattr(modulo.os, "replace", replace_negado_nas_duas_primeiras_vezes)
    esperas = []
    monkeypatch.setattr(time, "sleep", esperas.append)  # nao espera de verdade, mas registra

    salvar(Checkpoint(consulta="x", tamanho_pagina=50, itens_gravados=250), caminho)

    assert len(tentativas) == 3  # 2 negadas + 1 que funcionou
    assert len(esperas) == 2  # e esperou um pouco entre as tentativas (nao e um laco ocupado)
    assert json.loads(caminho.read_text(encoding="utf-8"))["itens_gravados"] == 250
    assert not caminho.with_suffix(".json.tmp").exists()


def test_salvar_relevanta_o_permission_error_se_o_windows_nega_sempre(tmp_path, monkeypatch):
    caminho = tmp_path / "checkpoint.json"
    salvar(Checkpoint(consulta="x", tamanho_pagina=50, itens_gravados=1), caminho)  # versao antiga
    tentativas = []

    def replace_sempre_negado(origem, destino):
        tentativas.append(1)
        raise PermissionError("[WinError 5] Acesso negado")
    monkeypatch.setattr(modulo.os, "replace", replace_sempre_negado)
    monkeypatch.setattr(time, "sleep", lambda segundos: None)

    with pytest.raises(PermissionError):
        salvar(Checkpoint(consulta="x", tamanho_pagina=50, itens_gravados=250), caminho)

    assert len(tentativas) == 10  # desiste depois de 10 tentativas, nao antes e nao pra sempre
    assert json.loads(caminho.read_text(encoding="utf-8"))["itens_gravados"] == 1  # o antigo segue valido


def test_salvar_cria_pastas_que_ainda_nao_existem(tmp_path):
    caminho = tmp_path / "gallica_crawl" / "algum-job" / "checkpoint.json"
    checkpoint = Checkpoint(consulta="x", tamanho_pagina=50)

    salvar(checkpoint, caminho)

    assert caminho.exists()


def test_slug_consulta_e_legivel_e_estavel():
    slug1 = slug_consulta('dc.type all "monographie"')
    slug2 = slug_consulta('dc.type all "monographie"')

    assert slug1 == slug2  # mesma consulta sempre gera o mesmo slug
    assert slug1.startswith("dc-type-all-monographie")


def test_slug_consulta_diferentes_para_consultas_diferentes():
    assert slug_consulta("consulta A") != slug_consulta("consulta B")
