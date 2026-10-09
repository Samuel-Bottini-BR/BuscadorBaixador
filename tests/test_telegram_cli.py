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


def test_mostrar_qr_salva_imagem(tmp_path, monkeypatch):
    monkeypatch.setattr(telegram_cli, "ARQUIVO_QR", tmp_path / "qr.png")
    monkeypatch.setattr(telegram_cli.os, "startfile", lambda p: None, raising=False)
    telegram_cli.mostrar_qr("tg://login?token=abc")
    assert (tmp_path / "qr.png").read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
