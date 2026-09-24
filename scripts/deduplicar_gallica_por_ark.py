# -*- coding: utf-8 -*-
"""Deduplica `saidas/gallica_mapa_livros.json` por ark_id (identificador
canonico da obra na Gallica), colapsando as multiplas ocorrencias que uma
mesma obra ganha quando o rastreador (mapear_gallica_selecoes_prototipo.py)
a encontra sob mais de uma trilha de navegacao/categoria.

Por que isso e necessario: o arquivo bruto tem 46.222 itens, mas a Gallica
cruza links entre categorias diferentes -- o mesmo livro pode aparecer sob
"Livres > Bande dessinee > ..." e tambem sob "Livres > Abecedaires > ..." ao
mesmo tempo, por exemplo. Contando por ark_id (nao por posicao na lista),
sao so 26.544 obras unicas de verdade. Ja confirmado ao vivo (nao precisa
reconferir): TODOS os 46.222 itens tem ark_id extraivel por
extrair_ark_id -- zero itens sem chave, zero caso de borda.

Este script nao reimplementa a logica de dedup: usa
buscador.core.cruzamento.colapsar_por_chave, ja testada em
tests/test_cruzamento.py, que mantem a PRIMEIRA ocorrencia de cada chave.

Roda direto, sem argumento de linha de comando:
    .venv/Scripts/python.exe scripts/deduplicar_gallica_por_ark.py
"""
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "src"))

from buscador.core.chaves_gallica import extrair_ark_id
from buscador.core.cruzamento import colapsar_por_chave

JSON_ORIGEM = RAIZ / "saidas" / "gallica_mapa_livros.json"
SAIDA = RAIZ / "saidas" / "gallica_mapa_livros_dedupado.json"

TOTAL_ESPERADO = 26544


def _extrair_chave(item: dict):
    return extrair_ark_id(item.get("link"))


def main():
    registros = json.loads(JSON_ORIGEM.read_text(encoding="utf-8"))

    deduplicados, relatorio = colapsar_por_chave(registros, _extrair_chave)

    # Acrescenta o ark_id em cada item de saida, pra quem for reaproveitar
    # depois nao precisar recalcular a partir do link.
    for item in deduplicados:
        item["ark_id"] = _extrair_chave(item)

    print(f"total_entrada:     {relatorio.total_entrada}")
    print(f"total_saida:       {relatorio.total_saida}")
    print(f"grupos_colapsados: {relatorio.grupos_colapsados}")
    print(f"sem_chave:         {relatorio.sem_chave}")

    # Verificacao obrigatoria: ja confirmamos ao vivo que TODOS os itens tem
    # ark_id extraivel, entao o numero final tem que bater exato. Se nao
    # bater, algo mudou (arquivo de origem diferente, regex quebrou etc.) --
    # nao seguir em frente sem entender o motivo.
    if relatorio.sem_chave != 0:
        raise SystemExit(
            f"ERRO: esperava sem_chave == 0, mas veio {relatorio.sem_chave}. "
            "Isso contradiz a checagem ao vivo ja feita (todos os itens "
            "deveriam ter ark_id extraivel) -- investigue antes de prosseguir."
        )
    if relatorio.total_saida != TOTAL_ESPERADO:
        raise SystemExit(
            f"ERRO: esperava total_saida == {TOTAL_ESPERADO}, mas veio "
            f"{relatorio.total_saida}. Nao force esse numero -- investigue "
            "a causa da divergencia antes de prosseguir."
        )

    SAIDA.write_text(
        json.dumps(deduplicados, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    print(f"\nSalvo (dedupado por ark_id): {SAIDA}")


if __name__ == "__main__":
    main()
