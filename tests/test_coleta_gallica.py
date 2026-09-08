# -*- coding: utf-8 -*-
import xml.etree.ElementTree as ET
from types import SimpleNamespace
from unittest.mock import MagicMock
from urllib.parse import parse_qs, urlparse

import pytest
import requests

from buscador.adapters.gallica import RespostaVaziaInesperadaError
from buscador.core.checkpoint import carregar_ou_criar
from buscador.core.coleta_csv import carregar_itens_csv
from buscador.core.coleta_gallica import coletar

CONSULTA = 'dc.type all "monographie"'


def _registros_sinteticos(quantidade):
    registros = []
    for indice in range(quantidade):
        registro = ET.Element("{http://www.loc.gov/zing/srw/}record")
        dados = ET.SubElement(registro, "{http://www.loc.gov/zing/srw/}recordData")
        dc = ET.SubElement(dados, "{http://purl.org/dc/elements/1.1/}dc")
        titulo = ET.SubElement(dc, "{http://purl.org/dc/elements/1.1/}title")
        titulo.text = f"Livro sintetico {indice + 1}"
        extra = ET.SubElement(registro, "{http://www.loc.gov/zing/srw/}extraRecordData")
        link = ET.SubElement(extra, "link")
        link.text = f"https://gallica.bnf.fr/ark:/00000/livro-{indice + 1}"
        registros.append(registro)
    return registros


def _resposta_pagina(todos_registros, inicio_idx, quantidade):
    fatia = todos_registros[inicio_idx:inicio_idx + quantidade]
    raiz = ET.Element("{http://www.loc.gov/zing/srw/}searchRetrieveResponse")
    numero = ET.SubElement(raiz, "{http://www.loc.gov/zing/srw/}numberOfRecords")
    numero.text = str(len(todos_registros))
    registros_no = ET.SubElement(raiz, "{http://www.loc.gov/zing/srw/}records")
    for registro in fatia:
        registros_no.append(registro)
    resposta = MagicMock()
    resposta.text = ET.tostring(raiz, encoding="unicode")
    return resposta


def _cliente_para_total(quantidade_total, quebra_em_startrecord=None):
    """Cliente fake que responde corretamente a qualquer startRecord pedido,
    calculado a partir de um corpus sintetico fixo. Se quebra_em_startrecord
    for passado, a PRIMEIRA vez que esse startRecord for pedido levanta um
    erro (simula uma pagina que falha/interrompe o processo)."""
    todos_registros = _registros_sinteticos(quantidade_total)
    ja_quebrou = {"sim": False}

    def get(url):
        parametros = parse_qs(urlparse(url).query)
        inicio = int(parametros["startRecord"][0])
        quantidade = int(parametros["maximumRecords"][0])
        if quebra_em_startrecord is not None and inicio == quebra_em_startrecord and not ja_quebrou["sim"]:
            ja_quebrou["sim"] = True
            raise RuntimeError("falha simulada de rede")
        return _resposta_pagina(todos_registros, inicio - 1, quantidade)

    cliente = MagicMock()
    cliente.get.side_effect = get
    return cliente


def test_coleta_completa_grava_csv_e_marca_checkpoint_concluido(tmp_path):
    diretorio_job = tmp_path / "job"
    cliente = _cliente_para_total(5)

    checkpoint = coletar(CONSULTA, diretorio_job, tamanho_pagina=2, cliente=cliente)

    assert checkpoint.concluido is True
    assert checkpoint.itens_gravados == 5
    assert checkpoint.total_registros_api == 5

    itens = carregar_itens_csv(diretorio_job / "itens.csv")
    assert len(itens) == 5
    assert itens[0].titulo_original == "Livro sintetico 1"
    assert itens[4].titulo_original == "Livro sintetico 5"


def test_retomada_apos_interrupcao_continua_da_pagina_certa(tmp_path):
    diretorio_job = tmp_path / "job"
    # 5 itens, paginas de 2: startRecord 1, 3, 5 -- quebra bem na segunda pagina
    cliente_que_falha = _cliente_para_total(5, quebra_em_startrecord=3)

    with pytest.raises(RuntimeError):
        coletar(CONSULTA, diretorio_job, tamanho_pagina=2, cliente=cliente_que_falha)

    checkpoint_apos_falha = carregar_ou_criar(diretorio_job / "checkpoint.json", CONSULTA, 2)
    assert checkpoint_apos_falha.concluido is False
    assert checkpoint_apos_falha.proximo_start_record == 3  # so a 1a pagina (2 itens) foi confirmada

    # "reinicia o programa": novo cliente, sem falha, mesma pasta de job
    cliente_de_retomada = _cliente_para_total(5)
    checkpoint_final = coletar(CONSULTA, diretorio_job, tamanho_pagina=2, cliente=cliente_de_retomada)

    assert checkpoint_final.concluido is True
    assert checkpoint_final.itens_gravados == 5

    # a 1a pagina nao foi buscada de novo pelo cliente de retomada
    startrecords_pedidos = [
        parse_qs(urlparse(chamada.args[0]).query)["startRecord"][0]
        for chamada in cliente_de_retomada.get.call_args_list
    ]
    assert startrecords_pedidos == ["3", "5"]

    itens = carregar_itens_csv(diretorio_job / "itens.csv")
    assert len(itens) == 5  # sem duplicata e sem lacuna
    assert sorted(i.titulo_original for i in itens) == [f"Livro sintetico {n}" for n in range(1, 6)]


def test_429_persistente_pausa_pelo_cooldown_e_tenta_de_novo(tmp_path):
    diretorio_job = tmp_path / "job"
    todos_registros = _registros_sinteticos(2)
    ja_falhou = {"sim": False}

    def get(url):
        parametros = parse_qs(urlparse(url).query)
        inicio = int(parametros["startRecord"][0])
        quantidade = int(parametros["maximumRecords"][0])
        if not ja_falhou["sim"]:
            ja_falhou["sim"] = True
            raise requests.HTTPError(response=SimpleNamespace(status_code=429))
        return _resposta_pagina(todos_registros, inicio - 1, quantidade)

    cliente = MagicMock()
    cliente.get.side_effect = get
    dormir_fake = MagicMock()

    checkpoint = coletar(CONSULTA, diretorio_job, tamanho_pagina=2, cliente=cliente,
                          cooldown_429_segundos=600, dormir=dormir_fake)

    dormir_fake.assert_called_once_with(600)
    assert checkpoint.concluido is True
    assert checkpoint.itens_gravados == 2


def test_progresso_fct_e_chamado_uma_vez_por_pagina(tmp_path):
    diretorio_job = tmp_path / "job"
    cliente = _cliente_para_total(5)
    progresso_fct = MagicMock()

    coletar(CONSULTA, diretorio_job, tamanho_pagina=2, cliente=cliente, progresso_fct=progresso_fct)

    assert progresso_fct.call_count == 3  # paginas de 2, 2, 1
    ultimo_checkpoint = progresso_fct.call_args_list[-1].args[0]
    assert ultimo_checkpoint.itens_gravados == 5


def test_pagina_vazia_inesperada_pausa_e_tenta_de_novo(tmp_path):
    """Regressao do caso real (2026-09-08): pagina no meio da busca voltou
    vazia mesmo com o total declarado ainda nao alcancado. Nao pode virar
    'concluido' -- tem que pausar e tentar de novo do mesmo startRecord."""
    diretorio_job = tmp_path / "job"
    todos_registros = _registros_sinteticos(4)
    ja_falhou = {"sim": False}

    def get(url):
        parametros = parse_qs(urlparse(url).query)
        inicio = int(parametros["startRecord"][0])
        quantidade = int(parametros["maximumRecords"][0])
        if inicio == 3 and not ja_falhou["sim"]:
            ja_falhou["sim"] = True
            resposta = MagicMock()
            resposta.text = (
                '<srw:searchRetrieveResponse xmlns:srw="http://www.loc.gov/zing/srw/">'
                "<srw:numberOfRecords>4</srw:numberOfRecords>"
                "<srw:records></srw:records>"
                "</srw:searchRetrieveResponse>"
            )
            return resposta
        return _resposta_pagina(todos_registros, inicio - 1, quantidade)

    cliente = MagicMock()
    cliente.get.side_effect = get
    dormir_fake = MagicMock()

    checkpoint = coletar(CONSULTA, diretorio_job, tamanho_pagina=2, cliente=cliente,
                          cooldown_pagina_vazia_segundos=15, dormir=dormir_fake)

    dormir_fake.assert_called_once_with(15)
    assert checkpoint.concluido is True
    assert checkpoint.itens_gravados == 4

    itens = carregar_itens_csv(diretorio_job / "itens.csv")
    assert len(itens) == 4  # sem lacuna: a pagina que falhou foi buscada nova depois


def test_erro_que_nao_e_429_sobe_e_para_a_coleta(tmp_path):
    diretorio_job = tmp_path / "job"
    cliente = MagicMock()
    cliente.get.side_effect = requests.HTTPError(response=SimpleNamespace(status_code=500))

    with pytest.raises(requests.HTTPError):
        coletar(CONSULTA, diretorio_job, tamanho_pagina=2, cliente=cliente)


def test_coletar_de_novo_apos_concluido_nao_faz_nenhuma_chamada(tmp_path):
    diretorio_job = tmp_path / "job"
    cliente = _cliente_para_total(2)
    coletar(CONSULTA, diretorio_job, tamanho_pagina=2, cliente=cliente)

    cliente_que_nao_deveria_ser_chamado = MagicMock()
    checkpoint = coletar(CONSULTA, diretorio_job, tamanho_pagina=2,
                          cliente=cliente_que_nao_deveria_ser_chamado)

    assert checkpoint.concluido is True
    cliente_que_nao_deveria_ser_chamado.get.assert_not_called()
