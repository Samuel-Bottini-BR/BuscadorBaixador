# -*- coding: utf-8 -*-
from unittest.mock import patch

from buscador import logar


def test_main_chama_resolver_na_mao_com_perfil_e_url(capsys):
    with patch("buscador.logar.resolver_na_mao") as resolver_mock:
        codigo = logar.main(["internet_archive", "https://archive.org/account/login"])

    resolver_mock.assert_called_once_with("internet_archive", "https://archive.org/account/login")
    assert codigo == 0
    saida = capsys.readouterr().out
    assert "internet_archive" in saida
    assert "Sessão salva" in saida


def test_main_exige_perfil_e_url():
    import pytest
    with pytest.raises(SystemExit):
        logar.main(["so-um-argumento"])
