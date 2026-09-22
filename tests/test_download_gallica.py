# -*- coding: utf-8 -*-
from unittest.mock import MagicMock

import pytest

from buscador.core.download_gallica import descobrir_url_download, montar_url_ajax_download


def test_montar_url_ajax_download():
    url = montar_url_ajax_download("bpt6k6382082m", indice_pagina=3)
    assert url == "https://gallica.bnf.fr/services/ajax/action/download/ark:/12148/bpt6k6382082m/f3.item"


def test_descobrir_url_download_devolve_campo_downoaldurl():
    resposta = MagicMock()
    resposta.json.return_value = {"downoaldurl": "https://gallica.bnf.fr/ark:/12148/bpt6k6382082m.pdf"}
    cliente = MagicMock()
    cliente.get.return_value = resposta

    url = descobrir_url_download("bpt6k6382082m", cliente)

    assert url == "https://gallica.bnf.fr/ark:/12148/bpt6k6382082m.pdf"
    cliente.get.assert_called_once_with(
        "https://gallica.bnf.fr/services/ajax/action/download/ark:/12148/bpt6k6382082m/f1.item"
    )


def test_descobrir_url_download_acha_campo_aninhado_fundo():
    # Formato real confirmado ao vivo (Tarefa C1): o campo "downoaldurl" nao
    # vem no nivel mais alto do JSON, vem enterrado dentro da estrutura de
    # "fragmentos" da interface do visualizador da Gallica.
    resposta = MagicMock()
    resposta.json.return_value = {
        "fragment": {
            "contenu": {
                "SideBarFragment": {
                    "contenu": {
                        "DownloadFragment": {
                            "contenu": {
                                "libelles": {
                                    "downoaldurl": "https://gallica.bnf.fr/ark:/12148/bpt6k6382082m",
                                    "outraChave": "outro valor",
                                }
                            }
                        }
                    }
                }
            }
        }
    }
    cliente = MagicMock()
    cliente.get.return_value = resposta

    url = descobrir_url_download("bpt6k6382082m", cliente)

    assert url == "https://gallica.bnf.fr/ark:/12148/bpt6k6382082m"


def test_descobrir_url_download_levanta_erro_se_campo_ausente():
    resposta = MagicMock()
    resposta.json.return_value = {"outro_campo": "valor qualquer"}
    cliente = MagicMock()
    cliente.get.return_value = resposta

    with pytest.raises(ValueError):
        descobrir_url_download("bpt6k6382082m", cliente)
