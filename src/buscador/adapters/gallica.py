# -*- coding: utf-8 -*-
"""Adaptador para a API SRU da Gallica (BnF) -- oficialmente documentada em
api.bnf.fr para uso programatico, sem chave. Mesmo assim, seguimos a regra
de raspagem educada (secao 7 do CLAUDE.md): 1 requisicao por vez, intervalo
entre elas, User-Agent honesto -- por isso usa ClienteEducado, como o
PhpbbAdapter, e nao httpx (diferente da DDB, aqui nao ha documentacao de
que "ir rapido" seja bem-vindo).

Confirmado ao vivo pelo Samuel (nao e so documentacao lida por mim):
endpoint, parametros e formato de resposta abaixo. maximumRecords vai de
0 a 50 (limite documentado pela BnF).
"""
from urllib.parse import urlencode
import xml.etree.ElementTree as ET

from buscador.adapters.base import Item, SiteAdapter
from buscador.core.http_educado import ClienteEducado

USER_AGENT = (
    "BuscadorBaixador-InstitutoSaoBento/0.1 "
    "(uso não comercial, preservação de obras; contato: artesacra.quotidianus@gmail.com)"
)
API_BASE = "https://gallica.bnf.fr/SRU"
MAXIMO_POR_PAGINA = 50  # limite documentado pela BnF

_TERMOS_DOMINIO_PUBLICO = ("domaine public", "domaine publique", "public domain")


class GallicaAdapter(SiteAdapter):
    nome = "Gallica (BnF)"

    # Na pratica (testado ao vivo), a Gallica devolve 429 entre paginas com o
    # intervalo padrao de 2s do ClienteEducado -- ela pede mais espaco que o
    # forum do Grand Sud. Mesmo assim, uma segunda pagina pode esbarrar num
    # limite por COTA acumulada (nao so por intervalo) -- por isso os padroes
    # abaixo buscam tudo numa unica pagina sempre que der (ate 50, o maximo
    # documentado pela BnF), evitando paginar sem necessidade.
    INTERVALO_SEGUNDOS = 6.0

    def __init__(self, consulta, cliente=None, max_resultados=MAXIMO_POR_PAGINA,
                 tamanho_pagina=MAXIMO_POR_PAGINA, startrecord_inicial=1):
        self.consulta = consulta
        self.cliente = cliente or ClienteEducado(USER_AGENT, intervalo_segundos=self.INTERVALO_SEGUNDOS)
        self.max_resultados = max_resultados
        self.tamanho_pagina = min(tamanho_pagina, MAXIMO_POR_PAGINA)
        self.startrecord_inicial = startrecord_inicial  # permite retomar de onde parou (coleta longa)
        self.total_ultima_busca = None  # numberOfRecords da ultima chamada -- so informativo

    def iter_itens(self):
        for _inicio_pagina, itens_pagina in self.iter_paginas():
            yield from itens_pagina

    def iter_paginas(self):
        """Gera (inicio_da_pagina, [itens_da_pagina]) -- uma pagina inteira
        de cada vez, em vez de um fluxo achatado de itens. Usado pela coleta
        longa (core/coleta_gallica.py) pra so avancar o checkpoint depois
        que uma pagina inteira foi processada com sucesso."""
        inicio = self.startrecord_inicial  # SRU pagina a partir de 1, nao de 0
        total = None
        while inicio <= self.max_resultados and (total is None or inicio <= total):
            raiz = self._buscar_pagina(inicio, self.tamanho_pagina)
            if total is None:
                total = _texto_como_int(raiz, "numberOfRecords")
                self.total_ultima_busca = total
            registros = _elementos_por_nome_local(raiz, "record")
            if not registros:
                return
            itens_pagina = [self._item_de_registro(registro) for registro in registros]
            yield inicio, itens_pagina
            inicio += len(registros)

    def _buscar_pagina(self, start_record, maximum_records):
        params = {
            "operation": "searchRetrieve",
            "version": "1.2",
            "query": self.consulta,
            "maximumRecords": maximum_records,
            "startRecord": start_record,
        }
        url = f"{API_BASE}?{urlencode(params)}"
        resposta = self.cliente.get(url)
        return ET.fromstring(resposta.text)

    def _item_de_registro(self, registro):
        titulo = _texto_local(registro, "title")
        autor = _texto_local(registro, "creator") or _texto_local(registro, "contributor")
        ano = _texto_local(registro, "date")
        idioma = _texto_local(registro, "language")
        editora = _texto_local(registro, "publisher")
        descricao = _texto_local(registro, "description")
        direitos = _texto_local(registro, "rights")
        link = _texto_local(registro, "link") or _texto_local(registro, "identifier")
        tipo_doc = _texto_local(registro, "typedoc")

        return Item(
            titulo_original=titulo,
            link=link,
            autor=autor,
            ano=ano,
            explicacao=descricao,
            fonte=editora or self.nome,
            provedor=self.nome,
            dominio_publico=_dominio_publico(direitos),
            url_pagina=link,
            extra={"idioma_origem": _idioma_iso(idioma), "tipo_doc": tipo_doc},
        )


def _elementos_por_nome_local(elemento, nome_local):
    """Acha elementos pelo nome, ignorando o prefixo de namespace (srw:record,
    dc:title, etc.) -- mais simples que declarar todos os namespaces exatos."""
    return [e for e in elemento.iter() if e.tag.rsplit("}", 1)[-1] == nome_local]


def _texto_local(elemento, nome_local):
    achados = _elementos_por_nome_local(elemento, nome_local)
    return (achados[0].text or "").strip() if achados and achados[0].text else ""


def _texto_como_int(elemento, nome_local):
    texto = _texto_local(elemento, nome_local)
    return int(texto) if texto.isdigit() else 0


def _dominio_publico(texto_direitos):
    texto = (texto_direitos or "").lower()
    return "Sim" if any(t in texto for t in _TERMOS_DOMINIO_PUBLICO) else "Não"


_MAPA_IDIOMA = {
    "fre": "fr", "fra": "fr", "français": "fr", "lat": "la", "latin": "la",
    "eng": "en", "gre": "el", "grc": "el", "greek": "el", "grec": "el",
}


def _idioma_iso(idioma):
    return _MAPA_IDIOMA.get((idioma or "").strip().lower(), "fr")
