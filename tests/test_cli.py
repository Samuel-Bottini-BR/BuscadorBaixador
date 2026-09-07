# -*- coding: utf-8 -*-
import pytest
from openpyxl import load_workbook

from buscador import cli
from buscador.adapters.base import Item


class AdapterFake:
    def __init__(self, url):
        self.url = url

    def iter_itens(self):
        yield Item(titulo_original="Obra Teste", link="https://exemplo.com/a.pdf",
                    autor="Fulano", fonte="Fonte Fake", extra={"idioma_origem": "fr"})
        yield Item(titulo_original="Outra Obra", link="https://academia.edu/b",
                    autor="Ciclano", fonte="Fonte Fake", extra={"idioma_origem": "fr"})


def test_escolher_adapter_por_dominio():
    url = "https://grand-sud-medieval.fr/forum/viewtopic.php?f=14&t=9264"
    assert cli.escolher_adapter(url) == "phpbb"


def test_escolher_adapter_forcado_tem_prioridade():
    assert cli.escolher_adapter("https://qualquer-site.com", forcado="ddb") == "ddb"


def test_escolher_adapter_domino_desconhecido_levanta_erro():
    with pytest.raises(ValueError):
        cli.escolher_adapter("https://site-nao-cadastrado.com")


def test_main_ponta_a_ponta_com_adapter_fake(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "construir_adapter", lambda nome, url: AdapterFake(url))
    monkeypatch.setattr(cli, "analisar", lambda link: (
        ("vivo (pdf direto)", "verde") if link.endswith(".pdf") else ("requer login", "requer login")
    ))
    monkeypatch.setattr(cli, "traduzir", lambda texto, idioma_origem="auto", idioma_destino="pt": f"{texto} (PT)")

    destino = tmp_path / "saida.xlsx"
    codigo = cli.main([
        "https://grand-sud-medieval.fr/forum/viewtopic.php?f=14&t=1",
        "--adapter", "phpbb",
        "--saida", str(destino),
    ])

    assert codigo == 0
    assert destino.exists()

    ws = load_workbook(destino)["Links"]
    assert ws.max_row == 3  # cabecalho + 2 itens
    assert ws.cell(row=2, column=1).value == "Obra Teste"
    assert ws.cell(row=2, column=2).value == "Obra Teste (PT)"
    assert ws.cell(row=2, column=6).value == "pdf direto"
    assert ws.cell(row=3, column=6).value == "precisa login"


def test_main_usa_caminho_padrao_quando_sem_saida(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "construir_adapter", lambda nome, url: AdapterFake(url))
    monkeypatch.setattr(cli, "analisar", lambda link: ("vivo (pdf direto)", "verde"))
    monkeypatch.setattr(cli, "traduzir", lambda texto, idioma_origem="auto", idioma_destino="pt": texto)
    monkeypatch.setattr(cli, "SAIDAS", tmp_path)

    codigo = cli.main(["https://grand-sud-medieval.fr/forum/viewtopic.php?f=14&t=1", "--adapter", "phpbb"])

    assert codigo == 0
    gerados = list(tmp_path.glob("grand-sud-medieval-fr_*.xlsx"))
    assert len(gerados) == 1
