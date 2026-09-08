# -*- coding: utf-8 -*-
import pathlib
import xml.etree.ElementTree as ET
from unittest.mock import MagicMock
from urllib.parse import parse_qs, urlparse

from buscador.adapters.gallica import GallicaAdapter, MAXIMO_POR_PAGINA

FIXTURE_PATH = pathlib.Path(__file__).parent / "fixtures" / "gallica" / "busca_clavius.xml"
FIXTURE_TEXTO = FIXTURE_PATH.read_text(encoding="utf-8")
_RAIZ_FIXTURE = ET.fromstring(FIXTURE_TEXTO)
_TODOS_REGISTROS = [e for e in _RAIZ_FIXTURE.iter() if e.tag.rsplit("}", 1)[-1] == "record"]


def _resposta(texto):
    r = MagicMock()
    r.text = texto
    return r


def _cliente_fake(texto_unico):
    cliente = MagicMock()
    cliente.get.return_value = _resposta(texto_unico)
    return cliente


def _xml_pagina(indice_inicio, quantidade):
    """Monta uma resposta SRU valida com um pedaco dos registros da fixture --
    simula paginacao sem precisar de um segundo arquivo de fixture."""
    fatia = _TODOS_REGISTROS[indice_inicio:indice_inicio + quantidade]
    raiz = ET.Element("{http://www.loc.gov/zing/srw/}searchRetrieveResponse")
    numero = ET.SubElement(raiz, "{http://www.loc.gov/zing/srw/}numberOfRecords")
    numero.text = str(len(_TODOS_REGISTROS))
    registros = ET.SubElement(raiz, "{http://www.loc.gov/zing/srw/}records")
    for registro in fatia:
        registros.append(registro)
    return ET.tostring(raiz, encoding="unicode")


def _itens_da_fixture(cliente=None):
    adapter = GallicaAdapter('gallica all "Clavius"', cliente=cliente or _cliente_fake(FIXTURE_TEXTO))
    return list(adapter.iter_itens())


def test_extrai_os_tres_registros_da_fixture():
    assert len(_itens_da_fixture()) == 3


def test_campos_do_primeiro_registro():
    item = _itens_da_fixture()[0]
    assert item.titulo_original == "Algebra Christophori Clavii"
    assert item.autor == "Clavius, Christophorus (1538-1612)"
    assert item.ano == "1608"
    assert item.link == "https://gallica.bnf.fr/ark:/12148/bpt6k83058n"
    assert item.fonte == "Bibliothèque nationale de France"
    assert item.provedor == "Gallica (BnF)"
    assert item.dominio_publico == "Sim"
    assert item.extra["idioma_origem"] == "la"
    assert item.extra["tipo_doc"] == "monographie"


def test_usa_contributor_quando_nao_ha_creator():
    item = _itens_da_fixture()[1]
    assert item.autor == "Clavius, Christophorus (1538-1612)"
    assert item.dominio_publico == "Sim"  # "public domain" em ingles tambem conta


def test_direitos_sem_dominio_publico_marca_nao():
    item = _itens_da_fixture()[2]
    assert item.dominio_publico == "Não"
    assert item.extra["idioma_origem"] == "fr"


def test_tamanho_pagina_nunca_passa_do_limite_da_bnf():
    adapter = GallicaAdapter("qualquer coisa", tamanho_pagina=999)
    assert adapter.tamanho_pagina == MAXIMO_POR_PAGINA


def test_paginacao_por_startrecord_ate_esgotar():
    chamadas = []

    def get(url):
        parametros = parse_qs(urlparse(url).query)
        chamadas.append(parametros)
        inicio = int(parametros["startRecord"][0]) - 1  # SRU comeca em 1
        quantidade = int(parametros["maximumRecords"][0])
        return _resposta(_xml_pagina(inicio, quantidade))

    cliente = MagicMock()
    cliente.get.side_effect = get

    adapter = GallicaAdapter('gallica all "Clavius"', cliente=cliente, tamanho_pagina=2)
    itens = list(adapter.iter_itens())

    assert len(itens) == 3  # 2 na primeira pagina + 1 na segunda
    assert len(chamadas) == 2
    assert chamadas[0]["startRecord"] == ["1"]
    assert chamadas[1]["startRecord"] == ["3"]
    assert itens[0].titulo_original == "Algebra Christophori Clavii"
    assert itens[2].titulo_original == "Correspondance sur les travaux de Clavius (étude moderne)"


def test_sem_resultados_nao_quebra():
    xml_vazio = (
        '<srw:searchRetrieveResponse xmlns:srw="http://www.loc.gov/zing/srw/">'
        "<srw:numberOfRecords>0</srw:numberOfRecords>"
        "<srw:records></srw:records>"
        "</srw:searchRetrieveResponse>"
    )
    adapter = GallicaAdapter("consulta-sem-resultado", cliente=_cliente_fake(xml_vazio))
    assert list(adapter.iter_itens()) == []
