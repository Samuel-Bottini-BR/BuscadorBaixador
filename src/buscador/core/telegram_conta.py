# -*- coding: utf-8 -*-
"""
Conta do Telegram usada para LISTAR arquivos (a biblioteca Telethon).

Três peças pequenas:
- ler_credenciais(): pega o api_id/api_hash do buscador.local.cfg (o
  arquivo que nunca vai pro GitHub). Se faltar, avisa o Samuel com o passo
  a passo (AcaoHumanaNecessaria), em vez de quebrar com erro feio.
- caminho_sessao(): onde fica o arquivo de login de cada conta --
  sessoes_telegram/<nome>.session. Uma conta = um arquivo, então dá pra ter
  várias contas (Samuel, Kaique...) e escolher qual usar.
- login_qr(): entra na conta mostrando um QR code para o celular escanear.
  Quem DESENHA o QR é quem chama (hoje: uma imagem PNG; no dashboard: a
  própria tela) -- por isso esta função só recebe "o que fazer com o link".

O arquivo .session vale como senha: está no .gitignore e nunca é commitado.
"""
import asyncio
import re
from pathlib import Path

from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError

from buscador.core.acao_humana import TIPO_CHAVE_API, TIPO_LOGIN, AcaoHumanaNecessaria
from buscador.core.config_sites import CAMINHO_PADRAO, ler_chave

# Pasta das sessões: na raiz do projeto, ao lado do buscador.local.cfg.
PASTA_SESSOES = CAMINHO_PADRAO.parent / "sessoes_telegram"

PASSO_A_PASSO_CHAVE = (
    "falta o api_id/api_hash do Telegram. Abra https://my.telegram.org, entre "
    "com seu número, clique em 'API development tools', crie um aplicativo "
    "(qualquer nome) e copie os dois valores para a seção [telegram] do "
    "arquivo buscador.local.cfg (veja o modelo em buscador.local.cfg.exemplo)."
)


def ler_credenciais(caminho: Path = CAMINHO_PADRAO) -> tuple[int, str]:
    """Devolve (api_id, api_hash). Se faltar algum, ou o api_id não for
    número, levanta AcaoHumanaNecessaria com o passo a passo."""
    api_id = ler_chave("telegram", "api_id", caminho=caminho)
    api_hash = ler_chave("telegram", "api_hash", caminho=caminho)
    if not api_id or not api_hash or not api_id.strip().isdigit():
        raise AcaoHumanaNecessaria(TIPO_CHAVE_API, PASSO_A_PASSO_CHAVE, site="telegram")
    return int(api_id.strip()), api_hash.strip()


def caminho_sessao(nome_conta: str, pasta: Path = PASTA_SESSOES) -> Path:
    """sessoes_telegram/<nome_conta>.session. O nome só pode ter letras,
    números, "_" e "-" -- assim ninguém escreve sem querer fora da pasta
    (ex.: um nome como "../outra_pasta")."""
    if not re.fullmatch(r"[A-Za-z0-9_-]+", nome_conta or ""):
        raise ValueError(
            f"Nome de conta inválido: {nome_conta!r}. Use só letras sem acento, "
            "números, '_' ou '-' (ex.: samuel, kaique)."
        )
    return pasta / f"{nome_conta}.session"


def criar_cliente(nome_conta: str, caminho_cfg: Path = CAMINHO_PADRAO,
                  pasta: Path = PASTA_SESSOES) -> TelegramClient:
    """Monta o cliente do Telethon para uma conta (ainda sem conectar)."""
    api_id, api_hash = ler_credenciais(caminho_cfg)
    sessao = caminho_sessao(nome_conta, pasta)
    sessao.parent.mkdir(parents=True, exist_ok=True)
    return TelegramClient(str(sessao), api_id, api_hash)


async def login_qr(cliente, mostrar_qr, pedir_senha, espera_por_qr: float = 60,
                   max_qrs: int = 5) -> None:
    """Entra na conta pelo QR code.

    - mostrar_qr(link): chamada a cada QR novo -- quem chama desenha o QR.
    - pedir_senha(): só é chamada se a conta tiver senha de duas etapas;
      a senha é usada na hora e não é guardada em lugar nenhum.
    Cada QR vale ~1 minuto; se ninguém escanear, gera outro (até max_qrs).
    """
    if await cliente.is_user_authorized():
        return  # já está logado nesta conta -- nada a fazer
    qr = await cliente.qr_login()
    for _ in range(max_qrs):
        mostrar_qr(qr.url)
        try:
            await qr.wait(espera_por_qr)
            return  # escaneou -- pronto
        except asyncio.TimeoutError:
            await qr.recreate()  # o QR venceu; faz outro
        except SessionPasswordNeededError:
            await cliente.sign_in(password=pedir_senha())
            return
    raise AcaoHumanaNecessaria(
        TIPO_LOGIN,
        "o QR code não foi escaneado a tempo. Rode o login de novo e, no "
        "celular, vá em Telegram > Configurações > Dispositivos > Conectar dispositivo.",
        site="telegram",
    )
