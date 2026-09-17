# -*- coding: utf-8 -*-
import json
from unittest.mock import MagicMock, patch

import pytest

from buscador.core.navegador import (
    abrir_navegador,
    resolver_na_mao,
    resolver_perfil,
)


def _local_state_com(mapa_nome_para_pasta, tmp_path):
    """Cria um Local State falso (mesmo formato que o Chrome de verdade usa)
    dentro de tmp_path, devolvendo o caminho da pasta User Data falsa."""
    info_cache = {pasta: {"name": nome} for nome, pasta in mapa_nome_para_pasta.items()}
    conteudo = {"profile": {"info_cache": info_cache}}
    (tmp_path / "Local State").write_text(json.dumps(conteudo), encoding="utf-8")
    return tmp_path


def test_resolver_perfil_acha_a_pasta_certa(tmp_path):
    pasta_user_data = _local_state_com({"Automação": "Profile 3", "Samuel": "Profile 1"}, tmp_path)
    assert resolver_perfil("Automação", pasta_user_data) == "Profile 3"


def test_resolver_perfil_sem_achar_levanta_erro_com_lista(tmp_path):
    pasta_user_data = _local_state_com({"Automação": "Profile 3", "Samuel": "Profile 1"}, tmp_path)
    with pytest.raises(ValueError) as excinfo:
        resolver_perfil("NaoExiste", pasta_user_data)
    assert "Automação" in str(excinfo.value)
    assert "Samuel" in str(excinfo.value)


def test_abrir_navegador_usa_user_data_dir_e_profile_directory(tmp_path):
    pasta_user_data = _local_state_com({"Automação": "Profile 3"}, tmp_path)
    with patch("buscador.core.navegador.pasta_chrome_real", return_value=pasta_user_data), \
         patch("buscador.core.navegador.Driver") as driver_mock:
        abrir_navegador("Automação", headless=True)

    driver_mock.assert_called_once_with(
        headless=True,
        user_data_dir=str(pasta_user_data),
        chromium_arg="--profile-directory=Profile 3",
    )


def test_abrir_navegador_nunca_passa_parametros_de_disfarce(tmp_path):
    pasta_user_data = _local_state_com({"Automação": "Profile 3"}, tmp_path)
    with patch("buscador.core.navegador.pasta_chrome_real", return_value=pasta_user_data), \
         patch("buscador.core.navegador.Driver") as driver_mock:
        abrir_navegador("Automação", headless=False)

    _, kwargs = driver_mock.call_args
    assert "uc" not in kwargs
    assert "uc_cdp" not in kwargs
    assert "uc_sub" not in kwargs


def test_resolver_na_mao_abre_visivel_navega_espera_enter_e_fecha(tmp_path):
    driver_falso = MagicMock()
    with patch("buscador.core.navegador.abrir_navegador", return_value=driver_falso) as abrir_mock, \
         patch("builtins.input", return_value="") as input_mock:
        resolver_na_mao("Automação", "https://archive.org/account/login")

    abrir_mock.assert_called_once_with("Automação", headless=False)
    driver_falso.get.assert_called_once_with("https://archive.org/account/login")
    input_mock.assert_called_once()
    driver_falso.quit.assert_called_once()


def test_resolver_na_mao_fecha_navegador_mesmo_se_input_falhar(tmp_path):
    driver_falso = MagicMock()
    with patch("buscador.core.navegador.abrir_navegador", return_value=driver_falso), \
         patch("builtins.input", side_effect=KeyboardInterrupt):
        try:
            resolver_na_mao("Automação", "https://archive.org/account/login")
            assert False, "deveria ter propagado o KeyboardInterrupt"
        except KeyboardInterrupt:
            pass

    driver_falso.quit.assert_called_once()
