# -*- coding: utf-8 -*-
import asyncio

import pytest
from telethon.errors import SessionPasswordNeededError

from buscador.core.acao_humana import AcaoHumanaNecessaria
from buscador.core.telegram_conta import caminho_sessao, ler_credenciais, login_qr


# --- credenciais ---------------------------------------------------------

def test_sem_arquivo_pede_acao_humana(tmp_path):
    with pytest.raises(AcaoHumanaNecessaria) as erro:
        ler_credenciais(tmp_path / "nao-existe.cfg")
    assert "my.telegram.org" in erro.value.mensagem


def test_api_id_que_nao_e_numero_pede_acao_humana(tmp_path):
    cfg = tmp_path / "buscador.local.cfg"
    cfg.write_text("[telegram]\napi_id = abc\napi_hash = xyz\n", encoding="utf-8")
    with pytest.raises(AcaoHumanaNecessaria):
        ler_credenciais(cfg)


def test_le_credenciais(tmp_path):
    cfg = tmp_path / "buscador.local.cfg"
    cfg.write_text("[telegram]\napi_id = 1234567\napi_hash = abcdef\n", encoding="utf-8")
    assert ler_credenciais(cfg) == (1234567, "abcdef")


# --- sessão por conta ----------------------------------------------------

def test_uma_sessao_por_conta(tmp_path):
    assert caminho_sessao("samuel", tmp_path) == tmp_path / "samuel.session"
    assert caminho_sessao("kaique", tmp_path) == tmp_path / "kaique.session"


@pytest.mark.parametrize("nome", ["../x", "a/b", "", "joão", "com espaco"])
def test_recusa_nome_de_conta_invalido(tmp_path, nome):
    with pytest.raises(ValueError):
        caminho_sessao(nome, tmp_path)


# --- login por QR, com um "Telegram de mentira" --------------------------

class QRFalso:
    """Imita o QR do Telethon: cada chamada de wait() faz o que está na
    lista de 'eventos' (vencer, pedir senha ou dar certo)."""

    def __init__(self, eventos):
        self.eventos = list(eventos)
        self.url = "tg://login?token=1"
        self.recriados = 0

    async def wait(self, timeout):
        evento = self.eventos.pop(0)
        if evento == "venceu":
            raise asyncio.TimeoutError
        if evento == "senha":
            raise SessionPasswordNeededError(request=None)

    async def recreate(self):
        self.recriados += 1
        self.url = f"tg://login?token={self.recriados + 1}"


class ClienteFalso:
    def __init__(self, qr, logado=False):
        self.qr = qr
        self.logado = logado
        self.senha_usada = None

    async def is_user_authorized(self):
        return self.logado

    async def qr_login(self):
        return self.qr

    async def sign_in(self, password):
        self.senha_usada = password


def rodar_login(cliente, **kw):
    links = []
    asyncio.run(login_qr(cliente, links.append, lambda: "senha-de-teste", **kw))
    return links


def test_ja_logado_nao_mostra_qr():
    assert rodar_login(ClienteFalso(QRFalso([]), logado=True)) == []


def test_qr_vencido_e_renovado():
    qr = QRFalso(["venceu", "ok"])
    links = rodar_login(ClienteFalso(qr))
    assert links == ["tg://login?token=1", "tg://login?token=2"]
    assert qr.recriados == 1


def test_senha_de_duas_etapas_e_pedida():
    cliente = ClienteFalso(QRFalso(["senha"]))
    rodar_login(cliente)
    assert cliente.senha_usada == "senha-de-teste"


def test_ninguem_escaneou_pede_acao_humana():
    with pytest.raises(AcaoHumanaNecessaria):
        rodar_login(ClienteFalso(QRFalso(["venceu"] * 3)), max_qrs=3)
