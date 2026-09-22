# -*- coding: utf-8 -*-
import hashlib
import json

import pytest

from buscador.core.baixar_gallica import (
    CheckpointDownload,
    baixar_lote,
    baixar_um,
    carregar_ou_criar_checkpoint,
    salvar_checkpoint,
)


def _sha256_esperado(conteudo: bytes) -> str:
    return hashlib.sha256(conteudo).hexdigest()


def _baixar_fct_fake(conteudos_por_ark, nomes_arquivo=None):
    """Constroi uma baixar_fct falsa (mesma assinatura de
    baixar_via_navegador: recebe ark_id e pasta_destino) que escreve um
    arquivo de conteudo conhecido na pasta_destino e devolve o Path -- pra
    testar baixar_um/baixar_lote sem abrir navegador nenhum. nomes_arquivo
    permite simular o nome real que a Gallica da ao arquivo (diferente de
    "<ark_id>.pdf", como acontece de verdade -- ver baixar_via_navegador)."""
    def _fake(ark_id, pasta_destino):
        conteudo = conteudos_por_ark[ark_id]
        nome = (nomes_arquivo or {}).get(ark_id, f"{ark_id}.pdf")
        caminho = pasta_destino / nome
        caminho.write_bytes(conteudo)
        return caminho
    return _fake


# --- baixar_um -----------------------------------------------------------


def test_baixar_um_calcula_sha256_do_arquivo_ja_em_disco(tmp_path):
    conteudo = b"%PDF-1.4 conteudo de teste"
    fake = _baixar_fct_fake({"abc123": conteudo})

    info = baixar_um("abc123", tmp_path, baixar_fct=fake)

    assert info["sha256"] == _sha256_esperado(conteudo)
    assert info["bytes"] == len(conteudo)
    assert info["caminho_local"] == str(tmp_path / "abc123.pdf")
    assert "baixado_em" in info


def test_baixar_um_renomeia_pro_nome_canonico_ark_id_pdf(tmp_path):
    # a Gallica da ao arquivo um nome real (com titulo, nao so o ark id) --
    # ver a confirmacao ao vivo da C-nav8/C-nav1 -- baixar_um precisa
    # renomear pro padrao <ark_id>.pdf antes de catalogar.
    conteudo = b"%PDF-1.4 outro conteudo"
    fake = _baixar_fct_fake(
        {"abc123": conteudo}, nomes_arquivo={"abc123": "Titulo_Real_Longo_abc123.pdf"}
    )

    info = baixar_um("abc123", tmp_path, baixar_fct=fake)

    assert info["caminho_local"] == str(tmp_path / "abc123.pdf")
    assert (tmp_path / "abc123.pdf").exists()
    assert not (tmp_path / "Titulo_Real_Longo_abc123.pdf").exists()


# --- carregar_ou_criar_checkpoint -----------------------------------------


def test_carregar_ou_criar_checkpoint_cria_novo_do_zero(tmp_path):
    caminho = tmp_path / "checkpoint_download.json"

    checkpoint = carregar_ou_criar_checkpoint(caminho, total_arks=10)

    assert checkpoint == CheckpointDownload(total_arks=10, atualizado_em=checkpoint.atualizado_em)
    assert caminho.exists()  # já grava o checkpoint inicial em disco


def test_carregar_ou_criar_checkpoint_retoma_do_que_ja_existe(tmp_path):
    caminho = tmp_path / "checkpoint_download.json"
    original = CheckpointDownload(total_arks=5, proximo_indice=3, baixados=3)
    salvar_checkpoint(original, caminho)

    retomado = carregar_ou_criar_checkpoint(caminho, total_arks=5)

    assert retomado.proximo_indice == 3
    assert retomado.baixados == 3


def test_carregar_ou_criar_checkpoint_recusa_total_arks_divergente(tmp_path):
    caminho = tmp_path / "checkpoint_download.json"
    salvar_checkpoint(CheckpointDownload(total_arks=5, proximo_indice=2), caminho)

    with pytest.raises(ValueError):
        carregar_ou_criar_checkpoint(caminho, total_arks=8)


# --- baixar_lote -----------------------------------------------------------


def test_baixar_lote_baixa_todos_e_cataloga(tmp_path):
    ark_ids = ["a1", "a2", "a3"]
    conteudos = {ark: f"%PDF-1.4 conteudo {ark}".encode() for ark in ark_ids}
    fake = _baixar_fct_fake(conteudos)

    checkpoint = baixar_lote(
        ark_ids,
        diretorio_job=tmp_path / "job",
        pasta_destino=tmp_path / "baixados",
        caminho_catalogo=tmp_path / "catalogo.json",
        baixar_fct=fake,
        dormir=lambda s: None,
    )

    assert checkpoint.concluido is True
    assert checkpoint.baixados == 3
    assert checkpoint.falhas == 0

    catalogo = json.loads((tmp_path / "catalogo.json").read_text(encoding="utf-8"))
    assert set(catalogo.keys()) == set(ark_ids)
    for ark in ark_ids:
        assert catalogo[ark]["sha256"] == _sha256_esperado(conteudos[ark])


def test_baixar_lote_pula_item_ja_catalogado_com_sucesso(tmp_path):
    caminho_catalogo = tmp_path / "catalogo.json"
    caminho_catalogo.write_text(
        json.dumps({"a1": {"sha256": "ja-tinha", "bytes": 1, "caminho_local": "x", "baixado_em": "x"}}),
        encoding="utf-8",
    )
    ark_ids = ["a1", "a2"]
    conteudos = {"a2": b"%PDF-1.4 conteudo a2"}
    fake = _baixar_fct_fake(conteudos)
    chamadas = []
    fake_com_registro = lambda ark_id, pasta: (chamadas.append(ark_id), fake(ark_id, pasta))[1]

    checkpoint = baixar_lote(
        ark_ids,
        diretorio_job=tmp_path / "job",
        pasta_destino=tmp_path / "baixados",
        caminho_catalogo=caminho_catalogo,
        baixar_fct=fake_com_registro,
        dormir=lambda s: None,
    )

    assert chamadas == ["a2"]  # a1 nunca foi baixado de novo
    assert checkpoint.baixados == 1  # só a2 contou como baixado nesta rodada


def test_baixar_lote_falha_isolada_nao_derruba_o_lote(tmp_path):
    ark_ids = ["a1", "a2", "a3"]

    def fake_com_falha(ark_id, pasta_destino):
        if ark_id == "a2":
            raise RuntimeError("navegador travou nesse item")
        caminho = pasta_destino / f"{ark_id}.pdf"
        caminho.write_bytes(f"conteudo {ark_id}".encode())
        return caminho

    checkpoint = baixar_lote(
        ark_ids,
        diretorio_job=tmp_path / "job",
        pasta_destino=tmp_path / "baixados",
        caminho_catalogo=tmp_path / "catalogo.json",
        baixar_fct=fake_com_falha,
        dormir=lambda s: None,
    )

    assert checkpoint.concluido is True
    assert checkpoint.baixados == 2
    assert checkpoint.falhas == 1
    catalogo = json.loads((tmp_path / "catalogo.json").read_text(encoding="utf-8"))
    assert set(catalogo.keys()) == {"a1", "a3"}  # a2 falhou, fica fora do catálogo


def test_baixar_lote_retomada_apos_interrupcao_nao_perde_nem_duplica(tmp_path):
    ark_ids = ["a1", "a2", "a3", "a4"]
    diretorio_job = tmp_path / "job"
    pasta_destino = tmp_path / "baixados"
    caminho_catalogo = tmp_path / "catalogo.json"

    chamadas = []

    def fake_com_interrupcao(ark_id, pasta):
        chamadas.append(ark_id)
        if ark_id == "a3":
            raise KeyboardInterrupt("simulando interrupcao no meio do lote")
        caminho = pasta / f"{ark_id}.pdf"
        caminho.write_bytes(f"conteudo {ark_id}".encode())
        return caminho

    with pytest.raises(KeyboardInterrupt):
        baixar_lote(
            ark_ids, diretorio_job, pasta_destino, caminho_catalogo,
            baixar_fct=fake_com_interrupcao, dormir=lambda s: None,
        )

    assert chamadas == ["a1", "a2", "a3"]  # parou exatamente no item que interrompeu

    # retoma: a1/a2 já catalogados não devem ser re-baixados; a3 (que
    # nunca chegou a ser catalogado, pois a exceção interrompeu antes do
    # catálogo ser salvo) e a4 devem ser processados agora
    def fake_retomada(ark_id, pasta):
        chamadas.append(ark_id)
        caminho = pasta / f"{ark_id}.pdf"
        caminho.write_bytes(f"conteudo {ark_id}".encode())
        return caminho

    chamadas.clear()
    checkpoint = baixar_lote(
        ark_ids, diretorio_job, pasta_destino, caminho_catalogo,
        baixar_fct=fake_retomada, dormir=lambda s: None,
    )

    # a1/a2 pulados (já catalogados antes da interrupção); a3 e a4 processados
    # nesta mesma chamada (baixar_lote só devolve quando concluido=True ou
    # levanta uma exceção -- não para sozinho no meio sem motivo)
    assert chamadas == ["a3", "a4"]
    assert checkpoint.concluido is True
    catalogo = json.loads(caminho_catalogo.read_text(encoding="utf-8"))
    assert set(catalogo.keys()) == {"a1", "a2", "a3", "a4"}
