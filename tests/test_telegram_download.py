# -*- coding: utf-8 -*-
"""Testes de core/telegram_download.py -- pastas temporárias, sem internet.

O teste do download de verdade roda o scripts/telegram/baixar_topico.sh
com um "tdl de mentira" (um script Python que só cria os arquivos), então
só roda onde houver bash (Linux/Mac, ou o Git Bash no Windows)."""
import json
import os
import stat
import sys
from datetime import datetime

import pytest

from buscador.core import telegram_download as dl

CHAT = 2136545743


def msg(id_, nome, mime="application/pdf", tamanho=1000, data=datetime(2025, 3, 12, 10)):
    return {"id": id_, "type": "message", "file": nome, "date": int(data.timestamp()),
            "raw": {"Message": "", "Media": {"Document": {
                "MimeType": mime, "Size": tamanho, "Attributes": [{"FileName": nome}]}}}}


def lista_exemplo():
    return {"id": CHAT, "messages": [
        msg(1, "Summa.pdf", tamanho=2 * 1024**2),
        msg(2, "Confissoes.epub", mime="application/epub+zip"),
        msg(3, "Pacote.rar", mime="application/vnd.rar"),
        msg(4, "sem_extensao", mime="application/octet-stream"),
    ]}


def gravar(caminho, dados):
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(json.dumps(dados), encoding="utf-8")


def test_pastas_de_topico_e_de_conversa(tmp_path):
    assert dl.nome_alvo(CHAT, 783) == "topico_783"
    assert dl.nome_alvo(CHAT, None) == f"chat_{CHAT}"
    pasta = dl.pasta_alvo(tmp_path, CHAT, 81988)
    # mesmo caminho que o telegram.bat (caminho_lista_padrao) já usa
    assert dl.caminho_lista(pasta) == tmp_path / "topico_81988" / "topico_81988_lista_busca.json"
    assert dl.pasta_arquivos(pasta) == tmp_path / "topico_81988" / "arquivos"


def test_ids_baixados_inclui_repetidos_e_ignora_tmp(tmp_path):
    arq = tmp_path / "arquivos"
    (arq / "repetidos").mkdir(parents=True)
    (arq / "10_Summa.pdf").write_text("x")
    (arq / "11_meio.pdf.tmp").write_text("x")
    (arq / "leia-me.txt").write_text("x")
    (arq / "repetidos" / "Apparatus - msg 60824.pdf").write_text("x")
    (arq / "repetidos" / "sem ext - msg 7").write_text("x")
    assert dl.ids_baixados(arq) == {10, 60824, 7}
    assert dl.ids_baixados(tmp_path / "nao_existe") == set()


def test_situacao(tmp_path):
    pasta = tmp_path / "topico_1"
    assert dl.situacao(pasta) == "não listado"
    gravar(dl.caminho_lista(pasta), lista_exemplo())
    assert dl.situacao(pasta) == "lista pronta"
    (dl.pasta_arquivos(pasta)).mkdir()
    (dl.pasta_arquivos(pasta) / "1_Summa.pdf").write_text("x")
    assert dl.situacao(pasta) == "baixado em parte (1 de 4)"
    for n in (2, 3, 4):
        (dl.pasta_arquivos(pasta) / f"{n}_x").write_text("x")
    assert dl.situacao(pasta) == "baixado"
    assert dl.situacao(pasta, rodando=True) == "baixando"


def test_tipo_arquivo():
    assert dl.tipo_arquivo("a.PDF", "") == "PDF"
    assert dl.tipo_arquivo("a", "application/pdf") == "PDF"
    assert dl.tipo_arquivo("a.epub", "application/epub+zip") == "EPUB/MOBI"
    assert dl.tipo_arquivo("a.rar", "") == "RAR/ZIP"
    assert dl.tipo_arquivo("a", "application/octet-stream") == "Outros"


def test_linhas_da_lista_marca_so_o_que_falta():
    linhas = dl.linhas_da_lista(lista_exemplo(), baixados={1})
    assert [l["baixar"] for l in linhas] == [False, True, True, True]
    assert [l["ja_baixado"] for l in linhas] == [True, False, False, False]
    assert linhas[0]["tipo"] == "PDF" and linhas[0]["tamanho_mb"] == 2.0
    assert linhas[0]["data"] == "12/03/2025"
    assert [l["tipo"] for l in linhas[1:]] == ["EPUB/MOBI", "RAR/ZIP", "Outros"]


def test_marcados_mantem_formato_com_raw_e_progresso(tmp_path):
    pasta = tmp_path / "topico_1"
    assert dl.progresso(pasta) is None
    destino = dl.gravar_marcados(lista_exemplo(), [1, 3], pasta)
    marcados = json.loads(destino.read_text(encoding="utf-8"))
    assert marcados["id"] == CHAT
    assert [m["id"] for m in marcados["messages"]] == [1, 3]
    assert marcados["messages"][0]["raw"]["Media"]["Document"]["Size"] == 2 * 1024**2
    dl.pasta_arquivos(pasta).mkdir()
    (dl.pasta_arquivos(pasta) / "1_Summa.pdf").write_text("x")
    (dl.pasta_arquivos(pasta) / "2_nao_marcado.epub").write_text("x")
    assert dl.progresso(pasta) == {"baixados": 1, "total": 2,
                                   "bytes_baixados": 2 * 1024**2,
                                   "bytes_total": 2 * 1024**2 + 1000}


def test_ultimas_linhas(tmp_path):
    log = tmp_path / "rodadas.log"
    assert dl.ultimas_linhas(log) == []
    log.write_text("\n".join(f"linha {i}" for i in range(20)), encoding="utf-8")
    assert dl.ultimas_linhas(log, 2) == ["linha 18", "linha 19"]


def test_download_rodando_pelo_pid_e_pelo_log(tmp_path, monkeypatch):
    pasta = tmp_path / "topico_1"
    pasta.mkdir()
    assert dl.download_rodando(pasta) is False  # sem download.pid
    dl.caminho_pid(pasta).write_text("12345")
    monkeypatch.setattr(dl, "processo_vivo", lambda pid: True)
    assert dl.download_rodando(pasta) is True
    dl.caminho_log(pasta).write_text("10:00 rodada 1\nCOMPLETO\n")
    assert dl.download_rodando(pasta) is False  # o log diz que acabou
    dl.caminho_log(pasta).write_text("10:00 rodada 1\n")
    monkeypatch.setattr(dl, "processo_vivo", lambda pid: None)
    assert dl.download_rodando(pasta) is None  # não deu para saber
    dl.caminho_pid(pasta).write_text("lixo")
    assert dl.download_rodando(pasta) is None


def test_processo_vivo_do_proprio_python():
    assert dl.processo_vivo(os.getpid()) is True


def test_montar_comando_usa_barras_normais(tmp_path):
    comando = dl.montar_comando(tmp_path / "bash", tmp_path / "l.json", tmp_path / "arq",
                                tmp_path / "r.log", script=tmp_path / "s.sh")
    assert comando[0] == str(tmp_path / "bash")
    assert all("\\" not in parte for parte in comando[1:])
    assert comando[1].endswith("/s.sh")


def test_comando_planilha_conversa_sem_topico(tmp_path):
    comando = dl.comando_planilha(tmp_path / "l.json", tmp_path / "s.xlsx", CHAT, None,
                                  "Nome", "Grupo")
    assert comando[0] == sys.executable
    assert comando[4:] == ["0", "Nome", str(CHAT), "Grupo"]


def test_planilha_de_verdade(tmp_path):
    """Roda o planilha_topico.py com o chat por argumento."""
    import subprocess
    from openpyxl import load_workbook
    lista = tmp_path / "l.json"
    gravar(lista, lista_exemplo())
    saida = tmp_path / "s.xlsx"
    r = subprocess.run(dl.comando_planilha(lista, saida, 999, None, "Conversa", "Meu grupo"),
                       capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stderr
    wb = load_workbook(saida)
    assert wb["Resumo"]["A1"].value == "Conversa: Meu grupo"
    assert wb["Arquivos"]["H2"].hyperlink.target == "https://t.me/c/999/1"


# --- repetidos -----------------------------------------------------------------

def test_repetidos_so_com_conteudo_identico(tmp_path):
    arq = tmp_path / "arquivos"
    arq.mkdir()
    (arq / "10_Livro.pdf").write_bytes(b"conteudo A")
    (arq / "20_Livro.pdf").write_bytes(b"conteudo A")    # cópia de verdade
    (arq / "30_Apparatus.pdf").write_bytes(b"conteudo B")
    (arq / "31_Apparatus.pdf").write_bytes(b"conteudo C")  # mesmo tamanho, outro conteúdo
    (arq / "40_unico.pdf").write_bytes(b"x")
    grupos = dl.achar_repetidos(arq)
    assert [[p.name for p in g] for g in grupos] == [["10_Livro.pdf", "20_Livro.pdf"]]

    movidos = dl.mover_repetidos(grupos, arq)
    assert len(movidos) == 2
    assert sorted(p.name for p in (arq / "repetidos").iterdir()) == \
        ["Livro - msg 10.pdf", "Livro - msg 20.pdf"]
    assert not (arq / "10_Livro.pdf").exists()
    # continuam contando como baixados (o script não baixa de novo)
    assert {10, 20} <= dl.ids_baixados(arq)


def test_mover_repetidos_nunca_escreve_por_cima(tmp_path):
    arq = tmp_path / "arquivos"
    (arq / "repetidos").mkdir(parents=True)
    (arq / "repetidos" / "Livro - msg 10.pdf").write_bytes(b"antigo")
    (arq / "10_Livro.pdf").write_bytes(b"novo")
    assert dl.mover_repetidos([[arq / "10_Livro.pdf"]], arq) == []
    assert (arq / "repetidos" / "Livro - msg 10.pdf").read_bytes() == b"antigo"
    assert (arq / "10_Livro.pdf").exists()


def test_nome_em_repetidos():
    assert dl.nome_em_repetidos("60824_Apparatus philosophicus.pdf") == \
        "Apparatus philosophicus - msg 60824.pdf"
    assert dl.nome_em_repetidos("sem_numero.pdf") == "sem_numero.pdf"


# --- o download de verdade (com tdl de mentira) -----------------------------------

TDL_FALSO = '''#!{python}
"""tdl de mentira: lê a lista (-f) e cria "<id>_<nome>" na pasta (-d)."""
import json, sys
args = sys.argv[1:]
lista = json.load(open(args[args.index("-f") + 1], encoding="utf-8"))
destino = args[args.index("-d") + 1]
for m in lista["messages"]:
    open(f"{{destino}}/{{m['id']}}_{{m['file']}}", "w").write("conteudo")
'''


def _executavel(caminho, texto):
    caminho.write_text(texto, encoding="utf-8")
    caminho.chmod(caminho.stat().st_mode | stat.S_IEXEC)
    return caminho


@pytest.mark.skipif(os.name == "nt" or dl.achar_bash() is None, reason="precisa de bash")
def test_baixar_topico_sh_com_tdl_falso(tmp_path):
    tdl = _executavel(tmp_path / "tdl_falso.py", TDL_FALSO.format(python=sys.executable))
    pasta = tmp_path / "topico_1"
    # a mensagem 2 já foi baixada antes e movida para repetidos/
    (dl.pasta_arquivos(pasta) / "repetidos").mkdir(parents=True)
    (dl.pasta_arquivos(pasta) / "repetidos" / "Confissoes - msg 2.epub").write_text("x")
    dl.gravar_marcados(lista_exemplo(), [1, 2, 3], pasta)

    pid = dl.iniciar_download(pasta, dl.achar_bash(), ambiente_extra={"TDL": str(tdl)})
    assert dl.caminho_pid(pasta).read_text() == str(pid)
    assert dl._PROCESSOS[pid].wait(timeout=60) == 0

    nomes = sorted(p.name for p in dl.pasta_arquivos(pasta).iterdir() if p.is_file())
    assert nomes == ["1_Summa.pdf", "3_Pacote.rar"]  # o 2 não veio de novo
    log = dl.ultimas_linhas(dl.caminho_log(pasta), 20)
    assert log[0].endswith("iniciado pelo aplicativo")
    assert log[-1] == "COMPLETO"
    assert dl.download_rodando(pasta) is False
    assert dl.progresso(pasta)["baixados"] == 3


@pytest.mark.skipif(os.name == "nt" or dl.achar_bash() is None, reason="precisa de bash")
def test_nao_deixa_iniciar_dois_downloads_do_mesmo_topico(tmp_path):
    demorado = _executavel(tmp_path / "demorado.sh", "#!/usr/bin/env bash\nsleep 30\n")
    pasta = tmp_path / "topico_1"
    dl.gravar_marcados(lista_exemplo(), [1], pasta)
    pid = dl.iniciar_download(pasta, dl.achar_bash(), script=demorado)
    try:
        assert dl.download_rodando(pasta) is True
        with pytest.raises(RuntimeError, match="Já existe"):
            dl.iniciar_download(pasta, dl.achar_bash(), script=demorado)
    finally:
        dl._PROCESSOS[pid].kill()
        dl._PROCESSOS[pid].wait()
    assert dl.download_rodando(pasta) is False


def test_sem_lista_de_marcados_recusa(tmp_path):
    with pytest.raises(RuntimeError, match="Marque os arquivos"):
        dl.iniciar_download(tmp_path / "topico_1", tmp_path / "bash")
