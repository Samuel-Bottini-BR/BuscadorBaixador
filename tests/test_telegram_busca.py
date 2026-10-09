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


# --- listar (fatia 2) ----------------------------------------------------
from datetime import datetime, timezone
from types import SimpleNamespace

from telethon.tl.functions.messages import SearchRequest
from telethon.tl.types import (
    Document,
    DocumentAttributeFilename,
    DocumentAttributeSticker,
    InputStickerSetEmpty,
    MessageMediaDocument,
)

from buscador.core.telegram_busca import listar_arquivos, montar_lista_tdl


def msg_doc(id_, nome=None, mime="application/pdf", tamanho=1000, figurinha=False):
    atributos = []
    if nome:
        atributos.append(DocumentAttributeFilename(nome))
    if figurinha:
        atributos.append(DocumentAttributeSticker(alt="", stickerset=InputStickerSetEmpty()))
    doc = Document(id=900 + id_, access_hash=0, file_reference=b"", date=None,
                   mime_type=mime, size=tamanho, dc_id=1, attributes=atributos)
    return SimpleNamespace(id=id_, media=MessageMediaDocument(document=doc),
                           message=f"legenda {id_}",
                           date=datetime(2025, 3, 12, tzinfo=timezone.utc))


class ClienteBusca(ClienteFalso):
    """Servidor de mentira com 250 mensagens com arquivo (ids 1..250),
    devolvidas da mais nova para a mais antiga, respeitando offset_id."""

    def __init__(self):
        super().__init__()
        self.todas = [msg_doc(i, f"livro_{i}.pdf") for i in range(250, 0, -1)]

    async def __call__(self, pedido):
        self.pedidos.append(pedido)
        if isinstance(pedido, SearchRequest):
            antes = [m for m in self.todas if not pedido.offset_id or m.id < pedido.offset_id]
            return SimpleNamespace(messages=antes[: pedido.limit])
        return await super().__call__(pedido)


def test_lista_todas_as_paginas_com_topico():
    cliente = ClienteBusca()
    paginas = []
    mensagens = asyncio.run(listar_arquivos(
        cliente, 2136545743, 81988, ao_receber_pagina=lambda p, n: paginas.append((p, n))))
    assert len(mensagens) == 250
    assert paginas == [(1, 100), (2, 200), (3, 250)]
    buscas = [p for p in cliente.pedidos if isinstance(p, SearchRequest)]
    assert [b.offset_id for b in buscas] == [0, 151, 51, 1]  # 4º pedido volta vazio
    assert all(b.top_msg_id == 81988 for b in buscas)
    assert all(isinstance(b.filter, InputMessagesFilterDocument) for b in buscas)


def test_formato_do_tdl_sem_figurinhas_e_em_ordem():
    mensagens = [
        msg_doc(30, "Summa.pdf", tamanho=5000),
        msg_doc(20, None, mime="application/epub+zip"),
        msg_doc(10, "x.webp", mime="image/webp", figurinha=True),
    ]
    lista = montar_lista_tdl(2136545743, mensagens)
    assert lista["id"] == 2136545743
    assert [m["id"] for m in lista["messages"]] == [20, 30]
    summa = lista["messages"][1]
    assert summa["type"] == "message"
    assert summa["file"] == "Summa.pdf"
    assert summa["date"] == int(datetime(2025, 3, 12, tzinfo=timezone.utc).timestamp())
    doc = summa["raw"]["Media"]["Document"]
    assert doc == {"MimeType": "application/pdf", "Size": 5000,
                   "Attributes": [{"FileName": "Summa.pdf"}]}
    sem_nome = lista["messages"][0]
    assert sem_nome["file"] == "920.epub"  # "<id do documento>.<extensão>", como o tdl


# --- conversa sem tópicos / outros tipos de conversa -----------------------------

def test_conversa_sem_topico_nao_manda_top_msg_id():
    cliente = ClienteBusca()
    asyncio.run(contar_arquivos(cliente, 2136545743, None))
    mensagens = asyncio.run(listar_arquivos(cliente, 2136545743, None))
    assert len(mensagens) == 250
    assert all(p.top_msg_id is None for p in cliente.pedidos)


def test_pedido_sem_topico_vira_bytes_sem_o_campo():
    """top_msg_id é opcional no Telegram: com None, o campo nem é enviado
    (o pedido fica 4 bytes menor que com um número de tópico)."""
    from telethon.tl.types import InputPeerEmpty
    sem = GetSearchCountersRequest(peer=InputPeerEmpty(), filters=[], top_msg_id=None)
    com = GetSearchCountersRequest(peer=InputPeerEmpty(), filters=[], top_msg_id=81988)
    assert len(bytes(com)) - len(bytes(sem)) == 4


def test_grupo_pequeno_usa_peer_chat():
    from telethon.tl.types import PeerChat

    class ClienteChat(ClienteFalso):
        async def get_input_entity(self, peer):
            assert isinstance(peer, PeerChat)
            return f"chat-{peer.chat_id}"

    cliente = ClienteChat()
    asyncio.run(contar_arquivos(cliente, 55, None, tipo="grupo"))
    assert cliente.pedidos[0].peer == "chat-55"
