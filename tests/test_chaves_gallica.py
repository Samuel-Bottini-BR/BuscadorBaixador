# -*- coding: utf-8 -*-
from buscador.core.chaves_gallica import extrair_ark_id


def test_extrai_ark_id_com_http_e_sufixo_f21_item():
    """Link com http:// e sufixo /f21.item."""
    url = "http://gallica.bnf.fr/ark:/12148/btv1b8595063v/f21.item"
    assert extrair_ark_id(url) == "btv1b8595063v"


def test_extrai_ark_id_com_https_e_sufixo_f1_item():
    """Link com https:// e sufixo /f1.item."""
    url = "https://gallica.bnf.fr/ark:/12148/bpt6k9112480c/f1.item"
    assert extrair_ark_id(url) == "bpt6k9112480c"


def test_extrai_ark_id_sem_sufixo():
    """Link sem sufixo após o ark id."""
    url = "http://gallica.bnf.fr/ark:/12148/btv1b8595063v"
    assert extrair_ark_id(url) == "btv1b8595063v"


def test_extrai_ark_id_com_sufixo_f1_image():
    """Link com sufixo /f1.image."""
    url = "https://gallica.bnf.fr/ark:/12148/bpt6k9112480c/f1.image"
    assert extrair_ark_id(url) == "bpt6k9112480c"


def test_devolve_none_para_string_vazia():
    """String vazia deve devolver None."""
    assert extrair_ark_id("") is None


def test_devolve_none_para_none():
    """None como entrada deve devolver None."""
    assert extrair_ark_id(None) is None


def test_devolve_none_quando_nao_tem_padrao():
    """Link sem o padrão ark:/12148/ deve devolver None."""
    url = "http://gallica.bnf.fr/pagina-qualquer"
    assert extrair_ark_id(url) is None
