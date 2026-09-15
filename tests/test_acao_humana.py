# -*- coding: utf-8 -*-
from buscador.core.acao_humana import (
    TIPO_CAPTCHA,
    TIPO_CHAVE_API,
    TIPO_LOGIN,
    AcaoHumanaNecessaria,
    formatar_aviso,
)


def test_guarda_tipo_mensagem_e_site():
    erro = AcaoHumanaNecessaria(TIPO_CHAVE_API, "cadastre-se em tal-site", site="tal-site")
    assert erro.tipo == TIPO_CHAVE_API
    assert erro.mensagem == "cadastre-se em tal-site"
    assert erro.site == "tal-site"


def test_site_e_opcional():
    erro = AcaoHumanaNecessaria(TIPO_LOGIN, "precisa logar")
    assert erro.site is None


def test_e_uma_excecao_de_verdade():
    try:
        raise AcaoHumanaNecessaria(TIPO_CAPTCHA, "apareceu captcha")
    except AcaoHumanaNecessaria as erro:
        assert str(erro) == "apareceu captcha"


def test_formatar_aviso_com_site():
    erro = AcaoHumanaNecessaria(TIPO_LOGIN, "precisa logar em x", site="gallica")
    assert formatar_aviso(erro) == "Preciso da sua ajuda (gallica): precisa logar em x"


def test_formatar_aviso_sem_site():
    erro = AcaoHumanaNecessaria(TIPO_CHAVE_API, "falta a chave")
    assert formatar_aviso(erro) == "Preciso da sua ajuda: falta a chave"
