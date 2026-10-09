# -*- coding: utf-8 -*-
"""Testes do mapeamento em segundo plano (core/mapear_segundo_plano.py),
sem rodar o motor de verdade: um "Popen falso" faz o papel do processo."""
import datetime
import sys
from pathlib import Path

import pytest

from buscador.core import mapear_segundo_plano as msp
from buscador.core import resumo_saidas


@pytest.fixture
def saidas(tmp_path, monkeypatch):
    monkeypatch.setattr(resumo_saidas, "SAIDAS", tmp_path)
    monkeypatch.setattr(msp, "_PROCESSOS", {})
    return tmp_path


class PopenFalso:
    """Faz de conta que é um processo. "codigo" None = ainda rodando."""
    def __init__(self, comando, **kwargs):
        self.comando = comando
        self.kwargs = kwargs
        self.pid = 4242
        self.codigo = None

    def poll(self):
        return self.codigo


def test_montar_consulta_gallica_embrulha_nome_simples():
    assert msp.montar_consulta("gallica", " Clavius ") == 'gallica all "Clavius"'


@pytest.mark.parametrize("cql", ['dc.creator all "Clavius"', 'gallica any "x"',
                                 "https://gallica.bnf.fr/SRU?query=a"])
def test_montar_consulta_gallica_deixa_cql_como_esta(cql):
    assert msp.montar_consulta("gallica", cql) == cql


def test_montar_consulta_recusa_vazio_e_forum_sem_url():
    with pytest.raises(ValueError):
        msp.montar_consulta("gallica", "  ")
    with pytest.raises(ValueError, match="URL"):
        msp.montar_consulta("phpbb", "tópico tal")
    assert msp.montar_consulta("internet_archive", "subject:x") == "subject:x"


def test_montar_comando_igual_ao_do_terminal():
    comando = msp.montar_comando("gallica", 'gallica all "x"', Path("s/a.xlsx"), python="py")
    assert comando == ["py", "-m", "buscador.cli", 'gallica all "x"', "--adapter", "gallica",
                       "--saida", str(Path("s/a.xlsx"))]


def test_nome_da_saida_tem_data_e_hora():
    assert msp.nome_da_saida("phpbb", datetime.datetime(2026, 10, 9, 14, 5, 7)) == "phpbb_2026-10-09_140507.xlsx"


def test_iniciar_grava_ficha_e_log_e_acompanha_o_processo(saidas):
    criados = []

    def abrir(comando, **kwargs):
        criados.append(PopenFalso(comando, **kwargs))
        return criados[-1]

    ficha = msp.iniciar_mapeamento("gallica", 'gallica all "x"', nome_site="Gallica", abrir_processo=abrir)
    processo = criados[0]
    assert processo.comando[0] == sys.executable and processo.comando[3] == 'gallica all "x"'
    assert processo.kwargs["env"]["PYTHONUNBUFFERED"] == "1"
    assert Path(ficha["saida"]).parent == saidas
    assert msp.ultimo_mapeamento() == ficha
    assert "Comando:" in msp.ler_fim_do_log(ficha)
    assert msp.situacao(ficha) == "rodando"

    # terminou bem e a planilha existe -> concluído
    processo.codigo = 0
    Path(ficha["saida"]).write_bytes(b"xlsx")
    assert msp.situacao(ficha) == "concluido"
    # terminou com código de erro -> erro
    processo.codigo = 1
    assert msp.situacao(ficha) == "erro"


def test_situacao_sem_processo_na_memoria_deduz_pelo_log(saidas):
    log = saidas / "m.log"
    saida = saidas / "m.xlsx"
    ficha = {"id": "m", "log": str(log), "saida": str(saida)}
    log.write_text("Comando: ...\n", encoding="utf-8")
    assert msp.situacao(ficha) == "desconhecido"
    log.write_text("Não deu para continuar: erro\n", encoding="utf-8")
    assert msp.situacao(ficha) == "erro"
    log.write_text("Preciso da sua ajuda (Gallica): faça login\n", encoding="utf-8")
    assert msp.situacao(ficha) == "erro"
    saida.write_bytes(b"x")
    log.write_text(f"3 itens encontrados. Planilha salva em: {saida}\n", encoding="utf-8")
    assert msp.situacao(ficha) == "concluido"


def test_ultimo_mapeamento_sem_nenhum(saidas):
    assert msp.ultimo_mapeamento() is None
