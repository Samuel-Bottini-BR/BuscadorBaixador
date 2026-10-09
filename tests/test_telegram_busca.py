# -*- coding: utf-8 -*-
import asyncio

from telethon.tl.functions.messages import GetSearchCountersRequest
from telethon.tl.types import (
    InputMessagesFilterDocument,
    InputMessagesFilterPhotos,
    InputMessagesFilterRoundVideo,
)
from telethon.tl.types.messages import SearchCounter

from buscador.core.telegram_busca import FILTROS, contar_arquivos, traduzir_contadores


def test_traduz_para_portugues():
    resposta = [
        SearchCounter(InputMessagesFilterDocument(), 353),
        SearchCounter(InputMessagesFilterPhotos(), 733),
    ]
    assert traduzir_contadores(resposta) == {
        "documentos (PDF, EPUB, RAR...)": 353,
        "fotos": 733,
    }


def test_filtro_desconhecido_usa_nome_tecnico():
    resposta = [SearchCounter(InputMessagesFilterRoundVideo(), 2)]
    assert traduzir_contadores(resposta) == {"InputMessagesFilterRoundVideo": 2}


class ClienteFalso:
    """Imita o Telethon: só 'conhece' o grupo depois de get_dialogs() se
    conhece_grupo=False; guarda os pedidos feitos ao servidor."""

    def __init__(self, conhece_grupo=True):
        self.conhece_grupo = conhece_grupo
        self.carregou_conversas = False
        self.pedidos = []

    async def get_input_entity(self, peer):
        if not self.conhece_grupo:
            raise ValueError("Could not find the input entity")
        return f"grupo-{peer.channel_id}"

    async def get_dialogs(self):
        self.carregou_conversas = True
        self.conhece_grupo = True

    async def __call__(self, pedido):
        self.pedidos.append(pedido)
        return [SearchCounter(InputMessagesFilterDocument(), 353)]


def test_pergunta_ao_servidor_com_topico_e_filtros():
    cliente = ClienteFalso()
    resultado = asyncio.run(contar_arquivos(cliente, 2136545743, 81988))
    assert resultado == {"documentos (PDF, EPUB, RAR...)": 353}
    (pedido,) = cliente.pedidos  # uma única pergunta
    assert isinstance(pedido, GetSearchCountersRequest)
    assert pedido.top_msg_id == 81988
    assert pedido.peer == "grupo-2136545743"
    assert [type(f) for f in pedido.filters] == list(FILTROS)


def test_conta_nova_carrega_conversas_para_achar_o_grupo():
    cliente = ClienteFalso(conhece_grupo=False)
    asyncio.run(contar_arquivos(cliente, 2136545743, 81988))
    assert cliente.carregou_conversas
