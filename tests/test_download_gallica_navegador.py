# -*- coding: utf-8 -*-
from unittest.mock import MagicMock, patch

import pytest

from buscador.core.download_gallica_navegador import (
    DownloadNaoConcluidoError,
    baixar_via_navegador,
    esperar_novo_arquivo,
    montar_url_pdf,
)


def test_montar_url_pdf_junta_base_com_ponto_pdf():
    assert (
        montar_url_pdf("https://gallica.bnf.fr/ark:/12148/bpt6k6382082m")
        == "https://gallica.bnf.fr/ark:/12148/bpt6k6382082m.pdf"
    )


def test_montar_url_pdf_remove_barra_final_antes_de_colar_pdf():
    assert (
        montar_url_pdf("https://gallica.bnf.fr/ark:/12148/bpt6k6382082m/")
        == "https://gallica.bnf.fr/ark:/12148/bpt6k6382082m.pdf"
    )


# --- esperar_novo_arquivo (lógica de "achar o arquivo novo na pasta",
# isolada de qualquer coisa do Selenium -- só filesystem de verdade,
# nenhum navegador aberto) ---------------------------------------------


def test_esperar_novo_arquivo_acha_arquivo_que_ja_esta_la(tmp_path):
    (tmp_path / "documento.pdf").write_bytes(b"%PDF-1.4 conteudo falso")

    encontrado = esperar_novo_arquivo(tmp_path, arquivos_antes=set(), timeout_segundos=1.0, intervalo_segundos=0.01)

    assert encontrado == tmp_path / "documento.pdf"


def test_esperar_novo_arquivo_ignora_arquivos_que_ja_existiam_antes(tmp_path):
    arquivo_velho = tmp_path / "ja_existia.pdf"
    arquivo_velho.write_bytes(b"arquivo antigo, nao deve contar")
    arquivos_antes = {arquivo_velho}

    with pytest.raises(DownloadNaoConcluidoError):
        esperar_novo_arquivo(tmp_path, arquivos_antes, timeout_segundos=0.05, intervalo_segundos=0.01)


def test_esperar_novo_arquivo_ignora_download_parcial_crdownload(tmp_path):
    # Simula o Chrome ainda baixando: só existe o arquivo temporário
    # ".crdownload" -- não deve contar como "pronto".
    (tmp_path / "documento.pdf.crdownload").write_bytes(b"baixando ainda...")

    with pytest.raises(DownloadNaoConcluidoError) as excinfo:
        esperar_novo_arquivo(tmp_path, arquivos_antes=set(), timeout_segundos=0.05, intervalo_segundos=0.01)

    # a mensagem de erro deve ser clara sobre o que foi observado, não um erro genérico
    assert "documento.pdf.crdownload" in str(excinfo.value)


def test_esperar_novo_arquivo_levanta_erro_claro_quando_timeout_estoura_sem_nada(tmp_path):
    with pytest.raises(DownloadNaoConcluidoError) as excinfo:
        esperar_novo_arquivo(tmp_path, arquivos_antes=set(), timeout_segundos=0.05, intervalo_segundos=0.01)

    mensagem = str(excinfo.value)
    assert str(tmp_path) in mensagem
    assert "0" in mensagem  # menciona o timeout usado


# --- baixar_via_navegador (mockado -- nunca abre um Chrome de verdade na
# suite automatizada, conforme pedido no brief) --------------------------


def _resposta_json(dados):
    resposta = MagicMock()
    resposta.json.return_value = dados
    return resposta


def test_baixar_via_navegador_levanta_erro_quando_download_nao_termina(tmp_path):
    driver_falso = MagicMock()
    cliente_falso = MagicMock()
    cliente_falso.get.return_value = _resposta_json(
        {"downoaldurl": "https://gallica.bnf.fr/ark:/12148/bpt6k6382082m"}
    )

    with patch(
        "buscador.core.download_gallica_navegador.abrir_navegador", return_value=driver_falso
    ) as abrir_mock, patch(
        "buscador.core.download_gallica_navegador.ClienteEducado", return_value=cliente_falso
    ):
        with pytest.raises(DownloadNaoConcluidoError):
            # timeout minúsculo de propósito -- nenhum arquivo vai aparecer
            # na pasta (driver.get é mockado, não baixa nada de verdade),
            # então o polling estoura rápido sem precisar mockar time.sleep.
            baixar_via_navegador("bpt6k6382082m", tmp_path, timeout_segundos=0.05)

    # headless=False sempre (headless=True já provado, em C-nav2/C-nav5,
    # que não passa no desafio anti-robô da Gallica) e escondida=True por
    # padrão (Tarefa C-nav7 -- ver core/navegador.py pra explicação completa).
    abrir_mock.assert_called_once_with("gallica", headless=False, external_pdf=True, escondida=True)
    driver_falso.get.assert_called_once_with("https://gallica.bnf.fr/ark:/12148/bpt6k6382082m.pdf")
    # o navegador tem que ser fechado mesmo quando o download falha (finally)
    driver_falso.quit.assert_called_once()


def test_baixar_via_navegador_fecha_navegador_mesmo_se_driver_get_falhar(tmp_path):
    driver_falso = MagicMock()
    driver_falso.get.side_effect = RuntimeError("navegador travou")
    cliente_falso = MagicMock()
    cliente_falso.get.return_value = _resposta_json(
        {"downoaldurl": "https://gallica.bnf.fr/ark:/12148/bpt6k6382082m"}
    )

    with patch(
        "buscador.core.download_gallica_navegador.abrir_navegador", return_value=driver_falso
    ), patch("buscador.core.download_gallica_navegador.ClienteEducado", return_value=cliente_falso):
        with pytest.raises(RuntimeError):
            baixar_via_navegador("bpt6k6382082m", tmp_path, timeout_segundos=0.05)

    driver_falso.quit.assert_called_once()


def test_baixar_via_navegador_configura_pasta_de_download_via_cdp_e_devolve_arquivo(tmp_path):
    cliente_falso = MagicMock()
    cliente_falso.get.return_value = _resposta_json(
        {"downoaldurl": "https://gallica.bnf.fr/ark:/12148/bpt6k6382082m"}
    )

    driver_falso = MagicMock()

    # Simula o navegador salvando o arquivo de verdade assim que driver.get
    # for chamado -- só pra exercitar o caminho "deu certo" sem abrir Chrome.
    def get_falso(url):
        (tmp_path / "bpt6k6382082m.pdf").write_bytes(b"%PDF-1.4 conteudo falso")

    driver_falso.get.side_effect = get_falso

    with patch(
        "buscador.core.download_gallica_navegador.abrir_navegador", return_value=driver_falso
    ), patch("buscador.core.download_gallica_navegador.ClienteEducado", return_value=cliente_falso):
        resultado = baixar_via_navegador("bpt6k6382082m", tmp_path, timeout_segundos=2.0)

    assert resultado == tmp_path / "bpt6k6382082m.pdf"
    driver_falso.execute_cdp_cmd.assert_called_once_with(
        "Page.setDownloadBehavior",
        {"behavior": "allow", "downloadPath": str(tmp_path)},
    )
    driver_falso.quit.assert_called_once()


def test_baixar_via_navegador_escondida_false_repassa_pro_abrir_navegador(tmp_path):
    # escondida=False é a via de depuração manual (janela real visível) --
    # ver docstring de baixar_via_navegador. Confirma que o parâmetro
    # realmente chega até abrir_navegador em vez de ser ignorado.
    driver_falso = MagicMock()
    cliente_falso = MagicMock()
    cliente_falso.get.return_value = _resposta_json(
        {"downoaldurl": "https://gallica.bnf.fr/ark:/12148/bpt6k6382082m"}
    )

    with patch(
        "buscador.core.download_gallica_navegador.abrir_navegador", return_value=driver_falso
    ) as abrir_mock, patch(
        "buscador.core.download_gallica_navegador.ClienteEducado", return_value=cliente_falso
    ):
        with pytest.raises(DownloadNaoConcluidoError):
            baixar_via_navegador("bpt6k6382082m", tmp_path, escondida=False, timeout_segundos=0.05)

    abrir_mock.assert_called_once_with("gallica", headless=False, external_pdf=True, escondida=False)
