# -*- coding: utf-8 -*-
"""Adaptador para a API REST da Deutsche Digitale Bibliothek (DDB) --
sucessora oficial do zvdd.de (CLAUDE.md, secao 12). Ao contrario do
fórum, aqui nao existe a mesma exigencia de "ir devagar" por educacao:
e uma API oficial, feita para consumo automatizado, sujeita apenas ao
rate-limit que a propria DDB documentar. Por isso usa httpx em vez de
requests+ClienteEducado.

Nomes de campo da resposta AINDA NAO CONFIRMADOS contra uma chamada real
(a API exige uma chave -- oauth_consumer_key -- que o Samuel ainda nao
gerou). O envelope da resposta (response.numFound / response.docs) e o
nome do parametro de autenticacao vieram de documentacao publica
(bundesAPI/ddb-api, cliente JS ddbrest) -- os nomes de campo DENTRO de
cada documento sao a melhor suposicao com base em convencoes Solr/EDM,
isolados aqui embaixo pra ajustar em um lugar so quando confirmarmos.
"""
import httpx

from buscador.adapters.base import Item, SiteAdapter
from buscador.core import config

API_BASE = "https://api.deutsche-digitale-bibliothek.de"
PARAM_AUTENTICACAO = "oauth_consumer_key"
FACET_PROVEDOR = "provider_fct"

# ID do zvdd como provedor/agregador dentro da DDB (confirmado: a pagina de
# organizacao do zvdd na DDB usa esse mesmo ID -- so a CONTAGEM de itens que
# ele entrega ainda nao foi confirmada, porque isso exige a API key).
PROVIDER_ID_ZVDD = "X6VKVOM5HGHDIQX36BI3ZKWROZTN74UX"

CAMPO_ID = "id"
CAMPO_TITULO = "title"
CAMPO_CRIADOR = "creator"
# Instituicao que digitalizou a obra (ex.: SUB Goettingen) vs. o provedor/
# agregador que entregou o item pra DDB (ex.: zvdd) sao coisas DIFERENTES --
# nomes de campo ainda nao confirmados contra uma resposta real.
CAMPO_INSTITUICAO = "dataProvider"
CAMPO_PROVEDOR = "provider"
CAMPO_ANO = "time"
CAMPO_IDIOMA = "language"

_MAPA_IDIOMA = {
    "german": "de", "deutsch": "de", "latin": "la", "latein": "la",
    "french": "fr", "français": "fr", "english": "en",
}


class DdbApiError(Exception):
    pass


class DdbAdapter(SiteAdapter):
    nome = "Deutsche Digitale Bibliothek"

    def __init__(self, consulta, api_key=None, cliente=None, max_resultados=200,
                 tamanho_pagina=20, provider_fct=None):
        self.consulta = consulta
        self.api_key = api_key or config.obter_ddb_api_key()
        self.cliente = cliente or httpx.Client(base_url=API_BASE, timeout=15.0)
        self.max_resultados = max_resultados
        self.tamanho_pagina = tamanho_pagina
        self.provider_fct = provider_fct

    def contar(self):
        """So a contagem (numFound), sem baixar nenhum item -- para checagens
        rapidas tipo "quantos itens desse provedor existem"."""
        corpo = self._buscar_pagina(0, 0)
        return corpo.get("response", {}).get("numFound", 0)

    def iter_itens(self):
        offset = 0
        while offset < self.max_resultados:
            corpo = self._buscar_pagina(offset, self.tamanho_pagina)
            resposta = corpo.get("response", {})
            docs = resposta.get("docs", [])
            if not docs:
                return
            for registro in docs:
                yield self._item_de_registro(registro)
            offset += len(docs)
            if offset >= resposta.get("numFound", 0):
                return

    def _buscar_pagina(self, offset, rows):
        params = {
            "query": self.consulta,
            "offset": offset,
            "rows": rows,
            PARAM_AUTENTICACAO: self.api_key,
        }
        if self.provider_fct:
            params[FACET_PROVEDOR] = self.provider_fct
        resposta = self.cliente.get("/search", params=params)
        if resposta.status_code != 200:
            raise DdbApiError(f"DDB respondeu {resposta.status_code}: {resposta.text[:200]}")
        return resposta.json()

    def _item_de_registro(self, registro):
        identificador = registro.get(CAMPO_ID, "")
        link = f"https://www.deutsche-digitale-bibliothek.de/item/{identificador}" if identificador else ""
        return Item(
            titulo_original=_primeiro(registro.get(CAMPO_TITULO)),
            link=link,
            autor=_primeiro(registro.get(CAMPO_CRIADOR)),
            ano=_primeiro(registro.get(CAMPO_ANO)),
            fonte=_primeiro(registro.get(CAMPO_INSTITUICAO)) or self.nome,
            provedor=_primeiro(registro.get(CAMPO_PROVEDOR)),
            url_pagina=link,
            extra={"idioma_origem": _idioma_iso(_primeiro(registro.get(CAMPO_IDIOMA)))},
        )


def _primeiro(valor):
    """Campos do Solr costumam vir como lista mesmo quando so tem um valor."""
    if isinstance(valor, list):
        return str(valor[0]) if valor else ""
    return str(valor) if valor is not None else ""


def _idioma_iso(idioma):
    return _MAPA_IDIOMA.get((idioma or "").strip().lower(), "de")
