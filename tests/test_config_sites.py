# -*- coding: utf-8 -*-
from buscador.core.config_sites import ler_chave


def test_devolve_none_se_arquivo_nao_existe(tmp_path):
    caminho = tmp_path / "nao-existe.cfg"
    assert ler_chave("ddb", caminho=caminho) is None


def test_devolve_none_se_site_nao_esta_no_arquivo(tmp_path):
    caminho = tmp_path / "buscador.local.cfg"
    caminho.write_text("[outrosite]\nchave_api = abc\n", encoding="utf-8")
    assert ler_chave("ddb", caminho=caminho) is None


def test_le_chave_do_site_certo(tmp_path):
    caminho = tmp_path / "buscador.local.cfg"
    caminho.write_text("[ddb]\nchave_api = minha-chave\n", encoding="utf-8")
    assert ler_chave("ddb", caminho=caminho) == "minha-chave"


def test_le_chave_customizada(tmp_path):
    caminho = tmp_path / "buscador.local.cfg"
    caminho.write_text("[algumsite]\nusuario = fulano\n", encoding="utf-8")
    assert ler_chave("algumsite", chave="usuario", caminho=caminho) == "fulano"


def test_aceita_comentario_no_arquivo(tmp_path):
    caminho = tmp_path / "buscador.local.cfg"
    caminho.write_text("# comentario\n[ddb]\nchave_api = minha-chave\n", encoding="utf-8")
    assert ler_chave("ddb", caminho=caminho) == "minha-chave"
