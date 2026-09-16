# -*- coding: utf-8 -*-
"""
Gera a planilha .xlsx (o formato de arquivo do Excel) de saída da Fase 1, a
partir de uma lista de Item já "enriquecidos" (com status_link/tipo/
titulo_pt já preenchidos por quem chama -- ver core/verificacao_links.py e
core/traducao.py). Este arquivo aqui NÃO verifica link nem traduz nada --
só escreve numa planilha o que já recebeu pronto.
"""
from pathlib import Path

from openpyxl import Workbook  # biblioteca que cria/edita arquivos .xlsx sem precisar do Excel instalado
from openpyxl.styles import Font, PatternFill  # Font = estilo de texto (negrito, cor); PatternFill = cor de fundo de célula
from openpyxl.worksheet.datavalidation import DataValidation  # cria o "menu suspenso" (dropdown) numa célula

from buscador.core.verificacao_links import COR  # reaproveita as mesmas cores (vermelho/azul/verde) definidas lá

# Nomes das colunas da planilha, na ordem em que vão aparecer -- e' o
# "cabecalho" que vai virar a primeira linha do arquivo gerado.
COLUNAS = ["titulo_original", "titulo_pt", "autor", "ano", "link", "tipo",
           "status_link", "explicacao", "fonte", "provedor", "dominio_publico",
           "avaliacao_humana"]
OPCOES_AVALIACAO = ["Aprovar", "Rejeitar", "Talvez / rever", "Já no acervo", "Duplicado"]
# Largura de cada coluna, em "unidades" do Excel (não é pixel nem
# centímetro, é uma unidade própria dele, baseada mais ou menos em quantos
# caracteres cabem).
LARGURAS = {
    "titulo_original": 40, "titulo_pt": 40, "autor": 20, "ano": 8, "link": 50,
    "tipo": 14, "status_link": 20, "explicacao": 60, "fonte": 25, "provedor": 20,
    "dominio_publico": 14, "avaliacao_humana": 16,
}
LINHAS_EXTRAS_DROPDOWN = 1000  # espaco a mais no dropdown, pra quem for preencher linhas novas a mao


def gerar_planilha(itens, caminho_saida, nome_aba="Links"):
    """Função principal deste arquivo. Recebe uma lista de Item e um
    caminho de arquivo, e cria o .xlsx ali. Devolve o próprio caminho de
    volta, já confirmado (útil pra quem chamou mostrar onde salvou)."""
    caminho_saida = Path(caminho_saida)
    wb = Workbook()  # "wb" = workbook, o arquivo Excel inteiro (pode ter várias abas)
    ws = wb.active  # "ws" = worksheet, a aba que já vem criada por padrão num workbook novo
    ws.title = nome_aba  # renomeia essa aba (ex.: de "Sheet1" pra "Links")

    ws.append(COLUNAS)  # adiciona a lista de nomes de coluna como a primeira linha (cabeçalho)
    for celula in ws[1]:  # "ws[1]" pega todas as células da linha 1
        celula.font = Font(bold=True, color="FFFFFF")  # texto branco e em negrito
        celula.fill = PatternFill("solid", fgColor="1F3864")  # fundo azul-escuro

    for item in itens:
        ws.append(_linha_de_item(item))  # adiciona uma linha nova com os dados desse item
        categoria = item.extra.get("categoria")
        if categoria in COR:
            # pinta a linha inteira (todas as colunas) com a cor certa,
            # de acordo com a categoria que a verificação de link já
            # calculou (vermelho = quebrado, azul = precisa login, verde = ok)
            fill = COR[categoria]
            for coluna in range(1, len(COLUNAS) + 1):
                ws.cell(row=ws.max_row, column=coluna).fill = fill
                # "ws.max_row" é sempre a última linha adicionada -- como
                # acabamos de adicionar esse item, é a linha dele mesmo

    for indice, nome_coluna in enumerate(COLUNAS, start=1):
        # "enumerate(COLUNAS, start=1)" percorre a lista de colunas indo
        # também contando a posição de cada uma, começando em 1 (não em 0,
        # que é o padrão do Python) -- porque no Excel a primeira coluna é a "1", a coluna "A"
        letra = ws.cell(row=1, column=indice).column_letter
        # ".column_letter" traduz o número da coluna (1, 2, 3...) pra letra do Excel (A, B, C...)
        ws.column_dimensions[letra].width = LARGURAS.get(nome_coluna, 20)
        # se essa coluna não estiver no dicionário LARGURAS, usa 20 como largura padrão

    _aplicar_dropdown_avaliacao(ws)
    ws.freeze_panes = "A2"
    # "congela" a primeira linha (cabeçalho) na tela -- ao rolar a
    # planilha pra baixo, o cabeçalho continua visível no topo

    caminho_saida.parent.mkdir(parents=True, exist_ok=True)
    # garante que a pasta de destino existe antes de tentar salvar o
    # arquivo ali dentro (senão o salvamento daria erro)
    wb.save(caminho_saida)
    return caminho_saida


def _linha_de_item(item):
    """Transforma um objeto Item numa lista simples de valores, na mesma
    ordem das COLUNAS -- é isso que ws.append() espera receber."""
    return [
        item.titulo_original, item.titulo_pt, item.autor, item.ano, item.link,
        item.tipo, item.status_link, item.explicacao, item.fonte, item.provedor,
        item.dominio_publico, item.avaliacao_humana,
    ]


def _aplicar_dropdown_avaliacao(ws):
    """Cria o menu suspenso (dropdown) na coluna "avaliacao_humana", com as
    opções de OPCOES_AVALIACAO, pra você escolher clicando em vez de
    digitar."""
    formula = '"{}"'.format(",".join(OPCOES_AVALIACAO))
    # monta um texto tipo "Aprovar,Rejeitar,Talvez / rever,..." entre
    # aspas -- é o formato que o Excel espera pra descrever uma lista fixa
    # de opções permitidas numa célula
    validacao = DataValidation(type="list", formula1=formula, allow_blank=True)
    ws.add_data_validation(validacao)
    coluna = COLUNAS.index("avaliacao_humana") + 1
    # acha em que posição a coluna "avaliacao_humana" está na lista
    # COLUNAS, e soma 1 porque o Excel conta colunas a partir de 1, não de 0
    letra = ws.cell(row=1, column=coluna).column_letter
    ultima_linha = max(ws.max_row, 2) + LINHAS_EXTRAS_DROPDOWN
    # aplica o dropdown não só nas linhas já preenchidas, mas em mais 1000
    # linhas depois -- assim, se alguém adicionar uma linha nova a mão na
    # planilha depois, o menu suspenso já funciona ali também
    validacao.add(f"{letra}2:{letra}{ultima_linha}")
