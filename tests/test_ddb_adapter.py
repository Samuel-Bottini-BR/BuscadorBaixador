# -*- coding: utf-8 -*-
import json
import pathlib

import httpx
import pytest

from buscador.adapters.ddb import DdbAdapter, DdbApiError, _idioma_iso, _primeiro

FIXTURE = json.loads((pathlib.Path(__file__).parent / "fixtures" / "ddb" / "busca_clavius.json").read_text(encoding="utf-8"))
DOCS = FIXTURE["response"]["docs"]


def _cliente_com_handler(handler):
    transporte = httpx.MockTransport(handler)
    return httpx.Client(base_url="https://api.deutsche-digitale-bibliothek.de", transport=transporte)


def test_primeiro_lida_com_lista_e_valor_solto():
    assert _primeiro(["a", "b"]) == "a"
    assert _primeiro([]) == ""
    assert _primeiro("solto") == "solto"
    assert _primeiro(None) == ""


def test_idioma_iso_conhecido_e_desconhecido():
    assert _idioma_iso("Latin") == "la"
    assert _idioma_iso("German") == "de"
    assert _idioma_iso("Klingon") == "de"  # padrao


def test_item_de_registro_mapeia_campos():
    adapter = DdbAdapter("Christophori Clavii", api_key="chave-teste")
    item = adapter._item_de_registro(DOCS[0])
    assert item.titulo_original == "Algebra Christophori Clavii"
    assert item.autor == "Christophorus Clavius"
    assert item.fonte == "Max-Planck-Institut für Wissenschaftsgeschichte"
    assert item.ano == "1608"
    assert item.link == "https://www.deutsche-digitale-bibliothek.de/item/G5ZN3SJPJ4MQKERNGUAK32IWF52R7PIH"
    assert item.extra["idioma_origem"] == "la"


def test_busca_uma_pagina_so_quando_cabe_tudo():
    chamadas = []

    def handler(request):
        chamadas.append(dict(request.url.params))
        return httpx.Response(200, json=FIXTURE)

    cliente = _cliente_com_handler(handler)
    adapter = DdbAdapter("Christophori Clavii", api_key="chave-teste", cliente=cliente, tamanho_pagina=20)
    itens = list(adapter.iter_itens())

    assert len(itens) == 3
    assert len(chamadas) == 1
    assert chamadas[0]["oauth_consumer_key"] == "chave-teste"
    assert chamadas[0]["query"] == "Christophori Clavii"


def test_pagina_por_offset_ate_esgotar():
    def handler(request):
        offset = int(request.url.params["offset"])
        rows = int(request.url.params["rows"])
        pagina_docs = DOCS[offset:offset + rows]
        return httpx.Response(200, json={"response": {"numFound": len(DOCS), "start": offset, "docs": pagina_docs}})

    cliente = _cliente_com_handler(handler)
    adapter = DdbAdapter("Christophori Clavii", api_key="chave-teste", cliente=cliente, tamanho_pagina=2)
    itens = list(adapter.iter_itens())

    assert len(itens) == 3  # 2 na primeira pagina + 1 na segunda
    assert itens[0].titulo_original == "Algebra Christophori Clavii"
    assert itens[2].titulo_original == "Christophori Clavii Epitome Arithmeticae Practicae"


def test_respeita_max_resultados():
    def handler(request):
        offset = int(request.url.params["offset"])
        rows = int(request.url.params["rows"])
        pagina_docs = DOCS[offset:offset + rows]
        return httpx.Response(200, json={"response": {"numFound": len(DOCS), "start": offset, "docs": pagina_docs}})

    cliente = _cliente_com_handler(handler)
    adapter = DdbAdapter("Christophori Clavii", api_key="chave-teste", cliente=cliente,
                          tamanho_pagina=1, max_resultados=2)
    itens = list(adapter.iter_itens())
    assert len(itens) == 2


def test_status_diferente_de_200_levanta_erro():
    def handler(request):
        return httpx.Response(401, text='{"name":"NotAuthorizedException"}')

    cliente = _cliente_com_handler(handler)
    adapter = DdbAdapter("Christophori Clavii", api_key="chave-errada", cliente=cliente)
    with pytest.raises(DdbApiError):
        list(adapter.iter_itens())


def test_sem_resultados_nao_quebra():
    def handler(request):
        return httpx.Response(200, json={"response": {"numFound": 0, "start": 0, "docs": []}})

    cliente = _cliente_com_handler(handler)
    adapter = DdbAdapter("nada-encontrado", api_key="chave-teste", cliente=cliente)
    assert list(adapter.iter_itens()) == []
