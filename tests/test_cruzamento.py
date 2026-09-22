# -*- coding: utf-8 -*-
from buscador.core.cruzamento import (
    RelatorioColapso,
    RelatorioCruzamento,
    colapsar_por_chave,
    enriquecer_de_outra_fonte,
    remover_duplicatas_exatas,
)


def _chave_por_link(registro):
    """extrair_chave de teste: usa o campo 'link' como chave, devolvendo
    None quando ele estiver ausente ou vazio (mesma convenção do resto do
    projeto: string vazia/None = 'sem chave extraível')."""
    return registro.get("link") or None


# ---------------------------------------------------------------------------
# enriquecer_de_outra_fonte
# ---------------------------------------------------------------------------

def test_enriquecer_copia_campos_quando_chave_bate():
    base = [{"link": "http://a", "titulo": "Livro A"}]
    fonte = [{"link": "http://a", "ano": "1900", "autor": "Fulano"}]

    resultado, relatorio = enriquecer_de_outra_fonte(
        base, fonte, _chave_por_link, ["ano", "autor"]
    )

    assert resultado == [
        {"link": "http://a", "titulo": "Livro A", "ano": "1900", "autor": "Fulano"}
    ]
    assert relatorio == RelatorioCruzamento(
        total_base=1, total_fonte=1, casados=1, chaves_nao_encontradas=[]
    )


def test_enriquecer_nao_sobrescreve_com_fonte_vazia():
    # A fonte TEM o campo "ano" pra essa chave, mas vazio -- não pode apagar
    # o valor que a base já tinha.
    base = [{"link": "http://a", "ano": "1850"}]
    fonte = [{"link": "http://a", "ano": ""}]

    resultado, relatorio = enriquecer_de_outra_fonte(
        base, fonte, _chave_por_link, ["ano"]
    )

    assert resultado == [{"link": "http://a", "ano": "1850"}]
    # a chave bateu (casou) -- só o campo vazio não foi copiado
    assert relatorio.casados == 1


def test_enriquecer_conta_chaves_sem_correspondencia():
    base = [{"link": "http://a"}, {"link": "http://b"}]
    fonte = [{"link": "http://a", "ano": "1900"}]

    resultado, relatorio = enriquecer_de_outra_fonte(
        base, fonte, _chave_por_link, ["ano"]
    )

    assert relatorio.total_base == 2
    assert relatorio.total_fonte == 1
    assert relatorio.casados == 1
    assert relatorio.chaves_nao_encontradas == ["http://b"]
    # shape uniforme: mesmo sem match, a linha ganha a chave "ano", com "" padrão
    assert resultado[1] == {"link": "http://b", "ano": ""}


def test_enriquecer_primeira_ocorrencia_na_fonte_ganha_em_caso_de_chave_repetida():
    base = [{"link": "http://a"}]
    fonte = [
        {"link": "http://a", "ano": "1900"},
        {"link": "http://a", "ano": "2000"},
    ]

    resultado, relatorio = enriquecer_de_outra_fonte(
        base, fonte, _chave_por_link, ["ano"]
    )

    assert resultado == [{"link": "http://a", "ano": "1900"}]
    assert relatorio.casados == 1


# ---------------------------------------------------------------------------
# colapsar_por_chave
# ---------------------------------------------------------------------------

def test_colapsar_mantem_so_a_primeira_linha_por_chave_por_padrao():
    registros = [
        {"link": "http://a", "titulo": "V1"},
        {"link": "http://a", "titulo": "V2"},
    ]

    resultado, relatorio = colapsar_por_chave(registros, _chave_por_link)

    assert resultado == [{"link": "http://a", "titulo": "V1"}]
    assert relatorio == RelatorioColapso(
        total_entrada=2, total_saida=1, grupos_colapsados=1, sem_chave=0
    )


def test_colapsar_aceita_funcao_escolher_customizada():
    registros = [
        {"link": "http://a", "titulo": "curto"},
        {"link": "http://a", "titulo": "titulo bem mais longo"},
    ]

    def escolher_titulo_mais_longo(grupo):
        return max(grupo, key=lambda r: len(r["titulo"]))

    resultado, relatorio = colapsar_por_chave(
        registros, _chave_por_link, escolher=escolher_titulo_mais_longo
    )

    assert resultado == [{"link": "http://a", "titulo": "titulo bem mais longo"}]
    assert relatorio.grupos_colapsados == 1


def test_colapsar_passa_direto_linhas_sem_chave():
    registros = [
        {"link": None, "titulo": "sem chave 1"},
        {"link": None, "titulo": "sem chave 2"},
    ]

    resultado, relatorio = colapsar_por_chave(registros, _chave_por_link)

    # nenhuma foi agrupada com a outra -- as duas passam direto, individualmente
    assert resultado == registros
    assert relatorio.total_entrada == 2
    assert relatorio.total_saida == 2
    assert relatorio.grupos_colapsados == 0
    assert relatorio.sem_chave == 2


# ---------------------------------------------------------------------------
# remover_duplicatas_exatas
# ---------------------------------------------------------------------------

def test_remover_duplicatas_exatas_remove_so_linhas_byte_a_byte_iguais():
    registros = [
        {"link": "http://a", "titulo": "X"},
        {"link": "http://a", "titulo": "X"},
    ]

    resultado, quantidade_removida = remover_duplicatas_exatas(registros)

    assert resultado == [{"link": "http://a", "titulo": "X"}]
    assert quantidade_removida == 1


def test_remover_duplicatas_exatas_mantem_linhas_parecidas_mas_diferentes():
    # mesma chave (link), mas um campo diferente -- não é duplicata exata
    registros = [
        {"link": "http://a", "titulo": "X"},
        {"link": "http://a", "titulo": "Y"},
    ]

    resultado, quantidade_removida = remover_duplicatas_exatas(registros)

    assert resultado == registros
    assert quantidade_removida == 0
