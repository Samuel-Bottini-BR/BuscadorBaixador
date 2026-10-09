# -*- coding: utf-8 -*-
from buscador import telegram_cli
from buscador.core import telegram_conta


def test_sem_api_id_mostra_passo_a_passo(tmp_path, monkeypatch, capsys):
    # cfg inexistente -> o aviso com o caminho do my.telegram.org, sem travar
    original = telegram_conta.criar_cliente
    monkeypatch.setattr(
        telegram_cli, "criar_cliente",
        lambda conta: original(conta, caminho_cfg=tmp_path / "nao.cfg", pasta=tmp_path),
    )
    codigo = telegram_cli.main(["contar", "--conta", "samuel", "--chat", "1", "--topico", "2"])
    assert codigo == 1
    assert "my.telegram.org" in capsys.readouterr().out


def test_nome_de_conta_invalido(tmp_path, monkeypatch, capsys):
    cfg = tmp_path / "buscador.local.cfg"
    cfg.write_text("[telegram]\napi_id = 1\napi_hash = x\n", encoding="utf-8")
    original = telegram_conta.criar_cliente
    monkeypatch.setattr(
        telegram_cli, "criar_cliente",
        lambda conta: original(conta, caminho_cfg=cfg, pasta=tmp_path),
    )
    assert telegram_cli.main(["login", "--conta", "../x"]) == 1
    assert "Nome de conta inválido" in capsys.readouterr().out


def test_cada_qr_vai_para_um_arquivo_novo(tmp_path, monkeypatch):
    monkeypatch.setattr(telegram_cli, "PASTA_QR", tmp_path)
    monkeypatch.setattr(telegram_cli, "_qrs_mostrados", 0)
    abertos = []
    monkeypatch.setattr(telegram_cli.os, "startfile", abertos.append, raising=False)
    telegram_cli.mostrar_qr("tg://login?token=1")
    telegram_cli.mostrar_qr("tg://login?token=2")
    assert abertos == [tmp_path / "qr_login_1.png", tmp_path / "qr_login_2.png"]
    for arquivo in abertos:
        assert arquivo.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


def test_imagem_que_nao_salva_mostra_qr_no_terminal(tmp_path, monkeypatch, capsys):
    # imita o Windows recusando gravar (arquivo travado)
    monkeypatch.setattr(telegram_cli, "PASTA_QR", tmp_path)
    monkeypatch.setattr(telegram_cli, "_qrs_mostrados", 0)

    class ImagemTravada:
        def save(self, destino):
            raise OSError(22, "Invalid argument")

    monkeypatch.setattr(telegram_cli.qrcode, "make", lambda link: ImagemTravada())
    telegram_cli.mostrar_qr("tg://login?token=1")  # não pode quebrar
    saida = capsys.readouterr().out
    assert any(c in saida for c in "█▀▄")  # QR desenhado em texto no terminal
