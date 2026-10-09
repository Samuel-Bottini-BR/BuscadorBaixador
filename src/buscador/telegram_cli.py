# -*- coding: utf-8 -*-
"""
Comandos de terminal do Telegram (listagem pela busca do servidor).

    telegram.bat login  --conta samuel
    telegram.bat contar --conta samuel --chat 2136545743 --topico 81988

"login" mostra um QR code (abre uma imagem) para escanear no celular e
guarda o login em sessoes_telegram/<conta>.session. "contar" pergunta ao
servidor do Telegram quantos arquivos de cada tipo existem no tópico --
uma pergunta só, sem ler a conversa.
"""
import argparse
import asyncio
import getpass
import os
import sys
import time

import qrcode

from buscador.core.acao_humana import TIPO_LOGIN, AcaoHumanaNecessaria, formatar_aviso
from buscador.core.config_sites import CAMINHO_PADRAO
from buscador.core.telegram_busca import contar_arquivos
from buscador.core.telegram_conta import criar_cliente, login_qr

# Onde a imagem do QR é salva (saidas/ não vai pro GitHub).
ARQUIVO_QR = CAMINHO_PADRAO.parent / "saidas" / "telegram" / "qr_login.png"


def mostrar_qr(link: str) -> None:
    """Desenha o QR numa imagem PNG e abre na tela (no Windows). Também
    imprime no terminal, caso a imagem não abra."""
    ARQUIVO_QR.parent.mkdir(parents=True, exist_ok=True)
    qrcode.make(link).save(ARQUIVO_QR)
    print()
    print(f"[{time.strftime('%H:%M:%S')}] QR code novo (vale ~1 minuto): {ARQUIVO_QR}")
    print("No celular: Telegram > Configurações > Dispositivos > Conectar dispositivo,")
    print("e aponte a câmera para o QR.")
    if hasattr(os, "startfile"):  # só existe no Windows
        os.startfile(ARQUIVO_QR)
    else:
        qr = qrcode.QRCode(border=1)
        qr.add_data(link)
        qr.print_ascii(invert=True)


def pedir_senha() -> str:
    return getpass.getpass(
        "Esta conta tem senha de duas etapas. Digite a senha (não aparece na tela, "
        "e não fica guardada): "
    )


async def cmd_login(conta: str) -> None:
    cliente = criar_cliente(conta)
    await cliente.connect()
    try:
        await login_qr(cliente, mostrar_qr, pedir_senha)
        eu = await cliente.get_me()
        nome = " ".join(p for p in (eu.first_name, eu.last_name) if p)
        print(f"\nPronto! Conta '{conta}' conectada como {nome}.")
    finally:
        await cliente.disconnect()


async def cmd_contar(conta: str, chat: int, topico: int) -> None:
    cliente = criar_cliente(conta)
    await cliente.connect()
    try:
        if not await cliente.is_user_authorized():
            raise AcaoHumanaNecessaria(
                TIPO_LOGIN,
                f"a conta '{conta}' ainda não está conectada. Rode antes: "
                f"telegram.bat login --conta {conta}",
                site="telegram",
            )
        inicio = time.monotonic()
        contagem = await contar_arquivos(cliente, chat, topico)
        segundos = time.monotonic() - inicio
    finally:
        await cliente.disconnect()
    print(f"\nTópico {topico} do grupo {chat} (contado em {segundos:.1f} s):")
    for tipo, numero in contagem.items():
        print(f"  {numero:>7}  {tipo}")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="telegram", description="Telegram: login e contagem de arquivos")
    sub = parser.add_subparsers(dest="comando", required=True)
    p_login = sub.add_parser("login", help="entrar numa conta pelo QR code")
    p_login.add_argument("--conta", required=True, help="nome curto da conta (ex.: samuel)")
    p_contar = sub.add_parser("contar", help="contar arquivos de um tópico")
    p_contar.add_argument("--conta", required=True)
    p_contar.add_argument("--chat", required=True, type=int, help="número do grupo (ex.: 2136545743)")
    p_contar.add_argument("--topico", required=True, type=int, help="número do tópico (ex.: 81988)")
    args = parser.parse_args(argv)

    try:
        if args.comando == "login":
            asyncio.run(cmd_login(args.conta))
        else:
            asyncio.run(cmd_contar(args.conta, args.chat, args.topico))
    except AcaoHumanaNecessaria as erro:
        print(formatar_aviso(erro))
        return 1
    except ValueError as erro:  # ex.: nome de conta inválido
        print(f"Erro: {erro}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
