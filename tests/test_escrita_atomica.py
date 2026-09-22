# -*- coding: utf-8 -*-
import json
import time

import pytest

from buscador.core import escrita_atomica as modulo
from buscador.core.escrita_atomica import salvar_json_atomico


def test_salvar_json_atomico_grava_e_le_de_volta(tmp_path):
    """Testa que dados serializáveis são gravados e podem ser lidos de volta."""
    caminho = tmp_path / "dados.json"
    dados = {"chave": "valor", "numero": 42, "lista": [1, 2, 3]}

    salvar_json_atomico(dados, caminho)

    assert caminho.exists()
    conteudo = json.loads(caminho.read_text(encoding="utf-8"))
    assert conteudo == dados


def test_salvar_json_atomico_nao_deixa_arquivo_tmp_para_tras(tmp_path):
    """Testa que o arquivo .tmp é removido após a gravação."""
    caminho = tmp_path / "dados.json"
    dados = {"chave": "valor"}

    salvar_json_atomico(dados, caminho)

    assert caminho.exists()
    assert not caminho.with_suffix(".json.tmp").exists()


def test_salvar_json_atomico_grava_com_list_tambem(tmp_path):
    """Testa que também funciona com listas, não só dicts."""
    caminho = tmp_path / "lista.json"
    dados = [1, 2, {"chave": "valor"}, 4]

    salvar_json_atomico(dados, caminho)

    assert caminho.exists()
    conteudo = json.loads(caminho.read_text(encoding="utf-8"))
    assert conteudo == dados


def test_salvar_json_atomico_tenta_de_novo_quando_o_windows_nega_o_os_replace(tmp_path, monkeypatch):
    """Testa que a função tenta novamente quando os.replace falha com PermissionError."""
    caminho = tmp_path / "dados.json"
    # Salva uma versão antiga para ter algo no disco
    salvar_json_atomico({"versao": 1}, caminho)

    replace_original = modulo.os.replace
    tentativas = []

    def replace_negado_nas_duas_primeiras_vezes(origem, destino):
        tentativas.append(1)
        if len(tentativas) <= 2:
            raise PermissionError("[WinError 5] Acesso negado")
        return replace_original(origem, destino)

    monkeypatch.setattr(modulo.os, "replace", replace_negado_nas_duas_primeiras_vezes)
    esperas = []
    monkeypatch.setattr(time, "sleep", esperas.append)

    salvar_json_atomico({"versao": 2}, caminho)

    assert len(tentativas) == 3  # 2 negadas + 1 que funcionou
    assert len(esperas) == 2  # esperou entre as tentativas
    assert json.loads(caminho.read_text(encoding="utf-8"))["versao"] == 2
    assert not caminho.with_suffix(".json.tmp").exists()


def test_salvar_json_atomico_relevanta_permission_error_se_nega_sempre(tmp_path, monkeypatch):
    """Testa que PermissionError é re-lançado se todas as tentativas falharem."""
    caminho = tmp_path / "dados.json"
    # Salva uma versão antiga
    salvar_json_atomico({"versao": 1}, caminho)

    tentativas = []

    def replace_sempre_negado(origem, destino):
        tentativas.append(1)
        raise PermissionError("[WinError 5] Acesso negado")

    monkeypatch.setattr(modulo.os, "replace", replace_sempre_negado)
    monkeypatch.setattr(time, "sleep", lambda segundos: None)

    with pytest.raises(PermissionError):
        salvar_json_atomico({"versao": 2}, caminho)

    assert len(tentativas) == 10  # desiste depois de 10 tentativas (padrão)
    assert json.loads(caminho.read_text(encoding="utf-8"))["versao"] == 1  # o antigo segue valido


def test_salvar_json_atomico_respeita_parametro_tentativas_customizado(tmp_path, monkeypatch):
    """Testa que o parâmetro tentativas_windows customiza a quantidade de tentativas."""
    caminho = tmp_path / "dados.json"
    salvar_json_atomico({"versao": 1}, caminho)

    tentativas = []

    def replace_sempre_negado(origem, destino):
        tentativas.append(1)
        raise PermissionError("[WinError 5] Acesso negado")

    monkeypatch.setattr(modulo.os, "replace", replace_sempre_negado)
    monkeypatch.setattr(time, "sleep", lambda segundos: None)

    with pytest.raises(PermissionError):
        salvar_json_atomico({"versao": 2}, caminho, tentativas_windows=5)

    assert len(tentativas) == 5  # desiste depois de 5 tentativas (customizado)


def test_salvar_json_atomico_respeita_parametro_espera_customizado(tmp_path, monkeypatch):
    """Testa que o parâmetro espera_entre_tentativas customiza o tempo de espera."""
    caminho = tmp_path / "dados.json"
    salvar_json_atomico({"versao": 1}, caminho)

    replace_original = modulo.os.replace
    tentativas = []

    def replace_negado_nas_duas_primeiras_vezes(origem, destino):
        tentativas.append(1)
        if len(tentativas) <= 2:
            raise PermissionError("[WinError 5] Acesso negado")
        return replace_original(origem, destino)

    monkeypatch.setattr(modulo.os, "replace", replace_negado_nas_duas_primeiras_vezes)
    esperas = []
    monkeypatch.setattr(time, "sleep", esperas.append)

    salvar_json_atomico({"versao": 2}, caminho, espera_entre_tentativas=0.1)

    assert esperas == [0.1, 0.1]  # espera com o valor customizado


def test_salvar_json_atomico_cria_pastas_que_nao_existem(tmp_path):
    """Testa que cria diretórios pais se não existirem."""
    caminho = tmp_path / "pasta" / "subpasta" / "dados.json"
    dados = {"chave": "valor"}

    salvar_json_atomico(dados, caminho)

    assert caminho.exists()
    assert caminho.read_text(encoding="utf-8")
