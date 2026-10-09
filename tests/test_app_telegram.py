# -*- coding: utf-8 -*-
"""Testes da tela Telegram com o "robô de testes" do Streamlit (AppTest).

O AppTest roda a página sem navegador e deixa conferir o que apareceu
(avisos, botões, tabelas). Todas as pastas são trocadas por pastas
temporárias -- nada de conta, grupo ou internet de verdade. Nenhum destes
testes conecta ao Telegram: a tela só conecta quando um botão de conexão é
clicado."""
import json
from datetime import datetime

import pytest
from streamlit.testing.v1 import AppTest

from buscador.app import pagina_telegram
from buscador.core import telegram_download as dl

CHAT = 2136545743


def _script():
    from buscador.app import pagina_telegram
    pagina_telegram.mostrar()


@pytest.fixture
def pastas(tmp_path, monkeypatch):
    """Troca todos os caminhos da tela por uma pasta temporária."""
    monkeypatch.setattr(pagina_telegram, "CAMINHO_CFG", tmp_path / "buscador.local.cfg")
    monkeypatch.setattr(pagina_telegram, "PASTA_CONTAS", tmp_path / "sessoes_telegram")
    monkeypatch.setattr(pagina_telegram, "ARQUIVO_GRUPOS", tmp_path / "telegram" / "grupos.json")
    monkeypatch.setattr(pagina_telegram, "PASTA_SAIDA", tmp_path / "telegram")
    return tmp_path


def _com_cfg(tmp_path):
    (tmp_path / "buscador.local.cfg").write_text(
        "[telegram]\napi_id = 1234567\napi_hash = abc\n", encoding="utf-8")


def _com_conta(tmp_path, nome="samuel"):
    (tmp_path / "sessoes_telegram").mkdir(exist_ok=True)
    (tmp_path / "sessoes_telegram" / f"{nome}.session").write_text("x")


def _com_grupo(tmp_path, **extra):
    grupo = {"chat_id": CHAT, "nome": "Refúgio Intelectual", "forum": True, "tipo": "canal",
             "topicos": [{"id": 783, "titulo": "Obras em Latim"},
                         {"id": 81988, "titulo": "CHAT"}], **extra}
    arquivo = tmp_path / "telegram" / "grupos.json"
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    arquivo.write_text(json.dumps([grupo]), encoding="utf-8")


def _msg(id_, nome, mime="application/pdf", tamanho=5 * 1024**2):
    return {"id": id_, "type": "message", "file": nome,
            "date": int(datetime(2025, 3, 12).timestamp()),
            "raw": {"Message": "", "Media": {"Document": {
                "MimeType": mime, "Size": tamanho, "Attributes": [{"FileName": nome}]}}}}


def _com_lista(tmp_path, nome_pasta="topico_783"):
    pasta = tmp_path / "telegram" / nome_pasta
    lista = {"id": CHAT, "messages": [_msg(1, "Summa.pdf"), _msg(2, "Catena.pdf"),
                                      _msg(3, "Confissoes.epub", "application/epub+zip")]}
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / f"{nome_pasta}_lista_busca.json").write_text(json.dumps(lista), encoding="utf-8")
    (pasta / "arquivos").mkdir()
    (pasta / "arquivos" / "1_Summa.pdf").write_text("x")  # já baixado
    return pasta


def _textos(at):
    return " ".join(e.value for tipo in ("warning", "info", "error", "success", "caption",
                                         "markdown")
                    for e in getattr(at, tipo))


def test_sem_configuracao_mostra_o_passo_a_passo(pastas):
    at = AppTest.from_function(_script).run()
    assert not at.exception
    assert at.title[0].value == "Telegram"
    assert "my.telegram.org" in at.warning[0].value
    assert not at.selectbox  # não mostra mais nada sem o api_id/api_hash


def test_sem_contas_mostra_adicionar_conta(pastas):
    _com_cfg(pastas)
    at = AppTest.from_function(_script).run()
    assert not at.exception
    assert "Nenhuma conta" in _textos(at)
    assert any(b.label == "Gerar QR e conectar" for b in at.button)
    senha = next(t for t in at.text_input if "duas etapas" in t.label)
    assert senha.proto.type == senha.proto.PASSWORD  # aparece como ••••


def test_nome_de_conta_invalido_avisa_sem_conectar(pastas):
    _com_cfg(pastas)
    at = AppTest.from_function(_script).run()
    next(t for t in at.text_input if t.label.startswith("Nome da conta")).input("../fora")
    next(b for b in at.button if b.label == "Gerar QR e conectar").click()
    at.run()
    assert not at.exception
    assert "Nome de conta inválido" in at.error[0].value


def test_com_conta_e_sem_grupo_mostra_adicionar_grupo(pastas):
    _com_cfg(pastas)
    _com_conta(pastas)
    at = AppTest.from_function(_script).run()
    assert not at.exception
    assert at.selectbox[0].value == "samuel"
    rotulos = [b.label for b in at.button]
    assert "Adicionar pelo link" in rotulos and "Carregar meus grupos" in rotulos


def test_topico_com_lista_mostra_as_tres_etapas(pastas, monkeypatch):
    _com_cfg(pastas)
    _com_conta(pastas)
    _com_grupo(pastas)
    _com_lista(pastas)
    at = AppTest.from_function(_script).run()
    assert not at.exception
    assert len(at.dataframe) == 2  # tabela de tópicos + tabela de escolha
    textos = _textos(at)
    assert "Etapa 1 · feita" in textos and "Etapa 2 · agora" in textos
    assert "SHA-256" in textos
    # 2 dos 3 ainda faltam -> vêm marcados
    assert any(b.label == "Baixar 2 marcados" for b in at.button)

    # sem Git Bash: clicar em Baixar mostra onde ele deveria estar
    monkeypatch.setattr(dl, "achar_bash", lambda: None)
    next(b for b in at.button if b.label == "Baixar 2 marcados").click()
    at.run()
    assert not at.exception
    assert "Git Bash" in at.error[0].value


def test_conversa_sem_topicos_usa_pasta_chat(pastas):
    _com_cfg(pastas)
    _com_conta(pastas)
    _com_grupo(pastas, forum=False, topicos=[])
    _com_lista(pastas, nome_pasta=f"chat_{CHAT}")
    at = AppTest.from_function(_script).run()
    assert not at.exception
    assert f"chat_{CHAT}" in _textos(at)
    assert any(b.label == "Baixar 2 marcados" for b in at.button)
