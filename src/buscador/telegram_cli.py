# -*- coding: utf-8 -*-
"""
Comandos de terminal do Telegram (listagem pela busca do servidor).

    telegram.bat login  --conta samuel
    telegram.bat contar --conta samuel --chat 2136545743 --topico 81988
    telegram.bat listar --conta samuel --chat 2136545743 --topico 81988

"login" mostra um QR code (abre uma imagem) para escanear no celular e
guarda o login em sessoes_telegram/<conta>.session. "contar" pergunta ao
servidor do Telegram quantos arquivos de cada tipo existem no tópico --
uma pergunta só, sem ler a conversa. "listar" busca só os documentos (PDF,
EPUB, RAR...) e grava a lista no formato do tdl, pronta para a planilha e o
baixar_topico.sh.
"""
import argparse
import asyncio
import getpass
import json
import os
import sys
import time
from pathlib import Path

import qrcode

from buscador.core.acao_humana import TIPO_LOGIN, AcaoHumanaNecessaria, formatar_aviso
from buscador.core.config_sites import CAMINHO_PADRAO
from buscador.core.registro_erros import instalar_em_comandos
from buscador.core.telegram_busca import contar_arquivos, listar_arquivos, montar_lista_tdl
from buscador.core.telegram_conta import criar_cliente, login_qr

# Pasta onde as imagens do QR são salvas (saidas/ não vai pro GitHub).
PASTA_QR = CAMINHO_PADRAO.parent / "saidas" / "telegram"
_qrs_mostrados = 0  # conta quantos QRs já foram mostrados nesta execução


def _apagar_qrs_antigos() -> None:
    """Tenta apagar imagens de QR de vezes anteriores. Se alguma estiver
    aberta no visualizador de fotos (o Windows trava o arquivo), deixa pra
    lá -- não é motivo para parar o login."""
    for antigo in PASTA_QR.glob("qr_login*.png"):
        try:
            antigo.unlink()
        except OSError:
            pass


def mostrar_qr(link: str) -> None:
    """Desenha o QR numa imagem PNG e abre na tela (no Windows).

    Cada QR vai para um arquivo NOVO (qr_login_1.png, qr_login_2.png...):
    o anterior pode estar aberto no visualizador de fotos, e o Windows não
    deixa gravar por cima de um arquivo aberto (foi o erro "Invalid
    argument" do primeiro teste). Se mesmo assim não der para salvar a
    imagem, desenha o QR no próprio terminal."""
    global _qrs_mostrados
    _qrs_mostrados += 1
    PASTA_QR.mkdir(parents=True, exist_ok=True)
    if _qrs_mostrados == 1:
        _apagar_qrs_antigos()
    arquivo = PASTA_QR / f"qr_login_{_qrs_mostrados}.png"
    print()
    print(f"[{time.strftime('%H:%M:%S')}] QR code nº {_qrs_mostrados} (se vencer, aparece outro sozinho)")
    print("No celular: Telegram > Configurações > Dispositivos > Conectar dispositivo,")
    print("e aponte a câmera para o QR.")
    try:
        qrcode.make(link).save(arquivo)
        if not hasattr(os, "startfile"):  # startfile só existe no Windows
            raise OSError("sem visualizador")
        os.startfile(arquivo)
        print(f"(imagem: {arquivo})")
    except OSError:
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


async def _exigir_login(cliente, conta: str) -> None:
    if not await cliente.is_user_authorized():
        raise AcaoHumanaNecessaria(
            TIPO_LOGIN,
            f"a conta '{conta}' ainda não está conectada. Rode antes: "
            f"telegram.bat login --conta {conta}",
            site="telegram",
        )


def caminho_lista_padrao(topico: int):
    return PASTA_QR / f"topico_{topico}" / f"topico_{topico}_lista_busca.json"


async def cmd_listar(conta: str, chat: int, topico: int, saida) -> None:
    cliente = criar_cliente(conta)
    await cliente.connect()
    try:
        await _exigir_login(cliente, conta)
        print(f"Buscando os documentos do tópico {topico} (100 por página)...")
        inicio = time.monotonic()
        mensagens = await listar_arquivos(
            cliente, chat, topico,
            ao_receber_pagina=lambda p, n: print(f"  página {p}: {n} até agora"),
        )
        segundos = time.monotonic() - inicio
    finally:
        await cliente.disconnect()
    lista = montar_lista_tdl(chat, mensagens)
    saida.parent.mkdir(parents=True, exist_ok=True)
    saida.write_text(json.dumps(lista, ensure_ascii=False, indent=1), encoding="utf-8")
    tamanho = sum(m["raw"]["Media"]["Document"]["Size"] for m in lista["messages"])
    print(f"\nPronto em {segundos:.1f} s: {len(lista['messages'])} documentos "
          f"({tamanho / 1024**3:.2f} GB), sem figurinhas.")
    print(f"Lista salva em: {saida}")


async def cmd_contar(conta: str, chat: int, topico: int) -> None:
    cliente = criar_cliente(conta)
    await cliente.connect()
    try:
        await _exigir_login(cliente, conta)
        inicio = time.monotonic()
        contagem = await contar_arquivos(cliente, chat, topico)
        segundos = time.monotonic() - inicio
    finally:
        await cliente.disconnect()
    print(f"\nTópico {topico} do grupo {chat} (contado em {segundos:.1f} s):")
    for tipo, numero in contagem.items():
        print(f"  {numero:>7}  {tipo}")


def main(argv=None) -> int:
    instalar_em_comandos("telegram_cli")  # erro inesperado também vai para logs/erros.log
    parser = argparse.ArgumentParser(prog="telegram", description="Telegram: login e contagem de arquivos")
    sub = parser.add_subparsers(dest="comando", required=True)
    p_login = sub.add_parser("login", help="entrar numa conta pelo QR code")
    p_login.add_argument("--conta", required=True, help="nome curto da conta (ex.: samuel)")
    p_contar = sub.add_parser("contar", help="contar arquivos de um tópico")
    p_contar.add_argument("--conta", required=True)
    p_contar.add_argument("--chat", required=True, type=int, help="número do grupo (ex.: 2136545743)")
    p_contar.add_argument("--topico", required=True, type=int, help="número do tópico (ex.: 81988)")
    p_listar = sub.add_parser("listar", help="listar os documentos de um tópico (formato do tdl)")
    p_listar.add_argument("--conta", required=True)
    p_listar.add_argument("--chat", required=True, type=int)
    p_listar.add_argument("--topico", required=True, type=int)
    p_listar.add_argument("--saida", help="onde salvar o .json (padrão: saidas/telegram/topico_<n>/)")
    args = parser.parse_args(argv)

    try:
        if args.comando == "login":
            asyncio.run(cmd_login(args.conta))
        elif args.comando == "contar":
            asyncio.run(cmd_contar(args.conta, args.chat, args.topico))
        else:
            saida = Path(args.saida) if args.saida else caminho_lista_padrao(args.topico)
            asyncio.run(cmd_listar(args.conta, args.chat, args.topico, saida))
    except AcaoHumanaNecessaria as erro:
        print(formatar_aviso(erro))
        return 1
    except ValueError as erro:  # ex.: nome de conta inválido
        print(f"Erro: {erro}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
