# -*- coding: utf-8 -*-
from unittest.mock import patch

from buscador.core.cookies_navegador import cookies_do_chrome


def test_devolve_none_quando_biblioteca_lanca_erro():
    with patch("buscador.core.cookies_navegador.browser_cookie3.chrome", side_effect=Exception("cifrado")):
        assert cookies_do_chrome("exemplo.com") is None


def test_devolve_none_quando_jar_vazio():
    with patch("buscador.core.cookies_navegador.browser_cookie3.chrome", return_value=[]):
        assert cookies_do_chrome("exemplo.com") is None


def test_devolve_jar_quando_tem_cookie():
    jar_falso = [object()]  # so precisa ter len() > 0
    with patch("buscador.core.cookies_navegador.browser_cookie3.chrome", return_value=jar_falso):
        assert cookies_do_chrome("exemplo.com") is jar_falso
