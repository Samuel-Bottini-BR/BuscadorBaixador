# -*- coding: utf-8 -*-
from unittest.mock import MagicMock, patch

from buscador.core import traducao


def test_texto_vazio_nao_chama_nada():
    with patch.object(traducao, "_traduzir_online") as online, \
         patch.object(traducao, "_traduzir_offline") as offline:
        assert traducao.traduzir("") == ""
        assert traducao.traduzir("   ") == ""
    online.assert_not_called()
    offline.assert_not_called()


def test_caminho_feliz_so_chama_online():
    with patch.object(traducao, "_traduzir_online", return_value="texto traduzido") as online, \
         patch.object(traducao, "_traduzir_offline") as offline:
        resultado = traducao.traduzir("texto original", idioma_origem="fr")
    assert resultado == "texto traduzido"
    online.assert_called_once_with("texto original", "fr", "pt")
    offline.assert_not_called()


def test_cai_para_offline_quando_online_falha():
    with patch.object(traducao, "_traduzir_online", side_effect=ConnectionError("sem internet")), \
         patch.object(traducao, "_traduzir_offline", return_value="tradução offline") as offline:
        resultado = traducao.traduzir("texto original", idioma_origem="fr")
    assert resultado == "tradução offline"
    offline.assert_called_once_with("texto original", "fr", "pt")


def test_mantem_original_quando_os_dois_falham():
    with patch.object(traducao, "_traduzir_online", side_effect=ConnectionError), \
         patch.object(traducao, "_traduzir_offline", side_effect=traducao.ErroTraducao("sem modelo")):
        resultado = traducao.traduzir("texto original", idioma_origem="fr")
    assert resultado == "texto original"


def test_traduzir_online_tenta_de_novo_antes_de_desistir():
    # O deep-translator (busca gratuita do Google) e instavel na pratica: a
    # mesma frase pode falhar e funcionar em chamadas seguidas -- vale tentar
    # de novo antes de cair pro offline por causa de uma falha passageira.
    tradutor_fake = MagicMock()
    tradutor_fake.translate.side_effect = [Exception("instabilidade"), "traduzido"]
    with patch("deep_translator.GoogleTranslator", return_value=tradutor_fake), \
         patch.object(traducao.time, "sleep"):
        resultado = traducao._traduzir_online("texto", "fr", "pt")
    assert resultado == "traduzido"
    assert tradutor_fake.translate.call_count == 2


def test_traduzir_online_desiste_apos_todas_as_tentativas():
    tradutor_fake = MagicMock()
    tradutor_fake.translate.side_effect = Exception("sempre falha")
    with patch("deep_translator.GoogleTranslator", return_value=tradutor_fake), \
         patch.object(traducao.time, "sleep"):
        try:
            traducao._traduzir_online("texto", "fr", "pt")
            assert False, "deveria ter levantado"
        except Exception as e:
            assert str(e) == "sempre falha"
    assert tradutor_fake.translate.call_count == traducao.TENTATIVAS_ONLINE


def test_offline_com_idioma_auto_levanta_erro_tratado():
    # Sem mockar _traduzir_offline: o proprio codigo real recusa "auto" antes
    # de tocar no argostranslate (nao baixa modelo nenhum, nao usa rede).
    with patch.object(traducao, "_traduzir_online", side_effect=ConnectionError):
        resultado = traducao.traduzir("texto original", idioma_origem="auto")
    assert resultado == "texto original"
