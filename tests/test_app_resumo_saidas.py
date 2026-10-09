# -*- coding: utf-8 -*-
"""Testes das funções que "olham" a pasta saidas/ (core/resumo_saidas.py)."""
import os
import time

from buscador.adapters.base import Item
from buscador.core import resumo_saidas as rs
from buscador.core.planilha import gerar_planilha


def _arquivo(caminho, tamanho=10):
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_bytes(b"x" * tamanho)
    return caminho


def test_listar_planilhas_da_mais_nova_para_a_mais_velha(tmp_path):
    velha = _arquivo(tmp_path / "velha.xlsx")
    nova = _arquivo(tmp_path / "sub" / "nova.xlsx")
    os.utime(velha, (time.time() - 3600, time.time() - 3600))
    _arquivo(tmp_path / "~$aberta.xlsx")  # temporário do Excel: ignora
    _arquivo(tmp_path / "telegram" / "arquivos" / "escondida.xlsx")  # pasta de downloads: não entra
    _arquivo(tmp_path / "nota.txt")
    achadas = rs.listar_planilhas(tmp_path)
    assert [p.caminho for p in achadas] == [nova, velha]


def test_listar_planilhas_respeita_profundidade(tmp_path):
    _arquivo(tmp_path / "a" / "b.xlsx")
    _arquivo(tmp_path / "solta.xlsx")
    assert [p.caminho.name for p in rs.listar_planilhas(tmp_path, profundidade_maxima=0)] == ["solta.xlsx"]


def test_listar_planilhas_de_pasta_que_nao_existe(tmp_path):
    assert rs.listar_planilhas(tmp_path / "nao_existe") == []


def test_contar_arquivos_telegram(tmp_path):
    tg = tmp_path / "telegram"
    _arquivo(tg / "arquivos" / "1_a.pdf", 100)
    _arquivo(tg / "topico_783" / "arquivos" / "2_b.pdf", 50)
    _arquivo(tg / "topico_783" / "arquivos" / "repetidos" / "c - msg 3.pdf", 5)
    _arquivo(tg / "topico_783" / "arquivos" / "4_d.pdf.tmp", 999)  # pela metade: não conta
    _arquivo(tg / "topico_783" / "lista.xlsx", 999)  # fora de "arquivos": não conta
    assert rs.contar_arquivos_telegram(tg) == (3, 155)


def test_contar_arquivos_telegram_sem_pasta(tmp_path):
    assert rs.contar_arquivos_telegram(tmp_path / "nada") == (0, 0)


def test_formatar_tamanho():
    assert rs.formatar_tamanho(0) == "0 bytes"
    assert rs.formatar_tamanho(2048) == "2,0 KB"
    assert rs.formatar_tamanho(int(125.7 * 1024 ** 3)) == "125,7 GB"
    assert rs.formatar_tamanho(5 * 1024 ** 4) == "5120,0 GB"


def _item(titulo, categoria=None):
    item = Item(titulo_original=titulo, link=f"https://x.org/{titulo}", fonte="teste")
    if categoria:
        item.extra["categoria"] = categoria
    return item


def test_ler_previa_planilha_descobre_a_bolinha_pela_cor(tmp_path):
    caminho = gerar_planilha(
        [_item("a", "verde"), _item("b", "requer login"), _item("c", "quebrado"), _item("d")],
        tmp_path / "p.xlsx",
    )
    colunas, linhas, bolinhas = rs.ler_previa_planilha(caminho)
    assert colunas[0] == "titulo_original" and "avaliacao_humana" in colunas
    assert [linha[0] for linha in linhas] == ["a", "b", "c", "d"]
    assert bolinhas == ["🟢", "🔵", "🔴", "⚪"]


def test_ler_previa_planilha_para_no_limite(tmp_path):
    caminho = gerar_planilha([_item(str(i)) for i in range(30)], tmp_path / "p.xlsx")
    _colunas, linhas, bolinhas = rs.ler_previa_planilha(caminho, limite=10)
    assert len(linhas) == 10 and len(bolinhas) == 10
