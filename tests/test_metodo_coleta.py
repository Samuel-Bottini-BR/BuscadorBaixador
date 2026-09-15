# -*- coding: utf-8 -*-
import pytest

from buscador.adapters.base import Item
from buscador.core.acao_humana import TIPO_CHAVE_API, TIPO_LOGIN, AcaoHumanaNecessaria
from buscador.core.metodo_coleta import MetodoColeta, coletar_em_cascata


class MetodoFalso(MetodoColeta):
    def __init__(self, nome, itens=None, disponivel=True, erro=None):
        self.nome = nome
        self._itens = itens or []
        self._disponivel = disponivel
        self._erro = erro

    def disponivel(self):
        return self._disponivel

    def iter_itens(self):
        for item in self._itens:
            yield item
        if self._erro:
            raise self._erro


def _item(titulo):
    return Item(titulo_original=titulo, link=f"https://exemplo.com/{titulo}")


def test_primeiro_disponivel_e_funciona_usa_so_ele():
    metodo_1 = MetodoFalso("um", itens=[_item("a"), _item("b")])
    metodo_2 = MetodoFalso("dois", itens=[_item("nunca-chega")])

    itens = list(coletar_em_cascata([metodo_1, metodo_2], "site-teste"))

    assert [i.titulo_original for i in itens] == ["a", "b"]


def test_primeiro_indisponivel_segundo_funciona():
    metodo_1 = MetodoFalso("um", disponivel=False)
    metodo_2 = MetodoFalso("dois", itens=[_item("a")])

    itens = list(coletar_em_cascata([metodo_1, metodo_2], "site-teste"))

    assert [i.titulo_original for i in itens] == ["a"]


def test_todos_indisponiveis_levanta_com_motivos_juntos():
    metodo_1 = MetodoFalso("um", disponivel=False)
    metodo_2 = MetodoFalso("dois", disponivel=False)

    with pytest.raises(AcaoHumanaNecessaria) as excinfo:
        list(coletar_em_cascata([metodo_1, metodo_2], "site-teste"))

    assert "um" in excinfo.value.mensagem
    assert "dois" in excinfo.value.mensagem
    assert excinfo.value.site == "site-teste"


def test_todos_falham_com_acao_humana_necessaria_junta_motivos():
    metodo_1 = MetodoFalso("um", erro=AcaoHumanaNecessaria(TIPO_CHAVE_API, "falta chave"))
    metodo_2 = MetodoFalso("dois", erro=AcaoHumanaNecessaria(TIPO_LOGIN, "falta login"))

    with pytest.raises(AcaoHumanaNecessaria) as excinfo:
        list(coletar_em_cascata([metodo_1, metodo_2], "site-teste"))

    assert excinfo.value.tipo == TIPO_LOGIN  # tipo do ultimo metodo que falhou
    assert "falta chave" in excinfo.value.mensagem
    assert "falta login" in excinfo.value.mensagem


def test_itens_produzidos_antes_de_falhar_nao_se_perdem():
    metodo_1 = MetodoFalso(
        "um",
        itens=[_item("a"), _item("b")],
        erro=AcaoHumanaNecessaria(TIPO_LOGIN, "travou no meio"),
    )
    metodo_2 = MetodoFalso("dois", itens=[_item("c")])

    itens = list(coletar_em_cascata([metodo_1, metodo_2], "site-teste"))

    # os itens do metodo 1 (antes de travar) chegaram, e o metodo 2 assumiu o resto
    assert [i.titulo_original for i in itens] == ["a", "b", "c"]


def test_lista_vazia_de_metodos_levanta_value_error():
    with pytest.raises(ValueError):
        list(coletar_em_cascata([], "site-teste"))
