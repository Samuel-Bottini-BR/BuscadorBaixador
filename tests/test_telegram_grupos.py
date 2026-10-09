# -*- coding: utf-8 -*-
"""Testes de core/telegram_grupos.py -- sem internet (Telethon falso)."""
import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from telethon.tl.functions.messages import GetForumTopicsRequest
from telethon.tl.types import (
    Channel,
    Chat,
    ChatPhotoEmpty,
    ForumTopic,
    ForumTopicDeleted,
    PeerChannel,
    PeerNotifySettings,
    User,
)

from buscador.core.telegram_grupos import (
    grupo_de_entidade,
    interpretar_link,
    ler_grupos,
    listar_contas,
    listar_dialogos,
    listar_topicos,
    mascarar_telefone,
    nome_para_mostrar,
    resolver_grupo,
    salvar_grupo,
    traduzir_topicos,
)

REFUGIO = Channel(id=2136545743, title="Refúgio Intelectual", photo=ChatPhotoEmpty(),
                  date=None, megagroup=True, forum=True)


def test_contas_sao_os_arquivos_session(tmp_path):
    assert listar_contas(tmp_path / "nao_existe") == []
    (tmp_path / "samuel.session").write_text("x")
    (tmp_path / "kaique.session").write_text("x")
    (tmp_path / "samuel.session-journal").write_text("x")  # arquivo auxiliar do SQLite
    assert listar_contas(tmp_path) == ["kaique", "samuel"]


def test_telefone_mascarado():
    assert mascarar_telefone("5511987654234") == "+55 •• ••••-•234"
    assert mascarar_telefone(None) == "—"


def test_salvar_grupo_acrescenta_e_atualiza_sem_perder_topicos(tmp_path):
    arquivo = tmp_path / "telegram" / "grupos.json"
    assert ler_grupos(arquivo) == []
    salvar_grupo({"chat_id": 1, "nome": "A", "forum": True, "tipo": "canal",
                  "topicos": [{"id": 783, "titulo": "Latim"}]}, arquivo)
    salvar_grupo({"chat_id": 2, "nome": "B", "forum": False, "tipo": "grupo"}, arquivo)
    salvar_grupo({"chat_id": 1, "nome": "A (novo nome)", "forum": True, "tipo": "canal"}, arquivo)
    grupos = ler_grupos(arquivo)
    assert [g["nome"] for g in grupos] == ["A (novo nome)", "B"]
    assert grupos[0]["topicos"] == [{"id": 783, "titulo": "Latim"}]


def test_nome_para_mostrar():
    assert nome_para_mostrar({"nome": "Refúgio", "forum": True, "tipo": "canal"}) == \
        "Refúgio (grupo com tópicos)"
    assert nome_para_mostrar({"nome": "Fulano", "forum": False, "tipo": "usuario"}) == \
        "Fulano (conversa)"


@pytest.mark.parametrize("texto, esperado", [
    ("https://t.me/c/2136545743/783/60824", 2136545743),
    ("t.me/c/2136545743", 2136545743),
    ("2136545743", 2136545743),
    ("-1002136545743", 2136545743),
    ("https://t.me/+AbCd_123", "https://t.me/+AbCd_123"),
    ("https://t.me/joinchat/XyZ", "https://t.me/joinchat/XyZ"),
    ("https://t.me/livros_antigos", "livros_antigos"),
    ("telegram.me/livros_antigos/15", "livros_antigos"),
    ("@livros_antigos", "livros_antigos"),
    ("  @livros_antigos  ", "livros_antigos"),
])
def test_interpretar_link(texto, esperado):
    assert interpretar_link(texto) == esperado


@pytest.mark.parametrize("texto", ["", "https://exemplo.com/x", "@ab"])
def test_link_desconhecido_explica(texto):
    with pytest.raises(ValueError, match="Não reconheci"):
        interpretar_link(texto)


def test_grupo_de_entidade():
    assert grupo_de_entidade(REFUGIO) == {
        "chat_id": 2136545743, "nome": "Refúgio Intelectual", "forum": True, "tipo": "canal"}
    chat = Chat(id=55, title="Grupinho", photo=ChatPhotoEmpty(), participants_count=3,
                date=None, version=1)
    assert grupo_de_entidade(chat)["tipo"] == "grupo"
    pessoa = User(id=7, first_name="Fulano", last_name="de Tal")
    assert grupo_de_entidade(pessoa) == {"chat_id": 7, "nome": "Fulano de Tal",
                                         "forum": False, "tipo": "usuario"}


class ClienteFalso:
    """Imita só o que o telegram_grupos usa do Telethon."""

    def __init__(self, topicos=()):
        self.topicos = list(topicos)
        self.pedidos = []
        self.pedidos_entidade = []

    async def get_input_entity(self, peer):
        return f"entrada-{peer.channel_id}"

    async def get_dialogs(self):
        pass

    async def get_entity(self, alvo):
        self.pedidos_entidade.append(alvo)
        if alvo in ("entrada-2136545743", "refugio"):
            return REFUGIO
        raise ValueError("No user has that username")

    async def iter_dialogs(self):
        pessoa = User(id=7, first_name="Fulano")
        for entidade, grupo, canal in [(REFUGIO, True, False), (pessoa, False, False)]:
            yield SimpleNamespace(entity=entidade, is_group=grupo, is_channel=canal)

    async def __call__(self, pedido):
        """Servidor de tópicos de mentira: devolve 'limit' tópicos depois
        de offset_topic (na ordem da lista)."""
        self.pedidos.append(pedido)
        assert isinstance(pedido, GetForumTopicsRequest)
        ids = [t.id for t in self.topicos]
        inicio = ids.index(pedido.offset_topic) + 1 if pedido.offset_topic else 0
        pagina = self.topicos[inicio:inicio + pedido.limit]
        mensagens = [SimpleNamespace(id=t.top_message, date=datetime(2025, 1, t.id % 28 + 1,
                                                                     tzinfo=timezone.utc))
                     for t in pagina if isinstance(t, ForumTopic)]
        return SimpleNamespace(count=len(self.topicos), topics=pagina, messages=mensagens)


def topico(id_, titulo):
    return ForumTopic(id=id_, date=None, peer=PeerChannel(1), title=titulo, icon_color=0,
                      top_message=id_ + 1000, read_inbox_max_id=0, read_outbox_max_id=0,
                      unread_count=0, unread_mentions_count=0, unread_reactions_count=0,
                      unread_poll_votes_count=0, from_id=PeerChannel(1),
                      notify_settings=PeerNotifySettings())


def test_traduzir_topicos_pula_apagados():
    resposta = SimpleNamespace(topics=[topico(783, "Latim"), ForumTopicDeleted(id=9)])
    assert traduzir_topicos(resposta) == [{"id": 783, "titulo": "Latim"}]


def test_listar_topicos_paginado():
    todos = [topico(i, f"Tópico {i}") for i in range(1, 251)]
    cliente = ClienteFalso(todos)
    resultado = asyncio.run(listar_topicos(cliente, 2136545743))
    assert len(resultado) == 250
    assert resultado[0] == {"id": 1, "titulo": "Tópico 1"}
    assert [p.offset_topic for p in cliente.pedidos] == [0, 100, 200]
    segundo = cliente.pedidos[1]
    assert segundo.offset_id == 1100  # a última mensagem do tópico 100
    assert segundo.offset_date is not None
    assert all(p.peer == "entrada-2136545743" for p in cliente.pedidos)


def test_listar_topicos_para_se_a_pagina_nao_anda():
    class Teimoso(ClienteFalso):
        async def __call__(self, pedido):
            self.pedidos.append(pedido)
            return SimpleNamespace(count=999, topics=[topico(1, "A")], messages=[])
    cliente = Teimoso()
    assert asyncio.run(listar_topicos(cliente, 1)) == [{"id": 1, "titulo": "A"}]
    assert len(cliente.pedidos) == 2  # o 2º veio repetido -> parou


def test_listar_dialogos_so_grupos_e_canais():
    grupos = asyncio.run(listar_dialogos(ClienteFalso()))
    assert [g["nome"] for g in grupos] == ["Refúgio Intelectual"]


def test_resolver_grupo_por_link_de_mensagem_e_por_nome():
    cliente = ClienteFalso()
    assert asyncio.run(resolver_grupo(cliente, "https://t.me/c/2136545743/783/1"))["forum"]
    assert asyncio.run(resolver_grupo(cliente, "@refugio"))["chat_id"] == 2136545743


def test_resolver_grupo_desconhecido_explica():
    with pytest.raises(ValueError, match="participa do grupo"):
        asyncio.run(resolver_grupo(ClienteFalso(), "@outro_grupo"))
