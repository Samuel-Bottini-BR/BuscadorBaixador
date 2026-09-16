# -*- coding: utf-8 -*-
import json
from unittest.mock import MagicMock
from urllib.parse import parse_qs, urlparse

from buscador.adapters.internet_archive import (
    InternetArchiveAdapter,
    MetodoApiInternetArchive,
)

DOC_LIVRE = {
    "identifier": "ellesmere-pride-and-prejudice",
    "title": "Ellesmere Pride And Prejudice",
    "creator": "Ross G. Arthur",
    "date": "2025-01-01T00:00:00Z",
    "language": "English",
    "publisher": "",
}

DOC_RESTRITO = {
    "identifier": "algumlivroemprestimo",
    "title": "Um Livro de Empréstimo",
    "creator": "Fulano de Tal",
    "date": "1950-01-01T00:00:00Z",
    "language": "por",
    "licenseurl": "",
    "access-restricted-item": True,
}

DOC_DOMINIO_PUBLICO = {
    "identifier": "obraantiga",
    "title": "Obra Antiga",
    "creator": "Fulano",
    "date": "1800-01-01T00:00:00Z",
    "language": "fre",
    "licenseurl": "http://creativecommons.org/publicdomain/mark/1.0/",
}


def _resposta(docs):
    r = MagicMock()
    r.text = json.dumps({"response": {"numFound": len(docs), "docs": docs}})
    return r


def _cliente_fake(docs):
    """Simula o comportamento real da API: a pagina 1 devolve os docs
    pedidos, qualquer pagina depois disso devolve vazio (sinal real de
    'acabaram os resultados') -- diferente de so usar return_value, que
    devolveria a mesma pagina pra sempre e nunca pararia o laco."""
    cliente = MagicMock()

    def get(url):
        parametros = parse_qs(urlparse(url).query)
        pagina = int(parametros["page"][0])
        return _resposta(docs if pagina == 1 else [])

    cliente.get.side_effect = get
    return cliente


def test_extrai_itens_da_resposta():
    adapter = MetodoApiInternetArchive("subject:theology", cliente=_cliente_fake([DOC_LIVRE]))
    itens = list(adapter.iter_itens())
    assert len(itens) == 1
    assert itens[0].titulo_original == "Ellesmere Pride And Prejudice"
    assert itens[0].link == "https://archive.org/details/ellesmere-pride-and-prejudice"
    assert itens[0].url_pagina == itens[0].link
    assert itens[0].autor == "Ross G. Arthur"
    assert itens[0].ano == "2025"
    assert itens[0].provedor == "Internet Archive"
    assert itens[0].extra["idioma_origem"] == "en"


def test_item_restrito_fica_marcado_mas_nao_trava_a_coleta():
    adapter = MetodoApiInternetArchive("qualquer", cliente=_cliente_fake([DOC_RESTRITO]))
    itens = list(adapter.iter_itens())
    assert len(itens) == 1
    assert itens[0].extra["access_restricted"] is True
    assert itens[0].extra["idioma_origem"] == "pt"


def test_item_sem_marcacao_de_restricao_fica_false():
    adapter = MetodoApiInternetArchive("qualquer", cliente=_cliente_fake([DOC_LIVRE]))
    item = list(adapter.iter_itens())[0]
    assert item.extra["access_restricted"] is False


def test_dominio_publico_so_marca_sim_com_licenca_explicita():
    adapter = MetodoApiInternetArchive("qualquer", cliente=_cliente_fake([DOC_DOMINIO_PUBLICO]))
    item = list(adapter.iter_itens())[0]
    assert item.dominio_publico == "Sim"


def test_sem_licenseurl_fica_em_branco_em_vez_de_supor():
    adapter = MetodoApiInternetArchive("qualquer", cliente=_cliente_fake([DOC_LIVRE]))
    item = list(adapter.iter_itens())[0]
    assert item.dominio_publico == ""


def test_sem_idioma_nao_preenche_a_chave_idioma_origem():
    # regressao: encontrado testando ao vivo -- se a chave existisse vazia,
    # o enriquecer_item nunca cairia no "auto" (ver core/enriquecimento.py)
    doc_sem_idioma = {**DOC_LIVRE, "language": ""}
    adapter = MetodoApiInternetArchive("qualquer", cliente=_cliente_fake([doc_sem_idioma]))
    item = list(adapter.iter_itens())[0]
    assert "idioma_origem" not in item.extra


def test_sem_resultados_nao_quebra():
    adapter = MetodoApiInternetArchive("consulta-sem-resultado", cliente=_cliente_fake([]))
    assert list(adapter.iter_itens()) == []


def test_pagina_ate_max_resultados():
    chamadas = []

    def get(url):
        parametros = parse_qs(urlparse(url).query)
        pagina = int(parametros["page"][0])
        chamadas.append(pagina)
        if pagina == 1:
            return _resposta([DOC_LIVRE, DOC_RESTRITO])
        return _resposta([DOC_DOMINIO_PUBLICO])

    cliente = MagicMock()
    cliente.get.side_effect = get

    adapter = MetodoApiInternetArchive("qualquer", cliente=cliente, max_resultados=3, tamanho_pagina=2)
    itens = list(adapter.iter_itens())

    assert len(itens) == 3
    assert chamadas == [1, 2]


def test_para_quando_max_resultados_e_atingido_no_meio_da_pagina():
    cliente = _cliente_fake([DOC_LIVRE, DOC_RESTRITO, DOC_DOMINIO_PUBLICO])
    adapter = MetodoApiInternetArchive("qualquer", cliente=cliente, max_resultados=2, tamanho_pagina=10)
    itens = list(adapter.iter_itens())
    assert len(itens) == 2


def test_adapter_wrapper_usa_a_cascata_e_devolve_os_mesmos_itens():
    adapter = InternetArchiveAdapter("subject:theology", cliente=_cliente_fake([DOC_LIVRE]))
    itens = list(adapter.iter_itens())
    assert len(itens) == 1
    assert itens[0].titulo_original == "Ellesmere Pride And Prejudice"
