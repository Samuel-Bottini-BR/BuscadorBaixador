# -*- coding: utf-8 -*-
"""
Contas, grupos e tópicos do Telegram -- a parte "de dados" da tela Telegram.

A tela (app/pagina_telegram.py) só desenha botões e tabelas; tudo que dá
para testar sem abrir a tela mora aqui:
- listar_contas(): quais contas já fizeram login (um .session por conta);
- ler_grupos()/salvar_grupo(): a lista de grupos que o Samuel adicionou,
  guardada em saidas/telegram/grupos.json (saidas/ não vai pro GitHub);
- interpretar_link(): entende "https://t.me/nome", "@nome", "t.me/c/123/..."
  e devolve o que o Telethon precisa para achar o grupo;
- grupo_de_entidade(): transforma a "ficha" que o Telethon devolve
  (Channel, Chat, User) num dicionário simples {chat_id, nome, forum, tipo};
- listar_dialogos()/resolver_grupo()/listar_topicos(): as perguntas ao
  servidor do Telegram (recebem o cliente pronto -- nos testes, um falso).

Nada aqui guarda senha. O grupos.json só tem número, nome e tipo do grupo.
"""
import json
import re
from pathlib import Path

from telethon.tl.functions.messages import GetForumTopicsRequest
from telethon.tl.types import Channel, Chat, ForumTopic, User

from buscador.core.config_sites import CAMINHO_PADRAO
from buscador.core.escrita_atomica import salvar_json_atomico
from buscador.core.telegram_busca import achar_grupo
from buscador.core.telegram_conta import PASTA_SESSOES

# Pasta de trabalho do Telegram (dentro de saidas/, que é gitignored).
PASTA_TELEGRAM = CAMINHO_PADRAO.parent / "saidas" / "telegram"
CAMINHO_GRUPOS = PASTA_TELEGRAM / "grupos.json"


# --- contas -----------------------------------------------------------------

def listar_contas(pasta: Path = PASTA_SESSOES) -> list[str]:
    """Nomes das contas que já têm login salvo: cada arquivo
    sessoes_telegram/<nome>.session é uma conta. Em ordem alfabética."""
    if not pasta.is_dir():
        return []
    return sorted(p.stem for p in pasta.glob("*.session"))


def mascarar_telefone(telefone: str | None) -> str:
    """'+5511987654234' -> '+55 •• ••••-•234' (mostra só o fim, como no
    rascunho da tela). Sem telefone -> '—'."""
    if not telefone:
        return "—"
    digitos = re.sub(r"\D", "", telefone)
    return f"+{digitos[:2]} •• ••••-•{digitos[-3:]}"


# --- grupos guardados -------------------------------------------------------

def ler_grupos(caminho: Path = CAMINHO_GRUPOS) -> list[dict]:
    """Lista de grupos adicionados. Arquivo ainda não existe -> lista vazia."""
    if not caminho.exists():
        return []
    return json.loads(caminho.read_text(encoding="utf-8"))


def salvar_grupo(grupo: dict, caminho: Path = CAMINHO_GRUPOS) -> list[dict]:
    """Acrescenta (ou atualiza, se o mesmo chat_id já estiver lá) um grupo
    e grava o arquivo. Devolve a lista nova.

    Ao atualizar, mantém o que já tinha sido guardado e o grupo novo não
    trouxe (ex.: a lista de tópicos já carregada)."""
    grupos = ler_grupos(caminho)
    for i, existente in enumerate(grupos):
        if existente["chat_id"] == grupo["chat_id"]:
            grupos[i] = {**existente, **grupo}
            break
    else:  # o "else" de um for roda quando o laço termina sem "break"
        grupos.append(grupo)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    salvar_json_atomico(grupos, caminho)
    return grupos


def nome_para_mostrar(grupo: dict) -> str:
    """Texto do grupo no seletor da tela: nome + que tipo de conversa é."""
    if grupo.get("forum"):
        descricao = "grupo com tópicos"
    else:
        descricao = {"canal": "grupo ou canal", "grupo": "grupo",
                     "usuario": "conversa"}.get(grupo.get("tipo"), "conversa")
    return f"{grupo['nome']} ({descricao})"


# --- links ------------------------------------------------------------------

_T_ME = r"(?:https?://)?(?:www\.)?(?:t\.me|telegram\.me|telegram\.dog)/"


def interpretar_link(texto: str):
    """Entende o que o Samuel colou e devolve:
    - um número (int) para link de mensagem/grupo privado: t.me/c/2136545743/...
      (ou o número puro, com ou sem o "-100" que alguns programas mostram);
    - o próprio link, para convite: t.me/+AbCd... ou t.me/joinchat/...;
    - o nome de usuário (texto), para t.me/nome ou @nome.
    Se não reconhecer, levanta ValueError com uma explicação."""
    texto = (texto or "").strip()
    if m := re.fullmatch(_T_ME + r"c/(\d+)(?:/.*)?", texto):
        return int(m.group(1))
    if m := re.fullmatch(r"-?(\d+)", texto):
        numero = m.group(1)
        if texto.startswith("-100"):
            numero = numero[3:]  # "-1002136545743" -> "2136545743"
        return int(numero)
    if m := re.fullmatch(_T_ME + r"(\+[\w-]+|joinchat/[\w-]+)/?", texto):
        return "https://t.me/" + m.group(1)
    if m := re.fullmatch(_T_ME + r"([A-Za-z][A-Za-z0-9_]{3,})(?:/.*)?", texto):
        return m.group(1)
    if m := re.fullmatch(r"@([A-Za-z][A-Za-z0-9_]{3,})", texto):
        return m.group(1)
    raise ValueError(
        "Não reconheci esse link. Exemplos que funcionam: https://t.me/nomedogrupo, "
        "@nomedogrupo, ou o link de uma mensagem do grupo (https://t.me/c/123456/789)."
    )


def grupo_de_entidade(entidade) -> dict:
    """A "ficha" do Telethon -> {chat_id, nome, forum, tipo}.
    - Channel: supergrupo ou canal (forum=True se tiver tópicos);
    - Chat: grupo pequeno antigo;
    - User: conversa com uma pessoa ou robô."""
    if isinstance(entidade, Channel):
        return {"chat_id": entidade.id, "nome": entidade.title,
                "forum": bool(getattr(entidade, "forum", False)), "tipo": "canal"}
    if isinstance(entidade, Chat):
        return {"chat_id": entidade.id, "nome": entidade.title, "forum": False, "tipo": "grupo"}
    if isinstance(entidade, User):
        nome = " ".join(p for p in (entidade.first_name, entidade.last_name) if p)
        return {"chat_id": entidade.id, "nome": nome or str(entidade.id),
                "forum": False, "tipo": "usuario"}
    raise ValueError(f"Tipo de conversa desconhecido: {type(entidade).__name__}")


# --- perguntas ao servidor ----------------------------------------------------

async def resolver_grupo(cliente, texto: str) -> dict:
    """Acha no Telegram o grupo do link colado. A conta precisa já ser
    membro (o programa não entra em grupo nenhum sozinho)."""
    alvo = interpretar_link(texto)
    try:
        if isinstance(alvo, int):
            entrada = await achar_grupo(cliente, alvo, "canal")
            entidade = await cliente.get_entity(entrada)
        else:
            entidade = await cliente.get_entity(alvo)
    except (ValueError, TypeError) as erro:
        raise ValueError(
            "Não achei esse grupo com esta conta. Confira o link e se a conta já "
            "participa do grupo (entre nele pelo celular primeiro)."
        ) from erro
    return grupo_de_entidade(entidade)


async def listar_dialogos(cliente) -> list[dict]:
    """Grupos, supergrupos e canais em que a conta está (conversas com
    pessoas ficam de fora). Uma pergunta ao servidor (paginada pelo Telethon)."""
    grupos = []
    async for dialogo in cliente.iter_dialogs():
        if dialogo.is_group or dialogo.is_channel:
            try:
                grupos.append(grupo_de_entidade(dialogo.entity))
            except ValueError:
                pass  # tipo estranho -- ignora em vez de quebrar a lista toda
    return grupos


def traduzir_topicos(resposta) -> list[dict]:
    """Resposta do GetForumTopics -> [{"id": 783, "titulo": "Obras em Latim"}].
    Tópicos apagados (ForumTopicDeleted, sem título) ficam de fora."""
    return [{"id": t.id, "titulo": t.title}
            for t in resposta.topics if isinstance(t, ForumTopic)]


async def listar_topicos(cliente, chat_id: int, por_pagina: int = 100) -> list[dict]:
    """Todos os tópicos de um grupo-fórum, de 100 em 100.

    Paginação do Telegram para tópicos: cada pedido diz "continue depois
    do último tópico que veio" -- informando o número dele (offset_topic),
    a última mensagem dele (offset_id) e a data dessa mensagem
    (offset_date). Para quando vier vazio ou já tivermos todos (count)."""
    grupo = await achar_grupo(cliente, chat_id, "canal")
    topicos, vistos = [], set()
    offset_date, offset_id, offset_topic = None, 0, 0
    while True:
        resposta = await cliente(GetForumTopicsRequest(
            peer=grupo, offset_date=offset_date, offset_id=offset_id,
            offset_topic=offset_topic, limit=por_pagina,
        ))
        novos = [t for t in traduzir_topicos(resposta) if t["id"] not in vistos]
        if not resposta.topics or not novos:
            break  # acabou (ou a página não andou -- evita repetir para sempre)
        for t in novos:
            vistos.add(t["id"])
            topicos.append(t)
        if len(vistos) >= resposta.count:
            break
        ultimo = resposta.topics[-1]
        offset_topic = ultimo.id
        offset_id = getattr(ultimo, "top_message", 0)
        datas = {m.id: m.date for m in resposta.messages if getattr(m, "date", None)}
        offset_date = datas.get(offset_id)
    return topicos

