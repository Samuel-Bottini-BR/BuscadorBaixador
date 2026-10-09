# -*- coding: utf-8 -*-
"""
Busca de arquivos num tópico do Telegram pelo PRÓPRIO SERVIDOR do Telegram.

Por que existe: o tdl lista um tópico lendo TODAS as mensagens (inclusive a
conversa) e só depois separa as que têm arquivo -- no tópico CHAT isso levou
~1h44. O Telegram tem comandos oficiais que já devolvem só o que interessa:
- messages.getSearchCounters: "quantos documentos/fotos/vídeos tem aqui?"
  numa única pergunta (contar_arquivos);
- messages.search com filtro: a lista em si, de 100 em 100 (listar_arquivos),
  já no formato JSON que o tdl entende para baixar (mensagem_para_tdl).
É o mesmo recurso que a aba "Arquivos" do aplicativo do Telegram usa.

Cuidado (achado da pesquisa): NÃO usar client.iter_messages(reply_to=...,
filter=...) do Telethon -- com reply_to ele ignora o filtro no servidor e
volta a ler tudo. Por isso chamamos o comando oficial diretamente.
"""
import mimetypes

from telethon.tl.functions.messages import GetSearchCountersRequest, SearchRequest
from telethon.tl.types import (
    DocumentAttributeFilename,
    DocumentAttributeSticker,
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


# Figurinhas não interessam (mesma regra do baixar_topico.sh).
MIMES_FIGURINHA = {"image/webp", "application/x-tgsticker", "video/webm"}


async def listar_arquivos(cliente, chat_id: int, topico_id: int,
                          filtro=InputMessagesFilterDocument, por_pagina: int = 100,
                          ao_receber_pagina=None):
    """Busca no servidor SÓ as mensagens com arquivo do tópico, de 100 em
    100, da mais nova para a mais antiga. Devolve a lista de mensagens.

    Paginação: cada pedido diz "me dá as próximas, antes da mensagem nº X"
    (offset_id = a última que já veio). Para quando vier uma página vazia.
    ao_receber_pagina(n_pagina, total_ate_agora) serve só pra mostrar progresso.
    Se o Telegram mandar esperar (FLOOD_WAIT), o Telethon espera sozinho."""
    grupo = await achar_grupo(cliente, chat_id)
    mensagens = []
    offset_id = 0
    pagina = 0
    while True:
        resposta = await cliente(SearchRequest(
            peer=grupo, q="", filter=filtro(),
            min_date=None, max_date=None,
            offset_id=offset_id, add_offset=0, limit=por_pagina,
            max_id=0, min_id=0, hash=0,
            top_msg_id=topico_id,
        ))
        lote = [m for m in resposta.messages if getattr(m, "media", None)]
        if not resposta.messages:
            break
        ultimo = resposta.messages[-1].id
        if offset_id and ultimo >= offset_id:
            break  # segurança: a página não andou para trás -- evita repetir para sempre
        pagina += 1
        mensagens.extend(lote)
        offset_id = ultimo
        if ao_receber_pagina:
            ao_receber_pagina(pagina, len(mensagens))
    return mensagens


def _documento(mensagem):
    return getattr(getattr(mensagem, "media", None), "document", None)


def eh_figurinha(mensagem) -> bool:
    doc = _documento(mensagem)
    if doc is None:
        return False
    return doc.mime_type in MIMES_FIGURINHA or any(
        isinstance(a, DocumentAttributeSticker) for a in doc.attributes)


def mensagem_para_tdl(mensagem) -> dict | None:
    """Uma mensagem do Telethon -> um item no MESMO formato do export do tdl
    (id, type, file, date + um pedaço do "raw" com nome/tipo/tamanho).
    Assim o baixar_topico.sh e o planilha_topico.py funcionam sem mudança.
    Devolve None para o que não for documento (ex.: foto comum)."""
    doc = _documento(mensagem)
    if doc is None:
        return None
    nome = next((a.file_name for a in doc.attributes
                 if isinstance(a, DocumentAttributeFilename)), "")
    if not nome:  # sem nome: o tdl usa "<id do documento>.<extensão>"
        nome = f"{doc.id}{mimetypes.guess_extension(doc.mime_type or '') or ''}"
    atributos = [{"FileName": nome}] if any(
        isinstance(a, DocumentAttributeFilename) for a in doc.attributes) else []
    return {
        "id": mensagem.id,
        "type": "message",
        "file": nome,
        "date": int(mensagem.date.timestamp()),
        "raw": {
            "Message": mensagem.message or "",
            "Media": {"Document": {
                "MimeType": doc.mime_type,
                "Size": doc.size,
                "Attributes": atributos,
            }},
        },
    }


def montar_lista_tdl(chat_id: int, mensagens) -> dict:
    """{"id": <grupo>, "messages": [...]} -- o formato do 'tdl dl -f'.
    Pula figurinhas; ordena da mais antiga para a mais nova."""
    itens = [mensagem_para_tdl(m) for m in mensagens if not eh_figurinha(m)]
    itens = sorted((i for i in itens if i), key=lambda i: i["id"])
    return {"id": chat_id, "messages": itens}
