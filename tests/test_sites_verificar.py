# -*- coding: utf-8 -*-
"""Testes da verificação de site novo (core/verificar_site.py), sem
internet: um "cliente falso" responde no lugar do site de verdade."""
import pytest
import requests

from buscador.core.verificar_site import (
    explicar_metodo,
    normalizar_endereco,
    verificar_site,
)


class _Resposta:
    def __init__(self, texto, status=200):
        self.text = texto
        self.status_code = status


class ClienteFalso:
    """Responde conforme um dicionário url -> (texto, código). Código >= 400
    vira HTTPError, igual ao ClienteEducado de verdade; "None" simula um
    site que nem responde. Guarda as URLs pedidas, para conferir quantos
    pedidos foram feitos."""

    def __init__(self, respostas):
        self.respostas = respostas
        self.pedidos = []

    def get(self, url):
        self.pedidos.append(url)
        texto, status = self.respostas.get(url, ("", 404))
        if status is None:
            raise requests.ConnectionError("sem resposta")
        if status >= 400:
            resposta = requests.Response()
            resposta.status_code = status
            raise requests.HTTPError(f"{status}", response=resposta)
        return _Resposta(texto, status)


ROBOTS = "https://exemplo.org/robots.txt"
OAI = "https://exemplo.org/oai?verb=Identify"
SRU = "https://exemplo.org/SRU?operation=explain&version=1.2"


def test_normalizar_endereco_poe_https_e_barra():
    assert normalizar_endereco("exemplo.org") == "https://exemplo.org/"
    assert normalizar_endereco(" https://exemplo.org/acervo ") == "https://exemplo.org/acervo"


@pytest.mark.parametrize("ruim", ["", "   ", "nao e site", "ftp://exemplo.org"])
def test_normalizar_endereco_recusa_o_que_nao_e_site(ruim):
    with pytest.raises(ValueError):
        normalizar_endereco(ruim)


def test_robots_permite_e_sem_api_sugere_html():
    cliente = ClienteFalso({ROBOTS: ("User-agent: *\nDisallow: /admin/\n", 200)})
    resultado = verificar_site("https://exemplo.org/acervo", cliente=cliente)
    assert resultado.robots_encontrado and resultado.robots_permite is True
    assert resultado.api_encontrada is None
    assert resultado.metodo_sugerido == "html" and resultado.pode_mapear
    assert len(cliente.pedidos) <= 3  # robots + no máximo 2 sondas de API
    assert "educada" in explicar_metodo(resultado)


def test_robots_proibe_tudo_nao_procura_api_e_nao_deixa_mapear():
    cliente = ClienteFalso({ROBOTS: ("User-agent: *\nDisallow: /\n", 200)})
    resultado = verificar_site("https://exemplo.org/", cliente=cliente)
    assert resultado.robots_permite is False
    assert resultado.metodo_sugerido == "proibido" and not resultado.pode_mapear
    assert cliente.pedidos == [ROBOTS]  # só leu o robots.txt; nada além


def test_robots_que_cita_nosso_robo_pelo_nome_vale():
    texto = "User-agent: BuscadorBaixador-InstitutoSaoBento\nDisallow: /\n\nUser-agent: *\nAllow: /\n"
    resultado = verificar_site("exemplo.org", cliente=ClienteFalso({ROBOTS: (texto, 200)}))
    assert resultado.metodo_sugerido == "proibido"


def test_sem_robots_404_quer_dizer_sem_restricao():
    resultado = verificar_site("exemplo.org", cliente=ClienteFalso({}))
    assert resultado.robots_encontrado is False
    assert resultado.robots_permite is True
    assert resultado.metodo_sugerido == "html"
    assert any("não tem robots.txt" in a for a in resultado.avisos)


def test_acha_api_oai_pmh():
    cliente = ClienteFalso({
        ROBOTS: ("User-agent: *\nAllow: /\n", 200),
        OAI: ('<?xml version="1.0"?><OAI-PMH xmlns="http://www.openarchives.org/OAI/2.0/">', 200),
    })
    resultado = verificar_site("exemplo.org", cliente=cliente)
    assert resultado.api_encontrada == "OAI-PMH" and resultado.url_api == OAI
    assert resultado.metodo_sugerido == "api"
    assert SRU not in cliente.pedidos  # achou na 1ª sonda, não precisou da 2ª


def test_acha_api_sru():
    cliente = ClienteFalso({
        ROBOTS: ("", 200),
        SRU: ("<srw:explainResponse>...</srw:explainResponse>", 200),
    })
    resultado = verificar_site("exemplo.org", cliente=cliente)
    assert resultado.api_encontrada == "SRU"


def test_nao_sonda_api_onde_o_robots_proibe():
    cliente = ClienteFalso({ROBOTS: ("User-agent: *\nDisallow: /oai\nDisallow: /SRU\n", 200)})
    resultado = verificar_site("exemplo.org", cliente=cliente)
    assert cliente.pedidos == [ROBOTS]
    assert resultado.metodo_sugerido == "html"


def test_robots_recusado_403_conta_como_proibido():
    resultado = verificar_site("exemplo.org", cliente=ClienteFalso({ROBOTS: ("", 403)}))
    assert resultado.metodo_sugerido == "proibido"


@pytest.mark.parametrize("status", [503, None])
def test_site_fora_do_ar_fica_indefinido(status):
    resultado = verificar_site("exemplo.org", cliente=ClienteFalso({ROBOTS: ("", status)}))
    assert resultado.metodo_sugerido == "indefinido" and not resultado.pode_mapear


def test_avisa_quando_robots_usa_curinga():
    # O caso da Gallica: "Disallow: /*?" -- o robotparser do Python não
    # entende o "*", então a tela avisa para uma pessoa conferir.
    cliente = ClienteFalso({ROBOTS: ("User-agent: *\nDisallow: /*?\n", 200)})
    resultado = verificar_site("exemplo.org", cliente=cliente)
    assert any("curingas" in a for a in resultado.avisos)


def test_le_sitemaps_do_robots_sem_pedido_extra():
    cliente = ClienteFalso({ROBOTS: ("Sitemap: https://exemplo.org/sitemap.xml\nUser-agent: *\nAllow: /\n", 200)})
    resultado = verificar_site("exemplo.org", cliente=cliente)
    assert resultado.sitemaps == ["https://exemplo.org/sitemap.xml"]
