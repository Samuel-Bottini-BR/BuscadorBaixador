# -*- coding: utf-8 -*-
from buscador.adapters.base import Item
from buscador.core.coleta_csv import EscritorCsvIncremental, carregar_itens_csv

ITEM_1 = Item(
    titulo_original="Algebra Christophori Clavii",
    link="https://gallica.bnf.fr/ark:/12148/bpt6k83058n",
    autor="Clavius, Christophorus (1538-1612)",
    ano="1608",
    explicacao="Tratado de algebra",
    fonte="Bibliothèque nationale de France",
    provedor="Gallica (BnF)",
    dominio_publico="Sim",
    url_pagina="https://gallica.bnf.fr/ark:/12148/bpt6k83058n",
    extra={"idioma_origem": "la", "tipo_doc": "monographie"},
)
ITEM_2 = Item(
    titulo_original="Outro livro",
    link="https://gallica.bnf.fr/ark:/12148/outro",
    autor="Autor Desconhecido",
    ano="1700",
    explicacao="",
    fonte="Bibliothèque nationale de France",
    provedor="Gallica (BnF)",
    dominio_publico="Não",
    url_pagina="https://gallica.bnf.fr/ark:/12148/outro",
    extra={"idioma_origem": "fr", "tipo_doc": "monographie"},
)


def test_escreve_cabecalho_uma_vez_e_pagina_vira_linhas(tmp_path):
    caminho = tmp_path / "itens.csv"
    with EscritorCsvIncremental(caminho) as escritor:
        escritor.escrever_pagina([ITEM_1, ITEM_2])

    itens = carregar_itens_csv(caminho)
    assert len(itens) == 2
    assert itens[0].titulo_original == "Algebra Christophori Clavii"
    assert itens[0].extra == {"idioma_origem": "la", "tipo_doc": "monographie"}
    assert itens[1].dominio_publico == "Não"


def test_reabrir_o_mesmo_arquivo_acrescenta_em_vez_de_sobrescrever(tmp_path):
    caminho = tmp_path / "itens.csv"
    with EscritorCsvIncremental(caminho) as escritor:
        escritor.escrever_pagina([ITEM_1])

    # simula o programa sendo reiniciado: uma segunda instancia, mesmo arquivo
    with EscritorCsvIncremental(caminho) as escritor:
        escritor.escrever_pagina([ITEM_2])

    itens = carregar_itens_csv(caminho)
    assert len(itens) == 2
    assert [i.link for i in itens] == [ITEM_1.link, ITEM_2.link]
    # cabecalho nao pode ter sido escrito de novo no meio do arquivo
    linhas = caminho.read_text(encoding="utf-8").splitlines()
    assert linhas.count(linhas[0]) == 1


def test_conteudo_fica_visivel_no_disco_sem_fechar_o_escritor(tmp_path):
    caminho = tmp_path / "itens.csv"
    escritor = EscritorCsvIncremental(caminho)
    try:
        escritor.escrever_pagina([ITEM_1])
        conteudo = caminho.read_text(encoding="utf-8")
        assert "Algebra Christophori Clavii" in conteudo
    finally:
        escritor.fechar()


def test_carregar_itens_csv_descarta_link_repetido_mantendo_o_primeiro(tmp_path):
    caminho = tmp_path / "itens.csv"
    item_1_duplicado = Item(
        titulo_original="Versao repetida (nao deve aparecer)",
        link=ITEM_1.link,
        extra={"idioma_origem": "la", "tipo_doc": "monographie"},
    )
    with EscritorCsvIncremental(caminho) as escritor:
        escritor.escrever_pagina([ITEM_1])
        escritor.escrever_pagina([item_1_duplicado, ITEM_2])

    itens = carregar_itens_csv(caminho)
    assert len(itens) == 2
    assert itens[0].titulo_original == "Algebra Christophori Clavii"
