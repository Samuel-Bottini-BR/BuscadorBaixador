# -*- coding: utf-8 -*-
import pytest

from buscador.adapters.base import Item, SiteAdapter


def test_site_adapter_e_abstrato():
    with pytest.raises(TypeError):
        SiteAdapter()


def test_descrever_junta_nome_secao_titulo():
    class AdapterFake(SiteAdapter):
        nome = "Fonte Fake"

        def iter_itens(self):
            return iter(())

    item = Item(titulo_original="Obra X", link="https://exemplo.com", secao="Matematica")
    assert AdapterFake().descrever(item) == "Fonte Fake > Matematica: Obra X"


def test_descrever_sem_secao():
    class AdapterFake(SiteAdapter):
        nome = "Fonte Fake"

        def iter_itens(self):
            return iter(())

    item = Item(titulo_original="Obra X", link="https://exemplo.com")
    assert AdapterFake().descrever(item) == "Fonte Fake: Obra X"


def test_item_tem_valores_padrao_vazios():
    item = Item(titulo_original="Obra X", link="https://exemplo.com")
    assert item.titulo_pt == ""
    assert item.avaliacao_humana == ""
    assert item.extra == {}
