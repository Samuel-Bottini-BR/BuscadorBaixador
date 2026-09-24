# -*- coding: utf-8 -*-
"""Recategoriza o mapa completo da Gallica (46.222 itens) em baldes
tematicos sensatos (nao a trilha de navegacao quebrada de
gallica_mapa_livros.json - ver mapear_gallica_selecoes_prototipo.py).

FINALIZADO em 17/09/2026 apos duas rodadas de ajuste fino, ver HANDOFF.md
("O que aconteceu com o mapeamento da Gallica"). Achado central: a coluna
"categoria" nao e uma trilha de navegacao do ITEM, e sim a lista de paginas
que o rastreador visitou ate chegar nele - a maior parte dessa lista e um
prefixo GIGANTE e repetido (ex.: quase todo item, de teologia medieval a
arquivo da Bastilha, carrega "Livros > Bande dessinee > ... > Manuscrits >
..." antes do pedaco que de fato descreve o item). So o ULTIMO segmento da
trilha (a pagina mais especifica que o rastreador realmente visitou para
aquele item) e um sinal confiavel; qualquer segmento anterior pode ser
"ruido" compartilhado por milhares de itens sem relacao nenhuma entre si.
Por isso categorizar() abaixo usa so o ultimo segmento (mais o titulo, como
reforco) - nunca a trilha inteira.

Este script SO categoriza (rapido, sem rede) - nao traduz mais. Para
traduzir os titulos em lote (lento, sujeito a rate limit de Google/MyMemory)
ver scripts/traduzir_titulos_lote_gallica.py, que le a saida deste script.

Atualizado em 23/09/2026: passou a ler o arquivo JA DEDUPLICADO por ark_id
(saidas/gallica_mapa_livros_dedupado.json, 26.544 obras unicas - gerado por
scripts/deduplicar_gallica_por_ark.py), nao mais o bruto com duplicata
(gallica_mapa_livros.json, 46.222 itens, onde a mesma obra pode aparecer
repetida sob mais de uma trilha de navegacao). O algoritmo de categorizar()
abaixo nao mudou - so a fonte dos dados. A saida vai para
gallica_categorizado_dedupado.json, sem sobrescrever a rodada antiga
(gallica_categorizado_completo.json, sobre o bruto), que fica de referencia.
"""
import json
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "src"))

JSON_ORIGEM = RAIZ / "saidas" / "gallica_mapa_livros_dedupado.json"
SAIDA = RAIZ / "saidas" / "gallica_categorizado_dedupado.json"


# Alem de tirar acento, troca ligaduras (oe/ae) e todo tipo de apostrofo
# ("’", "'", "`"...) por nada - o site mistura apostrofo reto e curvo no
# mesmo texto (ex.: "L'Epatant" vs "L'As"), e sem isso a palavra-chave bate
# num jeito e nao bate no outro.
_TRADUZ_CHAR = str.maketrans({
    "œ": "oe", "Œ": "OE", "æ": "ae", "Æ": "AE",
    "’": "", "‘": "", "'": "", "`": "", "´": "",
})


def sem_acento(s):
    s = s.translate(_TRADUZ_CHAR)
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


# Ordem importa: baldes mais especificos primeiro, "Literatura Classica
# Francesa" (a palavra-chave mais generica, "classique"/"litterature") por
# ultimo, para nao roubar item de balde mais estreito.
BALDES = [
    ("Manuscritos Medievais", [
        "manuscrit", "carolingien", "merovingien", "librairie de charles v",
        "librairie royale", "roman de la rose", "chretien de troyes",
        "christine de pizan", "roman de renart", "enluminure", "parchemin",
        "codex", "incunable",
    ]),
    ("Religiao e Teologia", [
        "theolog", "biblique", "bible", "evangil", "psautier", "liturg",
        "patristique", "eglise", "hagiograph", "missel", "breviaire",
        "religi", "clerge", "chretiente", "monastique", "abbaye", "couvent",
        "pape ", "cardinal", "concile",
    ]),
    ("Traducoes e Literaturas Estrangeiras", [
        "traduction", "litterature polonaise", "litteratures europeennes",
        "litterature etrangere", "auteurs britanniques", "auteurs etrangers",
        "litterature anglaise", "litterature allemande", "litterature russe",
        "litterature italienne", "litterature espagnole",
    ]),
    ("Referencia e Enciclopedias", [
        "encyclopedie", "dictionnaire", "abecedaire", "bibliographie",
        "repertoire", "nomenclature", "lexique", "glossaire", "annuaire",
        "catalogue", "inventaire", "usuel", "ouvrages-de-reference",
        "ouvrages de reference",
    ]),
    ("Quadrinhos", [
        "bande dessinee", "bandes dessinees", "dessin de presse",
        "dessins de georges wolinski", "presse satirique", "chat noir",
        "buster brown", "little nemo", "little sammy sneeze", "felix le chat",
        "coq hardi", "lisette", "fillette", "jumbo", "l'epatant", "l'as ",
        "pele-mele", "guignol", "arabelle", "professeur nimbus", "wrill",
        "becassine", "zig et puce", "caricature", "saint-ogan", "wolinski",
        "verbeck", "mccay", "outcault", "thomen", "caran d'ache", "steinlen",
        "rabier", "bandes dessinees de", "bibi fricotin", "pif le chien",
        "bob et bobette", "pieds nickeles", "belles images", "pitche",
        "pierrot", "l'aventureux", "petit francais illustre",
        "coeurs vaillants", "baionnette", "christophe", "famille fenouillard",
        "imagerie pellerin", "epinal", "presse enfantine", "ames vaillantes",
        "jeunesse illustree", "jeunesse magazine", "jeudi de la jeunesse",
        "ecolier illustre", "semaine des enfants", "junior", "american illustre",
        "disques illustres pour enfants",
    ]),
    ("Ciencias e Natureza", [
        "science", "botanique", "zoologie", "geologie", "medecine", "sante",
        "jardin", "horticulture", "numismatique", "monnaies", "jetons",
        "archeologie", "aviation", "avions", "transport aerien",
        "mathematique", "physique", "chimie", "astronomie", "cartes",
        "carte de cassini", "geographie", "naturelle", "biologie", "faune",
        "flore", "meteorologie", "technique", "cabinet des medailles",
        "globes terrestres", "globes en 3d", "objets numerises",
        "presse scientifique", "presse medicale", "pasteur",
    ]),
    ("Paris e Historia Local", [
        "paris", "notre-dame", "bastille", "opera", "hopital", "commune de paris",
        "resistance", "tranchees", "guerre mondiale", "armees francaises",
        "guadeloupe", "provence", "bastia", "gironde", "rhone", "auvergne",
        "departement", "region", "ile-de-france", "montmartre",
        "moreau de saint-mery",
        "presse algerienne", "presse marocaine", "presse malgache",
        "presse coloniale", "presse ottomane", "presse de l'ex-indochine",
        "presse du nord", "presse du gard", "presse de l'aude",
        "presse des alpes-maritimes", "presse de la seine-et-marne",
        "presse du finistere", "presse du pas-de-calais", "presse locale",
        "presse politique", "communards",
    ]),
    ("Literatura Classica Francesa", [
        "classique", "litterature", "romancier", "poesie", "auteur",
        "feuilleton", "roman ", "romans ", "conte", "ecrivain",
        "academie francaise", "moliere", "balzac", "zola", "dumas", "camus",
        "aurevilly", "poete", "nouvelles ", "femmes de lettres",
        "editeurs litteraires", "colette", "giono", "flaubert", "rabelais",
        "george sand", "gustave aimard", "recherche du temps perdu",
        "henri bosco", "jean de meun", "presse litteraire",
    ]),
]


def _bate(alvo_norm, palavras):
    return any(sem_acento(p.lower()) in alvo_norm for p in palavras)


def categorizar(item) -> str:
    """So confia no ULTIMO segmento da trilha (o mais especifico que o
    rastreador realmente visitou para ESTE item) - qualquer segmento antes
    dele pode ser ruido compartilhado por milhares de itens sem relacao
    (ver docstring do modulo). O titulo entra so como reforco, para os
    poucos itens cujo ultimo segmento nao bate em nenhum balde."""
    trilha = item["categoria"]
    titulo = item.get("titulo", "")
    partes = [p.strip() for p in trilha.split(">") if p.strip()]
    ultimo_norm = sem_acento((partes[-1] if partes else "").lower())
    titulo_norm = sem_acento(titulo.lower())

    for nome, palavras in BALDES:
        if _bate(ultimo_norm, palavras):
            return nome
    for nome, palavras in BALDES:
        if _bate(titulo_norm, palavras):
            return nome
    return "Outros"


def main():
    dados = json.loads(JSON_ORIGEM.read_text(encoding="utf-8"))
    resultado = []
    contagem = defaultdict(int)
    for item in dados:
        nome = categorizar(item)
        contagem[nome] += 1
        resultado.append({**item, "categoria_padronizada": nome})

    print(f"=== distribuicao final ({len(dados)} itens) ===")
    for nome, n in sorted(contagem.items(), key=lambda kv: -kv[1]):
        pct = 100 * n / len(dados)
        print(f"{n:6d}  ({pct:5.1f}%)  {nome}")

    # Verificacao de sanidade: a soma das categorias tem que bater exatamente
    # com o total de itens de entrada -- categorizar() sempre devolve
    # exatamente um balde por item, entao isso e mais uma garantia contra
    # erro de processamento (item perdido/duplicado) do que algo que possa
    # falhar de verdade, mas falha alto e claro se algo mudar nisso.
    soma_categorias = sum(contagem.values())
    if soma_categorias != len(dados):
        raise SystemExit(
            f"ERRO: soma das categorias ({soma_categorias}) nao bate com o "
            f"total de itens de entrada ({len(dados)}) -- investigue antes "
            "de prosseguir."
        )

    SAIDA.write_text(json.dumps(resultado, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nSalvo (categorizado, ainda sem traducao): {SAIDA}")


if __name__ == "__main__":
    main()
