# -*- coding: utf-8 -*-
"""
Busca de arquivos num tópico do Telegram pelo PRÓPRIO SERVIDOR do Telegram.

Por que existe: o tdl lista um tópico lendo TODAS as mensagens (inclusive a
conversa) e só depois separa as que têm arquivo -- no tópico CHAT isso levou
~1h44. O Telegram tem comandos oficiais que já devolvem só o que interessa:
- messages.getSearchCounters: "quantos documentos/fotos/vídeos tem aqui?"
  numa única pergunta (é o que esta fatia usa);
- messages.search com filtro: a lista em si (próxima fatia).
É o mesmo recurso que a aba "Arquivos" do aplicativo do Telegram usa.

Cuidado (achado da pesquisa): NÃO usar client.iter_messages(reply_to=...,
filter=...) do Telethon -- com reply_to ele ignora o filtro no servidor e
volta a ler tudo. Por isso chamamos o comando oficial diretamente.
"""
from telethon.tl.functions.messages import GetSearchCountersRequest
from telethon.tl.types import (
    InputMessagesFilterDocument,
    InputMessagesFilterMusic,
    InputMessagesFilterPhotos,
    InputMessagesFilterVideo,
    InputMessagesFilterVoice,
    PeerChannel,
)

# Cada filtro do Telegram e o nome em português que mostramos ao Samuel.
# "Documentos" inclui PDF, EPUB, RAR, ZIP... (tudo que foi enviado como arquivo).
FILTROS = {
    InputMessagesFilterDocument: "documentos (PDF, EPUB, RAR...)",
    InputMessagesFilterPhotos: "fotos",
    InputMessagesFilterVideo: "vídeos",
    InputMessagesFilterMusic: "músicas",
    InputMessagesFilterVoice: "áudios de voz",
}


def traduzir_contadores(contadores) -> dict[str, int]:
    """Transforma a resposta do Telegram (uma lista de SearchCounter) em
    {"documentos (PDF, EPUB, RAR...)": 353, "fotos": 733, ...}.
    Função pura (sem internet) -- por isso dá pra testar sozinha."""
    resultado = {}
    for c in contadores:
        nome = FILTROS.get(type(c.filter), type(c.filter).__name__)
        resultado[nome] = c.count
    return resultado


async def achar_grupo(cliente, chat_id: int):
    """Acha o grupo pelo número (ex.: 2136545743). Numa conta recém-logada
    o Telethon ainda não "conhece" o grupo; nesse caso carrega a lista de
    conversas da conta uma vez e tenta de novo."""
    try:
        return await cliente.get_input_entity(PeerChannel(chat_id))
    except ValueError:
        await cliente.get_dialogs()
        return await cliente.get_input_entity(PeerChannel(chat_id))


async def contar_arquivos(cliente, chat_id: int, topico_id: int) -> dict[str, int]:
    """Uma única pergunta ao servidor: quantos arquivos de cada tipo tem no
    tópico. top_msg_id = o número do tópico (fórum)."""
    grupo = await achar_grupo(cliente, chat_id)
    contadores = await cliente(GetSearchCountersRequest(
        peer=grupo,
        filters=[filtro() for filtro in FILTROS],
        top_msg_id=topico_id,
    ))
    return traduzir_contadores(contadores)
