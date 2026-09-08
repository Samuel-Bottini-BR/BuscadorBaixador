# -*- coding: utf-8 -*-
import json

import pytest

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
