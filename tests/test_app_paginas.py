# -*- coding: utf-8 -*-
"""
Testes das telas do aplicativo (Streamlit), sem abrir navegador: o
AppTest do Streamlit roda a tela "de mentirinha" e deixa a gente olhar o
que foi desenhado (títulos, botões, tabelas, avisos) e até clicar.

Todos os caminhos (saidas/, buscador.local.cfg, registro de jobs) são
trocados por uma pasta temporária -- nenhum teste olha os arquivos de
verdade do Samuel.
"""
import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from buscador.adapters.base import Item
from buscador.core import config_sites, jobs_registro, mapear_segundo_plano, resumo_saidas, verificar_site
from buscador.core.planilha import gerar_planilha


@pytest.fixture(autouse=True)
def pasta_vazia(tmp_path, monkeypatch):
    saidas = tmp_path / "saidas"
    saidas.mkdir()
    monkeypatch.setattr(resumo_saidas, "SAIDAS", saidas)
    monkeypatch.setattr(config_sites, "CAMINHO_PADRAO", tmp_path / "buscador.local.cfg")
    monkeypatch.setattr(jobs_registro, "CAMINHO_PADRAO", tmp_path / "jobs" / "registro.json")
    monkeypatch.setattr(mapear_segundo_plano, "_PROCESSOS", {})
    st.cache_data.clear()  # o cache guarda contas de um teste para o outro; começa limpo
    return saidas


# Cada tela vira um "mini-aplicativo" de uma tela só. As funções abaixo
# são executadas pelo AppTest como se fossem um script, por isso o import
# fica dentro delas.
def _app_inicio():
    from buscador.app import pagina_inicio
    pagina_inicio.mostrar()


def _app_sites():
    from buscador.app import pagina_sites
    pagina_sites.mostrar()


def _app_mapear():
    from buscador.app import pagina_mapear
    pagina_mapear.mostrar()


def _app_baixar():
    from buscador.app import pagina_baixar
    pagina_baixar.mostrar()


def _app_catalogar():
    from buscador.app import pagina_catalogar
    pagina_catalogar.mostrar()


def _rodar(funcao):
    app = AppTest.from_function(funcao, default_timeout=30)
    app.run()
    assert not app.exception, [e.value for e in app.exception]
    return app


def _textos(app):
    """Todo o texto desenhado (markdown, avisos, legendas), junto."""
    partes = []
    for tipo in ("markdown", "caption", "info", "warning", "success", "error", "subheader", "title"):
        partes += [str(e.value) for e in getattr(app, tipo)]
    return "\n".join(partes)


@pytest.mark.parametrize("funcao", [_app_inicio, _app_sites, _app_mapear, _app_baixar, _app_catalogar])
def test_cada_tela_abre_sem_erro_numa_pasta_vazia(funcao):
    _rodar(funcao)


# --- Início ----------------------------------------------------------------
def test_inicio_mostra_numeros_reais(pasta_vazia):
    arquivos = pasta_vazia / "telegram" / "topico_1" / "arquivos"
    arquivos.mkdir(parents=True)
    for i in range(3):
        (arquivos / f"{i}.pdf").write_bytes(b"x" * 1024)
    gerar_planilha([Item(titulo_original="a", link="https://x.org")], pasta_vazia / "gallica_2026.xlsx")

    app = _rodar(_app_inicio)
    metricas = {m.label: m.value for m in app.metric}
    assert metricas["Sites cadastrados"] == "3"
    assert metricas["Planilhas geradas"] == "1"
    assert metricas["Arquivos baixados"] == "3"
    assert metricas["Tarefas rodando agora"] == "0"
    assert "buscador.local.cfg" in _textos(app)  # o arquivo não existe: avisa
    assert len(app.dataframe) == 1  # últimas atividades


# --- Sites -----------------------------------------------------------------
def test_sites_mostra_um_cartao_por_site():
    app = _rodar(_app_sites)
    textos = _textos(app)
    for nome in ("Gallica (BnF)", "Grand Sud Médiéval", "Internet Archive"):
        assert nome in textos
    assert len([b for b in app.button if b.label == "Mapear agora"]) == 3


def test_sites_fazer_login_mostra_o_comando_do_logar():
    app = _rodar(_app_sites)
    app.button(key="login_internet_archive").click().run()
    assert not app.exception
    assert any("buscador.logar internet_archive https://archive.org/account/login" in c.value for c in app.code)


def _verificacao_falsa(metodo):
    def falsa(endereco, cliente=None):
        resultado = verificar_site.ResultadoVerificacao(
            endereco=verificar_site.normalizar_endereco(endereco), robots_encontrado=True,
            robots_permite=metodo != "proibido", robots_texto="User-agent: *\n", metodo_sugerido=metodo,
        )
        return resultado
    return falsa


def test_sites_adicionar_site_permitido_e_salvar(monkeypatch, pasta_vazia):
    monkeypatch.setattr(verificar_site, "verificar_site", _verificacao_falsa("html"))
    app = _rodar(_app_sites)
    app.text_input[0].input("Biblioteca Teste")
    app.text_input[1].input("biblioteca-teste.org")
    app.button[0].click().run()  # "Verificar" (o primeiro botão é o do formulário)
    assert not app.exception
    assert "permite a leitura" in _textos(app)
    salvar = [b for b in app.button if b.label == "Salvar site"][0]
    salvar.click().run()
    assert not app.exception
    assert (pasta_vazia / "sites_cadastrados.json").exists()
    assert "Biblioteca Teste" in _textos(app)


def test_sites_proibido_nao_deixa_salvar(monkeypatch, pasta_vazia):
    monkeypatch.setattr(verificar_site, "verificar_site", _verificacao_falsa("proibido"))
    app = _rodar(_app_sites)
    app.text_input[0].input("Site Fechado")
    app.text_input[1].input("fechado.org")
    app.button[0].click().run()
    assert not app.exception
    textos = _textos(app)
    assert "não burla" in textos and "Pular este site" in textos
    salvar = [b for b in app.button if b.label == "Salvar site"][0]
    assert salvar.disabled
    assert not (pasta_vazia / "sites_cadastrados.json").exists()


# --- Mapear ----------------------------------------------------------------
def test_mapear_mostra_a_planilha_mais_nova_com_bolinhas(pasta_vazia):
    itens = [Item(titulo_original="Astrolabium", link="https://x.org/1"),
             Item(titulo_original="Gnomonices", link="https://x.org/2")]
    itens[0].extra["categoria"] = "verde"
    gerar_planilha(itens, pasta_vazia / "gallica_2026-10-09.xlsx")
    app = _rodar(_app_mapear)
    tabela = app.dataframe[0].value
    assert list(tabela["cor"]) == ["🟢", "⚪"]
    assert list(tabela["titulo_original"]) == ["Astrolabium", "Gnomonices"]
    assert "Exportar planilha (.xlsx)" in [b.label for b in app.get("download_button")]


def test_mapear_vem_com_o_site_escolhido_na_tela_sites():
    app = AppTest.from_function(_app_mapear, default_timeout=30)
    app.session_state["mapear_site_id"] = "grand_sud"
    app.run()
    assert not app.exception
    assert app.selectbox[0].value == "grand_sud"
    assert "phpbb" in _textos(app)


def test_mapear_inicia_em_segundo_plano(monkeypatch):
    chamadas = []

    def iniciar_falso(adapter, entrada, nome_site=""):
        chamadas.append((adapter, entrada, nome_site))
        return {}
    monkeypatch.setattr(mapear_segundo_plano, "iniciar_mapeamento", iniciar_falso)
    app = _rodar(_app_mapear)  # o primeiro site da lista é a Gallica
    app.text_input[0].input("Clavius")
    [b for b in app.button if b.label == "Mapear"][0].click().run()
    assert not app.exception
    assert chamadas == [("gallica", 'gallica all "Clavius"', "Gallica (BnF)")]


def test_mapear_mostra_andamento_do_ultimo(pasta_vazia):
    pasta = pasta_vazia / "mapeamentos"
    pasta.mkdir()
    (pasta / "m.log").write_text("Comando: x\nNão deu para continuar: sem rede\n", encoding="utf-8")
    import json
    (pasta / "m.json").write_text(json.dumps({
        "id": "m", "site": "Gallica (BnF)", "adapter": "gallica", "entrada": "x",
        "saida": str(pasta_vazia / "m.xlsx"), "log": str(pasta / "m.log"),
        "iniciado_em": "2026-10-09T10:00:00",
    }), encoding="utf-8")
    app = _rodar(_app_mapear)
    assert "parou sem gerar a planilha" in _textos(app)
    assert any("sem rede" in c.value for c in app.code)


# --- Baixar ----------------------------------------------------------------
def test_baixar_explica_o_que_ainda_nao_existe_e_mostra_jobs():
    jobs_registro.salvar_registro([jobs_registro.JobRegistrado(
        id="cli-1", modulo="cli", argv=["x"], pid=1, estado="concluido", log_path="jobs/cli-1.log",
        iniciado_em="2026-10-01T10:00:00", atualizado_em="2026-10-01T10:05:00",
    )], jobs_registro.CAMINHO_PADRAO)
    app = _rodar(_app_baixar)
    textos = _textos(app)
    assert "Ainda não" in textos and "bloqueado" in textos
    assert app.dataframe[0].value["Tarefa"][0] == "Mapear (Fase 1)"


# --- Catalogar -------------------------------------------------------------
def test_catalogar_e_fase_futura_com_botoes_desligados():
    app = _rodar(_app_catalogar)
    assert "Fase 4" in _textos(app)
    assert all(b.disabled for b in app.button)
    assert "Mandar pro Claude Pro" in [b.label for b in app.button]


def test_mapear_de_ponta_a_ponta_com_processo_de_verdade(monkeypatch, pasta_vazia):
    """Roda um processo Python DE VERDADE em segundo plano (no lugar do
    motor, um script curtinho que gera a planilha e escreve a frase de
    sucesso do cli.py), e confere que a tela mostra "Pronto!" no fim."""
    import sys
    import time

    def comando_falso(adapter, entrada, caminho_saida, python=None):
        script = (
            "from buscador.adapters.base import Item\n"
            "from buscador.core.planilha import gerar_planilha\n"
            f"gerar_planilha([Item(titulo_original='Astrolabium', link='https://x.org')], r'{caminho_saida}')\n"
            f"print('1 itens encontrados. Planilha salva em: {caminho_saida}')\n"
        )
        return [sys.executable, "-c", script]
    monkeypatch.setattr(mapear_segundo_plano, "montar_comando", comando_falso)

    app = _rodar(_app_mapear)
    app.text_input[0].input("Clavius")
    [b for b in app.button if b.label == "Mapear"][0].click().run()
    assert not app.exception
    for processo in list(mapear_segundo_plano._PROCESSOS.values()):
        for _ in range(300):  # espera o processo terminar (até ~30 s)
            if processo.poll() is not None:
                break
            time.sleep(0.1)
    app.run()
    assert not app.exception
    assert "Pronto! Planilha salva em" in _textos(app)
    assert list(app.dataframe[0].value["titulo_original"]) == ["Astrolabium"]
