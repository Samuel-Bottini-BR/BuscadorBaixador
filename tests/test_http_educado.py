# -*- coding: utf-8 -*-
from unittest.mock import MagicMock, patch

from buscador.core.http_educado import ClienteEducado


def test_primeira_chamada_nao_espera():
    cliente = ClienteEducado("UA-teste", intervalo_segundos=2.0)
    with patch("buscador.core.http_educado.time.sleep") as sleep_mock, \
         patch("buscador.core.http_educado.requests.get", return_value=MagicMock(status_code=200)):
        cliente.get("https://exemplo.com")
    sleep_mock.assert_not_called()


def test_segunda_chamada_espera_o_intervalo():
    cliente = ClienteEducado("UA-teste", intervalo_segundos=2.0)
    # 1a chamada a monotonic(): dentro de _esperar_intervalo, pra medir o decorrido.
    # 2a chamada: depois de esperar, pra marcar a nova _ultima_chamada.
    tempos = iter([100.5, 102.0])

    with patch("buscador.core.http_educado.time.monotonic", side_effect=lambda: next(tempos)), \
         patch("buscador.core.http_educado.time.sleep") as sleep_mock, \
         patch("buscador.core.http_educado.requests.get", return_value=MagicMock(status_code=200)):
        cliente._ultima_chamada = 100.0
        cliente.get("https://exemplo.com")

    sleep_mock.assert_called_once()
    faltam = sleep_mock.call_args[0][0]
    assert faltam == 1.5  # 2.0 - 0.5 decorrido


def test_user_agent_vai_no_cabecalho():
    cliente = ClienteEducado("BuscadorBaixador-teste/0.1")
    with patch("buscador.core.http_educado.requests.get", return_value=MagicMock(status_code=200)) as get_mock:
        cliente.get("https://exemplo.com")
    _, kwargs = get_mock.call_args
    assert kwargs["headers"]["User-Agent"] == "BuscadorBaixador-teste/0.1"


def test_levanta_erro_em_status_ruim():
    resposta = MagicMock()
    resposta.raise_for_status.side_effect = Exception("erro http")
    cliente = ClienteEducado("UA-teste")
    with patch("buscador.core.http_educado.requests.get", return_value=resposta):
        try:
            cliente.get("https://exemplo.com")
            assert False, "deveria ter levantado"
        except Exception as e:
            assert str(e) == "erro http"


def test_retenta_em_429_antes_de_desistir():
    resposta_429 = MagicMock(status_code=429, headers={"Retry-After": "1"})
    resposta_ok = MagicMock(status_code=200)
    cliente = ClienteEducado("UA-teste")
    with patch("buscador.core.http_educado.requests.get", side_effect=[resposta_429, resposta_ok]), \
         patch("buscador.core.http_educado.time.sleep") as sleep_mock:
        resultado = cliente.get("https://exemplo.com")
    assert resultado is resposta_ok
    sleep_mock.assert_any_call(1.0)


def test_desiste_apos_todas_as_tentativas_em_429():
    resposta_429 = MagicMock(status_code=429, headers={})
    resposta_429.raise_for_status.side_effect = Exception("429 sempre")
    cliente = ClienteEducado("UA-teste")
    with patch("buscador.core.http_educado.requests.get", return_value=resposta_429) as get_mock, \
         patch("buscador.core.http_educado.time.sleep") as sleep_mock:
        try:
            cliente.get("https://exemplo.com")
            assert False, "deveria ter levantado"
        except Exception as e:
            assert str(e) == "429 sempre"
    assert get_mock.call_count == ClienteEducado.TENTATIVAS_429
    # espera padrao (sem Retry-After) dobrando a cada nova tentativa: 5s, 10s, 20s
    sleep_mock.assert_any_call(5.0)
    sleep_mock.assert_any_call(10.0)
    sleep_mock.assert_any_call(20.0)
