# -*- coding: utf-8 -*-
import json
import xml.etree.ElementTree as ET
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
import requests

from buscador.adapters.gallica import RespostaVaziaInesperadaError
from buscador.core.backfill_gallica import (
    COOLDOWN_429_PADRAO_SEGUNDOS,
    COOLDOWN_INFRA_PADRAO_SEGUNDOS,
    COOLDOWN_LOTE_VAZIO_PADRAO_SEGUNDOS,
    CheckpointBackfill,
    backfill,
    carregar_ou_criar_checkpoint,
    salvar_checkpoint,
)


def _registro_sintetico(ark_id, titulo=None):
    """Monta um <srw:record> sintetico, no mesmo formato XML real da
    Gallica (ver tests/test_coleta_gallica.py::_registros_sinteticos), pra
    UM ark id especifico -- com autor/ano/direitos/idioma preenchidos, pra
    poder conferir que o backfill extrai esses campos certo."""
    registro = ET.Element("{http://www.loc.gov/zing/srw/}record")
    dados = ET.SubElement(registro, "{http://www.loc.gov/zing/srw/}recordData")
    dc = ET.SubElement(dados, "{http://purl.org/dc/elements/1.1/}dc")

    campo_titulo = ET.SubElement(dc, "{http://purl.org/dc/elements/1.1/}title")
    campo_titulo.text = titulo or f"Livro {ark_id}"
    campo_autor = ET.SubElement(dc, "{http://purl.org/dc/elements/1.1/}creator")
    campo_autor.text = f"Autor de {ark_id}"
    campo_data = ET.SubElement(dc, "{http://purl.org/dc/elements/1.1/}date")
    campo_data.text = "1900"
    campo_idioma = ET.SubElement(dc, "{http://purl.org/dc/elements/1.1/}language")
    campo_idioma.text = "fre"
    campo_direitos = ET.SubElement(dc, "{http://purl.org/dc/elements/1.1/}rights")
    campo_direitos.text = "domaine public"

    extra = ET.SubElement(registro, "{http://www.loc.gov/zing/srw/}extraRecordData")
    link = ET.SubElement(extra, "link")
    link.text = f"https://gallica.bnf.fr/ark:/12148/{ark_id}"
    return registro


def _resposta_com_arks(ark_ids_presentes):
    """Monta a resposta XML completa (searchRetrieveResponse) contendo só
    os ark ids da lista passada -- simula a Gallica so devolvendo os itens
    que ela realmente tem, mesmo que o lote pedido tenha mais ark ids."""
    raiz = ET.Element("{http://www.loc.gov/zing/srw/}searchRetrieveResponse")
    numero = ET.SubElement(raiz, "{http://www.loc.gov/zing/srw/}numberOfRecords")
    numero.text = str(len(ark_ids_presentes))
    registros_no = ET.SubElement(raiz, "{http://www.loc.gov/zing/srw/}records")
    for ark_id in ark_ids_presentes:
        registros_no.append(_registro_sintetico(ark_id))
    resposta = MagicMock()
    resposta.text = ET.tostring(raiz, encoding="unicode")
    return resposta


def _cliente_com_respostas(*respostas_ou_erros):
    """Cliente fake cujo .get() devolve, em sequencia, cada item da lista
    passada -- se o item for uma excecao, levanta ela em vez de devolver."""
    cliente = MagicMock()

    def get(url):
        item = respostas_ou_erros[cliente.get.call_count - 1]
        if isinstance(item, Exception):
            raise item
        return item

    cliente.get.side_effect = get
    return cliente


def _carregar_resultado_json(caminho):
    return json.loads(caminho.read_text(encoding="utf-8"))


def test_lote_completo_todos_encontrados(tmp_path):
    diretorio_job = tmp_path / "job"
    ark_ids = ["ark1", "ark2", "ark3"]
    cliente = _cliente_com_respostas(_resposta_com_arks(ark_ids))

    checkpoint = backfill(ark_ids, diretorio_job, tamanho_lote=3, cliente=cliente)

    assert checkpoint.concluido is True
    assert checkpoint.proximo_lote == 1
    assert checkpoint.encontrados == 3
    assert checkpoint.nao_encontrados == 0
    cliente.get.assert_called_once()

    resultado = _carregar_resultado_json(diretorio_job / "resultado_backfill.json")
    assert set(resultado.keys()) == set(ark_ids)
    for ark_id in ark_ids:
        entrada = resultado[ark_id]
        assert entrada["status"] == "encontrado"
        assert entrada["autor"] == f"Autor de {ark_id}"
        assert entrada["ano"] == "1900"
        assert entrada["dominio_publico"] == "Sim"
        assert entrada["idioma_origem"] == "fr"


def test_lote_parcial_ark_ids_ausentes_viram_nao_encontrado_sem_erro(tmp_path):
    diretorio_job = tmp_path / "job"
    ark_ids = ["ark1", "ark2", "ark3", "ark4"]
    # so ark1 e ark3 realmente existem na Gallica -- ark2 e ark4 nao
    # aparecem na resposta (ex.: sao periodicos, fora do escopo do indice oficial)
    cliente = _cliente_com_respostas(_resposta_com_arks(["ark1", "ark3"]))

    checkpoint = backfill(ark_ids, diretorio_job, tamanho_lote=4, cliente=cliente)

    assert checkpoint.concluido is True
    assert checkpoint.encontrados == 2
    assert checkpoint.nao_encontrados == 2

    resultado = _carregar_resultado_json(diretorio_job / "resultado_backfill.json")
    assert resultado["ark1"]["status"] == "encontrado"
    assert resultado["ark3"]["status"] == "encontrado"
    assert resultado["ark2"] == {
        "status": "nao_encontrado", "autor": None, "ano": None,
        "dominio_publico": None, "idioma_origem": None,
    }
    assert resultado["ark4"]["status"] == "nao_encontrado"


def test_checkpoint_retoma_sem_reprocessar_lote_concluido(tmp_path):
    diretorio_job = tmp_path / "job"
    ark_ids = ["ark1", "ark2", "ark3", "ark4"]
    diretorio_job.mkdir(parents=True)

    # simula uma interrupcao: o lote 0 ([ark1, ark2]) ja foi processado e
    # salvo (resultado + checkpoint avancado), mas o lote 1 ([ark3, ark4])
    # ainda nao rodou
    caminho_checkpoint = diretorio_job / "checkpoint_backfill.json"
    caminho_resultado = diretorio_job / "resultado_backfill.json"
    resultado_parcial = {
        "ark1": {"status": "encontrado", "autor": "Autor de ark1", "ano": "1900",
                  "dominio_publico": "Sim", "idioma_origem": "fr"},
        "ark2": {"status": "nao_encontrado", "autor": None, "ano": None,
                  "dominio_publico": None, "idioma_origem": None},
    }
    caminho_resultado.write_text(json.dumps(resultado_parcial), encoding="utf-8")
    checkpoint_parcial = CheckpointBackfill(
        total_arks=4, tamanho_lote=2, proximo_lote=1, encontrados=1, nao_encontrados=1,
    )
    salvar_checkpoint(checkpoint_parcial, caminho_checkpoint)

    # "reinicia o programa": novo cliente, so responde pelo lote 1
    cliente_de_retomada = _cliente_com_respostas(_resposta_com_arks(["ark3", "ark4"]))
    checkpoint_final = backfill(ark_ids, diretorio_job, tamanho_lote=2, cliente=cliente_de_retomada)

    assert checkpoint_final.concluido is True
    assert checkpoint_final.proximo_lote == 2
    assert checkpoint_final.encontrados == 3  # 1 do lote 0 (ja salvo) + 2 do lote 1
    assert checkpoint_final.nao_encontrados == 1
    cliente_de_retomada.get.assert_called_once()  # so buscou o lote que faltava

    resultado_final = _carregar_resultado_json(caminho_resultado)
    assert set(resultado_final.keys()) == set(ark_ids)
    assert resultado_final["ark1"]["status"] == "encontrado"  # preservado do lote ja concluido
    assert resultado_final["ark2"]["status"] == "nao_encontrado"
    assert resultado_final["ark3"]["status"] == "encontrado"
    assert resultado_final["ark4"]["status"] == "encontrado"


def test_429_dispara_dormir_injetado_e_tenta_o_mesmo_lote_de_novo(tmp_path):
    diretorio_job = tmp_path / "job"
    ark_ids = ["ark1", "ark2"]
    cliente = _cliente_com_respostas(
        requests.HTTPError(response=SimpleNamespace(status_code=429)),
        _resposta_com_arks(ark_ids),
    )
    dormir_fake = MagicMock()

    checkpoint = backfill(ark_ids, diretorio_job, tamanho_lote=2, cliente=cliente, dormir=dormir_fake)

    dormir_fake.assert_called_once_with(COOLDOWN_429_PADRAO_SEGUNDOS)
    assert checkpoint.concluido is True
    assert checkpoint.encontrados == 2
    assert checkpoint.proximo_lote == 1  # o lote so avancou uma vez, nao duas
    assert cliente.get.call_count == 2  # 1a tentativa (429) + 2a tentativa (sucesso), mesmo lote

    resultado = _carregar_resultado_json(diretorio_job / "resultado_backfill.json")
    assert resultado["ark1"]["status"] == "encontrado"
    assert resultado["ark2"]["status"] == "encontrado"


def test_resposta_vazia_inesperada_pausa_e_tenta_de_novo(tmp_path):
    diretorio_job = tmp_path / "job"
    ark_ids = ["ark1", "ark2"]
    resposta_vazia_mas_total_nao_zero = MagicMock()
    resposta_vazia_mas_total_nao_zero.text = (
        '<srw:searchRetrieveResponse xmlns:srw="http://www.loc.gov/zing/srw/">'
        "<srw:numberOfRecords>2</srw:numberOfRecords>"
        "<srw:records></srw:records>"
        "</srw:searchRetrieveResponse>"
    )
    cliente = _cliente_com_respostas(resposta_vazia_mas_total_nao_zero, _resposta_com_arks(ark_ids))
    dormir_fake = MagicMock()

    checkpoint = backfill(ark_ids, diretorio_job, tamanho_lote=2, cliente=cliente, dormir=dormir_fake)

    dormir_fake.assert_called_once_with(COOLDOWN_LOTE_VAZIO_PADRAO_SEGUNDOS)
    assert checkpoint.concluido is True
    assert checkpoint.encontrados == 2


def test_erro_infraestrutura_pausa_e_tenta_de_novo(tmp_path):
    diretorio_job = tmp_path / "job"
    ark_ids = ["ark1", "ark2"]
    cliente = _cliente_com_respostas(
        requests.exceptions.ConnectTimeout("timeout simulado de conexao"),
        _resposta_com_arks(ark_ids),
    )
    dormir_fake = MagicMock()

    checkpoint = backfill(ark_ids, diretorio_job, tamanho_lote=2, cliente=cliente, dormir=dormir_fake)

    dormir_fake.assert_called_once_with(COOLDOWN_INFRA_PADRAO_SEGUNDOS)
    assert checkpoint.concluido is True


def test_erro_500_pausa_e_tenta_de_novo(tmp_path):
    diretorio_job = tmp_path / "job"
    ark_ids = ["ark1", "ark2"]
    cliente = _cliente_com_respostas(
        requests.HTTPError(response=SimpleNamespace(status_code=500)),
        _resposta_com_arks(ark_ids),
    )
    dormir_fake = MagicMock()

    checkpoint = backfill(ark_ids, diretorio_job, tamanho_lote=2, cliente=cliente, dormir=dormir_fake)

    dormir_fake.assert_called_once_with(COOLDOWN_INFRA_PADRAO_SEGUNDOS)
    assert checkpoint.concluido is True


def test_erro_4xx_que_nao_e_429_propaga_e_para(tmp_path):
    diretorio_job = tmp_path / "job"
    ark_ids = ["ark1", "ark2"]
    cliente = MagicMock()
    cliente.get.side_effect = requests.HTTPError(response=SimpleNamespace(status_code=400))

    with pytest.raises(requests.HTTPError):
        backfill(ark_ids, diretorio_job, tamanho_lote=2, cliente=cliente)

    # nada foi confirmado -- checkpoint continua no lote 0, nada concluido
    checkpoint_apos_falha = carregar_ou_criar_checkpoint(
        diretorio_job / "checkpoint_backfill.json", len(ark_ids), 2
    )
    assert checkpoint_apos_falha.concluido is False
    assert checkpoint_apos_falha.proximo_lote == 0


def test_varios_lotes_processa_todos_em_ordem(tmp_path):
    diretorio_job = tmp_path / "job"
    ark_ids = ["ark1", "ark2", "ark3", "ark4", "ark5"]
    cliente = _cliente_com_respostas(
        _resposta_com_arks(["ark1", "ark2"]),
        _resposta_com_arks(["ark3", "ark4"]),
        _resposta_com_arks(["ark5"]),
    )

    checkpoint = backfill(ark_ids, diretorio_job, tamanho_lote=2, cliente=cliente)

    assert checkpoint.concluido is True
    assert checkpoint.proximo_lote == 3  # 3 lotes: 2 + 2 + 1
    assert checkpoint.encontrados == 5
    assert cliente.get.call_count == 3

    resultado = _carregar_resultado_json(diretorio_job / "resultado_backfill.json")
    assert set(resultado.keys()) == set(ark_ids)
    assert all(entrada["status"] == "encontrado" for entrada in resultado.values())


def test_backfill_de_novo_apos_concluido_nao_faz_nenhuma_chamada(tmp_path):
    diretorio_job = tmp_path / "job"
    ark_ids = ["ark1", "ark2"]
    cliente = _cliente_com_respostas(_resposta_com_arks(ark_ids))
    backfill(ark_ids, diretorio_job, tamanho_lote=2, cliente=cliente)

    cliente_que_nao_deveria_ser_chamado = MagicMock()
    checkpoint = backfill(ark_ids, diretorio_job, tamanho_lote=2, cliente=cliente_que_nao_deveria_ser_chamado)

    assert checkpoint.concluido is True
    cliente_que_nao_deveria_ser_chamado.get.assert_not_called()


def test_carregar_ou_criar_checkpoint_total_arks_divergente_levanta_erro_claro(tmp_path):
    """Regressao de review (fix round 1): se a lista de ark ids for
    regerada com tamanho diferente (ex.: a tarefa A4 rodar de novo) e o
    backfill for chamado de novo apontando pro MESMO diretorio_job sem
    limpar o checkpoint antigo, retomar silenciosamente aplicaria um
    proximo_lote calculado pra lista ANTIGA na lista NOVA -- pulando um
    pedaco inteiro dela sem erro nenhum. Tem que falhar alto, nao
    continuar por engano."""
    caminho_checkpoint = tmp_path / "checkpoint_backfill.json"
    carregar_ou_criar_checkpoint(caminho_checkpoint, total_arks=10, tamanho_lote=5)

    with pytest.raises(ValueError) as excinfo:
        carregar_ou_criar_checkpoint(caminho_checkpoint, total_arks=20, tamanho_lote=5)

    mensagem = str(excinfo.value)
    assert "10" in mensagem  # valor antigo (salvo)
    assert "20" in mensagem  # valor novo (pedido agora)


def test_carregar_ou_criar_checkpoint_tamanho_lote_divergente_levanta_erro_claro(tmp_path):
    caminho_checkpoint = tmp_path / "checkpoint_backfill.json"
    carregar_ou_criar_checkpoint(caminho_checkpoint, total_arks=10, tamanho_lote=5)

    with pytest.raises(ValueError) as excinfo:
        carregar_ou_criar_checkpoint(caminho_checkpoint, total_arks=10, tamanho_lote=7)

    mensagem = str(excinfo.value)
    assert "5" in mensagem
    assert "7" in mensagem


def test_carregar_ou_criar_checkpoint_valores_iguais_nao_levanta_erro(tmp_path):
    caminho_checkpoint = tmp_path / "checkpoint_backfill.json"
    carregar_ou_criar_checkpoint(caminho_checkpoint, total_arks=10, tamanho_lote=5)

    checkpoint_retomado = carregar_ou_criar_checkpoint(caminho_checkpoint, total_arks=10, tamanho_lote=5)

    assert checkpoint_retomado.total_arks == 10
    assert checkpoint_retomado.tamanho_lote == 5


def test_backfill_com_lista_de_ark_ids_redimensionada_levanta_erro_em_vez_de_pular_lote(tmp_path):
    """Cenario concreto do review: roda o backfill inteiro com 2 ark ids,
    depois chama backfill de novo no MESMO diretorio_job com uma lista
    MAIOR (ex.: a A4 regerou arks_faltantes.json) -- tem que falhar alto em
    vez de silenciosamente reaproveitar um checkpoint que nao corresponde
    mais a essa lista."""
    diretorio_job = tmp_path / "job"
    ark_ids_originais = ["ark1", "ark2"]
    cliente = _cliente_com_respostas(_resposta_com_arks(ark_ids_originais))
    backfill(ark_ids_originais, diretorio_job, tamanho_lote=2, cliente=cliente)

    ark_ids_redimensionados = ["ark1", "ark2", "ark3", "ark4"]
    cliente_novo = MagicMock()
    with pytest.raises(ValueError):
        backfill(ark_ids_redimensionados, diretorio_job, tamanho_lote=2, cliente=cliente_novo)

    cliente_novo.get.assert_not_called()  # falhou antes de fazer qualquer chamada de rede


def test_progresso_fct_e_chamado_uma_vez_por_lote(tmp_path):
    diretorio_job = tmp_path / "job"
    ark_ids = ["ark1", "ark2", "ark3"]
    cliente = _cliente_com_respostas(
        _resposta_com_arks(["ark1"]),
        _resposta_com_arks(["ark2"]),
        _resposta_com_arks(["ark3"]),
    )
    progresso_fct = MagicMock()

    backfill(ark_ids, diretorio_job, tamanho_lote=1, cliente=cliente, progresso_fct=progresso_fct)

    assert progresso_fct.call_count == 3
    ultimo_checkpoint = progresso_fct.call_args_list[-1].args[0]
    assert ultimo_checkpoint.proximo_lote == 3
