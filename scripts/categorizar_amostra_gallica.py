# -*- coding: utf-8 -*-
"""Recategoriza uma amostra do mapa da Gallica em baldes tematicos sensatos
(nao a trilha de navegacao quebrada de gallica_mapa_livros.json - ver
mapear_gallica_selecoes_prototipo.py), traduz os titulos, e grava uma amostra
pronta para gerar as planilhas de teste (ver gerar_3_versoes_planilha.py).

PROTOTIPO / RASCUNHO - os baldes (BALDES abaixo) sao um primeiro palpite por
palavra-chave, nao a versao final. Na rodada de 13-15/09/2026 so 4 dos 8
baldes pegaram itens de verdade (Quadrinhos, Manuscritos Medievais, Religiao
e Teologia, Referencia) - os outros 4 (Ciencias, Paris, Literatura Classica,
Traducoes) ficaram vazios porque a ordem dos baldes prioriza os primeiros
match numa trilha contaminada (ver HANDOFF.md, secao sobre o mapeamento da
Gallica) - um item pode ter varias palavras-chave na trilha, e so a primeira
que bate manda. Precisa de ajuste antes de rodar nos 46 mil itens de verdade.
"""
import json
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "src"))
from buscador.core.traducao import traduzir  # noqa: E402

JSON_ORIGEM = RAIZ / "saidas" / "gallica_mapa_livros.json"
SAIDA = RAIZ / "saidas" / "amostra_categorizada_traduzida.json"


def sem_acento(s):
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


BALDES = [
    ("Religiao e Teologia", ["theolog", "religi", "biblique", "bible", "liturg",
                              "patristique", "saints", "eglise", "psautier",
                              "evangil", "missel", "breviaire"]),
    ("Manuscritos Medievais", ["manuscrit", "carolingien", "roman-de-la-rose",
                                 "chretien-de-troyes", "christine-de-pizan",
                                 "roman-de-renart", "moyen age", "merovingien"]),
    ("Referencia e Enciclopedias", ["ouvrages-de-reference", "encyclopedie",
                                       "dictionnaire", "abecedaire"]),
    ("Quadrinhos", ["bande dessinee", "bande-dessinee"]),
    ("Ciencias e Natureza", ["science", "botanique", "zoologie", "geologie",
                                "medecine", "sante", "jardin", "horticulture"]),
    ("Paris e Historia Local", ["paris", "hopital", "bastille", "opera", "notre-dame"]),
    ("Literatura Classica Francesa", ["classique", "litterature", "roman ",
                                         "poesie", "auteur"]),
    ("Traducoes e Literaturas Estrangeiras", ["traduction", "traductions"]),
]


def categorizar(categoria_bruta: str) -> str:
    alvo = sem_acento(categoria_bruta.lower())
    for nome, palavras in BALDES:
        for p in palavras:
            if sem_acento(p.lower()) in alvo:
                return nome
    return "Outros"


def main(itens_por_balde: int = 6):
    dados = json.loads(JSON_ORIGEM.read_text(encoding="utf-8"))
    por_balde = defaultdict(list)
    for item in dados:
        por_balde[categorizar(item["categoria"])].append(item)

    print("=== distribuicao real (46222 itens) ===")
    for nome, itens in sorted(por_balde.items(), key=lambda kv: -len(kv[1])):
        print(f"{len(itens):6d}  {nome}")

    amostra = []
    for nome, itens in por_balde.items():
        if nome == "Outros":
            continue
        for item in itens[:itens_por_balde]:
            amostra.append({**item, "categoria_padronizada": nome})

    print(f"\nAmostra: {len(amostra)} itens, traduzindo...")
    for item in amostra:
        item["titulo_traduzido"] = traduzir(item["titulo"], idioma_origem="fr", idioma_destino="pt")
        print(f"  {item['titulo'][:50]!r} -> {item['titulo_traduzido'][:50]!r}")

    SAIDA.write_text(json.dumps(amostra, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nSalvo: {SAIDA}")


if __name__ == "__main__":
    main()
