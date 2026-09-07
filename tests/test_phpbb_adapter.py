# -*- coding: utf-8 -*-
import pathlib
from unittest.mock import MagicMock

from buscador.adapters.phpbb import PhpbbAdapter

FIXTURES = pathlib.Path(__file__).parent / "fixtures" / "grand_sud"


def _cliente_fake(html):
    cliente = MagicMock()
    resposta = MagicMock()
    resposta.text = html
    cliente.get.return_value = resposta
    return cliente


def _itens_da_pagina_1():
    html = (FIXTURES / "viewtopic_f14_t9264_p1.html").read_text(encoding="utf-8")
    url = "https://grand-sud-medieval.fr/forum/viewtopic.php?f=14&t=9264"
    adapter = PhpbbAdapter(url, cliente=_cliente_fake(html))
    return list(adapter.iter_itens())


def test_extrai_um_item_por_link_nao_por_post():
    itens = _itens_da_pagina_1()
    # 5 posts nesta pagina, mas 2 deles tem 2 links cada -> 7 itens
    assert len(itens) == 7


def test_titulo_e_secao_do_topico():
    itens = _itens_da_pagina_1()
    assert all(item.titulo_original == "Les jongleurs" for item in itens)
    assert all(item.secao == "CULTURE D'OC" for item in itens)


def test_autor_e_fonte():
    itens = _itens_da_pagina_1()
    assert itens[0].autor == "drapier"
    assert itens[0].fonte == "Grand Sud Médiéval"


def test_primeiro_link_e_o_href_nao_o_texto_truncado():
    itens = _itens_da_pagina_1()
    assert itens[0].link == (
        "http://www.persee.fr/web/revues/home/prescript/article/ccmed_0007-9731_1998_num_41_162_2717"
    )


def test_post_com_dois_links_gera_dois_itens_com_mesmo_contexto():
    itens = _itens_da_pagina_1()
    do_segundo_post = [i for i in itens if "brittlebooks" in i.link or "archive.org" in i.link]
    assert len(do_segundo_post) == 2
    assert do_segundo_post[0].explicacao == do_segundo_post[1].explicacao
    assert "Edmond Faral" in do_segundo_post[0].explicacao


def test_explicacao_nao_contem_marcadores_de_comentario_html():
    itens = _itens_da_pagina_1()
    for item in itens:
        assert "<!--" not in item.explicacao
        assert "-->" not in item.explicacao


def test_data_do_post_extraida_sem_o_comentario_html():
    itens = _itens_da_pagina_1()
    assert itens[0].extra["data_post"] == "07 Fév 2015, 17:33"


def test_idioma_origem_frances():
    itens = _itens_da_pagina_1()
    assert all(item.extra["idioma_origem"] == "fr" for item in itens)
