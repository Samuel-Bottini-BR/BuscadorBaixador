# -*- coding: utf-8 -*-
"""Testes da lista de sites cadastrados (core/sites_cadastrados.py)."""
import json

import pytest

from buscador.core import sites_cadastrados as sc


def test_sem_arquivo_comeca_com_os_sites_que_o_motor_conhece(tmp_path):
    sites = sc.carregar_sites(tmp_path / "sites.json")
    assert {s["adapter"] for s in sites} == {"gallica", "phpbb", "internet_archive"}
    assert not (tmp_path / "sites.json").exists()  # só ler não grava nada


def test_carregar_nao_entrega_a_lista_padrao_original(tmp_path):
    sites = sc.carregar_sites(tmp_path / "sites.json")
    sites[0]["nome"] = "mexido"
    assert sc.SITES_PADRAO[0]["nome"] != "mexido"


def test_salvar_e_carregar_de_volta(tmp_path):
    caminho = tmp_path / "sub" / "sites.json"
    sites = sc.adicionar_site(sc.carregar_sites(caminho), {"nome": "Biblioteca São José", "endereco": "https://bsj.org"})
    sc.salvar_sites(sites, caminho)
    lidos = sc.carregar_sites(caminho)
    assert lidos[-1]["id"] == "biblioteca_sao_jose"
    assert lidos[-1]["nome"] == "Biblioteca São José"  # acento preservado no JSON


def test_arquivo_estragado_avisa_em_vez_de_apagar(tmp_path):
    caminho = tmp_path / "sites.json"
    caminho.write_text("[{", encoding="utf-8")
    with pytest.raises(ValueError, match="defeito"):
        sc.carregar_sites(caminho)
    assert caminho.read_text(encoding="utf-8") == "[{"


def test_arquivo_que_nao_e_lista(tmp_path):
    caminho = tmp_path / "sites.json"
    caminho.write_text(json.dumps({"a": 1}), encoding="utf-8")
    with pytest.raises(ValueError):
        sc.carregar_sites(caminho)


def test_gerar_id_tira_acento_e_simbolo():
    assert sc.gerar_id("Biblioteca São José!") == "biblioteca_sao_jose"
    assert sc.gerar_id("!!!") == "site"


@pytest.mark.parametrize("novo, trecho", [
    ({"nome": "", "endereco": "https://x.org"}, "nome"),
    ({"nome": "X", "endereco": ""}, "endereço"),
    ({"nome": "gallica (bnf)", "endereco": "https://outro.org"}, "Já existe"),
    ({"nome": "Outro", "endereco": "https://archive.org/"}, "já está cadastrado"),
])
def test_adicionar_recusa_vazio_e_repetido(novo, trecho):
    with pytest.raises(ValueError, match=trecho):
        sc.adicionar_site(list(sc.SITES_PADRAO), novo)


def test_adicionar_cria_id_unico():
    sites = [{"id": "biblio", "nome": "A", "endereco": "https://a.org"}]
    sites = sc.adicionar_site(sites, {"nome": "Biblio", "endereco": "https://b.org"})
    assert sites[-1]["id"] == "biblio_2"
    assert sites[-1]["adapter"] is None and sites[-1]["metodo"] == "html"


def test_remover_e_achar():
    sites = list(sc.SITES_PADRAO)
    assert sc.achar_site(sites, "gallica")["nome"] == "Gallica (BnF)"
    assert sc.achar_site(sc.remover_site(sites, "gallica"), "gallica") is None
