# -*- coding: utf-8 -*-
"""
Motor genérico de cruzamento e deduplicação de listas de registros
(dicionários), pluggável por site.

Este módulo é GENÉRICO: não é específico da Gallica, não importa nada de
`chaves_gallica.py`. Quem chama passa a função `extrair_chave` (que sabe
extrair a chave canônica de UM registro, específica de cada site) como
parâmetro -- é infraestrutura reutilizável, pensada pra cruzar listas de
outros sites no futuro, não só Gallica.

Todas as funções aqui são puras (sem I/O, sem mutar as listas/dicts que
recebem): sempre devolvem listas/dicionários novos.
"""
from dataclasses import dataclass, field
from typing import Callable, Optional


@dataclass
class RelatorioCruzamento:
    total_base: int
    total_fonte: int
    casados: int
    chaves_nao_encontradas: list[str] = field(default_factory=list)


def enriquecer_de_outra_fonte(
    base: list[dict],
    fonte: list[dict],
    extrair_chave: Callable[[dict], Optional[str]],
    campos_para_copiar: list[str],
) -> tuple[list[dict], RelatorioCruzamento]:
    """Enriquece cada linha de `base` com campos vindos de `fonte`, casando
    as duas listas pela chave que `extrair_chave` extrai de cada registro.

    Regras de comportamento (não óbvias, testadas em test_cruzamento.py):
    - Se duas linhas de `fonte` batem na mesma chave, a PRIMEIRA ocorrência
      ganha (mesma convenção de `coleta_csv.py::carregar_itens_csv`, que
      dedupa por link mantendo a primeira ocorrência).
    - Um campo só é copiado de `fonte` pra `base` se estiver presente E
      não-vazio na fonte -- nunca sobrescreve um valor já existente na base
      com uma string vazia.
    - Toda linha de saída ganha as chaves de `campos_para_copiar`, mesmo
      quando não há match (usa "" como valor padrão nesse caso), pra manter
      o formato (shape) uniforme entre todas as linhas de saída.
    """
    # Constrói um índice chave -> registro da fonte, aplicando "primeira
    # ocorrência ganha": se a chave já está no índice, ignora as próximas
    # linhas da fonte com a mesma chave. Registros sem chave extraível
    # (None) nunca entram no índice -- não tem como casar com eles.
    indice_fonte: dict[str, dict] = {}
    for registro_fonte in fonte:
        chave = extrair_chave(registro_fonte)
        if chave is None:
            continue
        if chave not in indice_fonte:
            indice_fonte[chave] = registro_fonte

    saida: list[dict] = []
    casados = 0
    chaves_nao_encontradas: list[str] = []

    for registro_base in base:
        nova_linha = dict(registro_base)  # copia -- não muta a linha original
        # Garante o shape uniforme: toda linha de saída tem as chaves de
        # campos_para_copiar, mesmo que não haja match (default "").
        # setdefault não mexe em valores que a linha já tinha.
        for campo in campos_para_copiar:
            nova_linha.setdefault(campo, "")

        chave = extrair_chave(registro_base)
        registro_fonte = indice_fonte.get(chave) if chave is not None else None

        if registro_fonte is not None:
            casados += 1
            for campo in campos_para_copiar:
                valor_fonte = registro_fonte.get(campo)
                if valor_fonte:  # presente E não-vazio (None e "" são falsy)
                    nova_linha[campo] = valor_fonte
        elif chave is not None:
            # Teve chave extraível, mas não achou correspondência na fonte.
            # Uma linha sem chave extraível (chave is None) não entra aqui:
            # não há uma string de chave pra reportar, e a ausência de
            # chave não é a mesma coisa que "chave não encontrada" na fonte.
            chaves_nao_encontradas.append(chave)

        saida.append(nova_linha)

    relatorio = RelatorioCruzamento(
        total_base=len(base),
        total_fonte=len(fonte),
        casados=casados,
        chaves_nao_encontradas=chaves_nao_encontradas,
    )
    return saida, relatorio


@dataclass
class RelatorioColapso:
    total_entrada: int
    total_saida: int
    grupos_colapsados: int  # quantas chaves tinham >1 linha
    sem_chave: int  # linhas sem chave extraivel, mantidas como estao


def colapsar_por_chave(
    registros: list[dict],
    extrair_chave: Callable[[dict], Optional[str]],
    escolher: Optional[Callable[[list[dict]], dict]] = None,
) -> tuple[list[dict], RelatorioColapso]:
    """Colapsa `registros` em um por chave (usando `extrair_chave`),
    devolvendo uma linha por chave distinta.

    Regras de comportamento (não óbvias, testadas em test_cruzamento.py):
    - Linhas sem chave (extrair_chave devolve None) passam direto pro
      resultado, sem serem agrupadas com nada -- cada uma é contada
      individualmente em `sem_chave`.
    - `escolher` decide qual linha representa um grupo com mais de uma
      linha; se não for passado, o padrão é manter a PRIMEIRA linha de
      cada grupo (mesma convenção de "primeira ganha" do resto do
      projeto).
    - A ordem de saída preserva a posição da primeira aparição de cada
      chave (e a posição original das linhas sem chave).
    """
    # Guarda, na ordem de primeira aparição, as linhas de cada chave.
    grupos: dict[str, list[dict]] = {}
    # A saída é montada com placeholders (None) nas posições dos grupos,
    # preenchidos depois com o representante escolhido -- assim a ordem de
    # saída acompanha a ordem de primeira aparição de cada chave, e as
    # linhas sem chave ficam exatamente na posição em que apareceram.
    saida: list = []
    posicao_do_grupo: dict[str, int] = {}
    sem_chave = 0

    for registro in registros:
        chave = extrair_chave(registro)
        if chave is None:
            saida.append(registro)
            sem_chave += 1
            continue
        if chave not in grupos:
            grupos[chave] = []
            saida.append(None)  # placeholder, preenchido no passo seguinte
            posicao_do_grupo[chave] = len(saida) - 1
        grupos[chave].append(registro)

    grupos_colapsados = 0
    for chave, linhas_do_grupo in grupos.items():
        if len(linhas_do_grupo) > 1:
            grupos_colapsados += 1
        representante = escolher(linhas_do_grupo) if escolher else linhas_do_grupo[0]
        saida[posicao_do_grupo[chave]] = representante

    relatorio = RelatorioColapso(
        total_entrada=len(registros),
        total_saida=len(saida),
        grupos_colapsados=grupos_colapsados,
        sem_chave=sem_chave,
    )
    return saida, relatorio


def remover_duplicatas_exatas(registros: list[dict]) -> tuple[list[dict], int]:
    """Remove linhas que são duplicatas EXATAS (todos os campos idênticos,
    campo a campo, não só a chave canônica) de outra linha já vista,
    mantendo a primeira ocorrência.

    Devolve a lista sem duplicatas e a QUANTIDADE de linhas removidas por
    serem duplicatas (não a contagem de linhas únicas) -- assim quem chama
    pode logar "removidas N duplicatas" diretamente.
    """
    vistos: set = set()
    saida: list[dict] = []
    removidos = 0

    for registro in registros:
        # tuple(sorted(...)) dá uma "impressão digital" do dict inteiro,
        # comparável e hasheável, pra guardar num set -- ordena pelos nomes
        # dos campos (chaves do dict), que são sempre strings e únicas
        # dentro do dict, então nunca precisa desempatar comparando valores.
        impressao = tuple(sorted(registro.items()))
        if impressao in vistos:
            removidos += 1
            continue
        vistos.add(impressao)
        saida.append(registro)

    return saida, removidos
