# -*- coding: utf-8 -*-
from buscador.adapters.base import Item
from buscador.core import enriquecimento


def test_enriquecer_item_preenche_status_tipo_e_titulo_pt(monkeypatch):
    monkeypatch.setattr(enriquecimento, "analisar", lambda link: ("vivo (pdf direto)", "verde"))
    monkeypatch.setattr(enriquecimento, "traduzir",
                         lambda texto, idioma_origem="auto", idioma_destino="pt": f"{texto} (PT)")

    item = Item(titulo_original="Algebra", link="https://exemplo.com/a.pdf",
                extra={"idioma_origem": "la"})
    resultado = enriquecimento.enriquecer_item(item)

    assert resultado is item  # muda o item recebido, nao cria um novo
    assert resultado.status_link == "vivo (pdf direto)"
    assert resultado.tipo != ""
    assert resultado.extra["categoria"] == "verde"
    assert resultado.titulo_pt == "Algebra (PT)"
