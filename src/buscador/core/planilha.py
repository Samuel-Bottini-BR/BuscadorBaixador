# -*- coding: utf-8 -*-
"""Gera a planilha .xlsx de saida da Fase 1, a partir de uma lista de Item ja
enriquecidos (status_link/tipo/titulo_pt preenchidos por quem chama --
core/verificacao_links.py e core/traducao.py). Nao verifica link nem
traduz nada aqui, so escreve o que recebe."""
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.worksheet.datavalidation import DataValidation

from buscador.core.verificacao_links import COR

COLUNAS = ["titulo_original", "titulo_pt", "autor", "ano", "link", "tipo",
           "status_link", "explicacao", "fonte", "provedor", "dominio_publico",
           "avaliacao_humana"]
OPCOES_AVALIACAO = ["Aprovar", "Rejeitar", "Talvez / rever", "Já no acervo", "Duplicado"]
LARGURAS = {
    "titulo_original": 40, "titulo_pt": 40, "autor": 20, "ano": 8, "link": 50,
    "tipo": 14, "status_link": 20, "explicacao": 60, "fonte": 25, "provedor": 20,
    "dominio_publico": 14, "avaliacao_humana": 16,
}
LINHAS_EXTRAS_DROPDOWN = 1000  # espaco a mais no dropdown, pra quem for preencher linhas novas a mao


def gerar_planilha(itens, caminho_saida, nome_aba="Links"):
    caminho_saida = Path(caminho_saida)
    wb = Workbook()
    ws = wb.active
    ws.title = nome_aba

    ws.append(COLUNAS)
    for celula in ws[1]:
        celula.font = Font(bold=True, color="FFFFFF")
        celula.fill = PatternFill("solid", fgColor="1F3864")

    for item in itens:
        ws.append(_linha_de_item(item))
        categoria = item.extra.get("categoria")
        if categoria in COR:
            fill = COR[categoria]
            for coluna in range(1, len(COLUNAS) + 1):
                ws.cell(row=ws.max_row, column=coluna).fill = fill

    for indice, nome_coluna in enumerate(COLUNAS, start=1):
        letra = ws.cell(row=1, column=indice).column_letter
        ws.column_dimensions[letra].width = LARGURAS.get(nome_coluna, 20)

    _aplicar_dropdown_avaliacao(ws)
    ws.freeze_panes = "A2"

    caminho_saida.parent.mkdir(parents=True, exist_ok=True)
    wb.save(caminho_saida)
    return caminho_saida


def _linha_de_item(item):
    return [
        item.titulo_original, item.titulo_pt, item.autor, item.ano, item.link,
        item.tipo, item.status_link, item.explicacao, item.fonte, item.provedor,
        item.dominio_publico, item.avaliacao_humana,
    ]


def _aplicar_dropdown_avaliacao(ws):
    formula = '"{}"'.format(",".join(OPCOES_AVALIACAO))
    validacao = DataValidation(type="list", formula1=formula, allow_blank=True)
    ws.add_data_validation(validacao)
    coluna = COLUNAS.index("avaliacao_humana") + 1
    letra = ws.cell(row=1, column=coluna).column_letter
    ultima_linha = max(ws.max_row, 2) + LINHAS_EXTRAS_DROPDOWN
    validacao.add(f"{letra}2:{letra}{ultima_linha}")
