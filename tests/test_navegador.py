# -*- coding: utf-8 -*-
from unittest.mock import MagicMock, patch

from buscador.core.navegador import abrir_navegador, caminho_perfil, resolver_na_mao


def test_caminho_perfil_e_por_nome(tmp_path):
    with patch("buscador.core.navegador.PASTA_SESSOES", tmp_path):
        assert caminho_perfil("internet_archive") == tmp_path / "internet_archive"


def test_abrir_navegador_cria_pasta_de_perfil_e_chama_driver(tmp_path):
    with patch("buscador.core.navegador.PASTA_SESSOES", tmp_path), \
         patch("buscador.core.navegador.Driver") as driver_mock:
        abrir_navegador("internet_archive", headless=True)

    perfil = tmp_path / "internet_archive"
    assert perfil.exists()
    # external_pdf tem default False -- quem chama sem passar esse
    # parâmetro (ex. logar.py/resolver_na_mao) continua se comportando
    # igual a antes (Chrome abre PDF no visualizador embutido, como sempre).
    driver_mock.assert_called_once_with(headless=True, user_data_dir=str(perfil), external_pdf=False)


def test_abrir_navegador_repassa_external_pdf_true_pro_driver(tmp_path):
    with patch("buscador.core.navegador.PASTA_SESSOES", tmp_path), \
         patch("buscador.core.navegador.Driver") as driver_mock:
        abrir_navegador("gallica", headless=True, external_pdf=True)

    perfil = tmp_path / "gallica"
    driver_mock.assert_called_once_with(headless=True, user_data_dir=str(perfil), external_pdf=True)


def test_abrir_navegador_nunca_passa_parametros_de_disfarce(tmp_path):
    with patch("buscador.core.navegador.PASTA_SESSOES", tmp_path), \
         patch("buscador.core.navegador.Driver") as driver_mock:
        abrir_navegador("internet_archive", headless=False)

    _, kwargs = driver_mock.call_args
    assert "uc" not in kwargs
    assert "uc_cdp" not in kwargs
    assert "uc_sub" not in kwargs


def test_resolver_na_mao_abre_visivel_navega_espera_enter_e_fecha(tmp_path):
    driver_falso = MagicMock()
    with patch("buscador.core.navegador.PASTA_SESSOES", tmp_path), \
         patch("buscador.core.navegador.abrir_navegador", return_value=driver_falso) as abrir_mock, \
         patch("builtins.input", return_value="") as input_mock:
        resolver_na_mao("internet_archive", "https://archive.org/account/login")

    abrir_mock.assert_called_once_with("internet_archive", headless=False)
    driver_falso.get.assert_called_once_with("https://archive.org/account/login")
    input_mock.assert_called_once()
    driver_falso.quit.assert_called_once()


def test_resolver_na_mao_fecha_navegador_mesmo_se_input_falhar(tmp_path):
    driver_falso = MagicMock()
    with patch("buscador.core.navegador.PASTA_SESSOES", tmp_path), \
         patch("buscador.core.navegador.abrir_navegador", return_value=driver_falso), \
         patch("builtins.input", side_effect=KeyboardInterrupt):
        try:
            resolver_na_mao("internet_archive", "https://archive.org/account/login")
            assert False, "deveria ter propagado o KeyboardInterrupt"
        except KeyboardInterrupt:
            pass

    driver_falso.quit.assert_called_once()
