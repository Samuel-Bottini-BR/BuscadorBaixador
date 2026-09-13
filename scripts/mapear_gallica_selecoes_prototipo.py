# -*- coding: utf-8 -*-
"""Mapeia as paginas de curadoria ("selecoes") da Gallica - PROTOTIPO EXPLORATORIO.

Nao faz parte do pacote buscador ainda (nao tem testes, nao segue o padrao de
adapters/base.py). Escrito em 12-13/09/2026 para responder ao pedido do Samuel
de mapear https://gallica.bnf.fr/selections/fr/html/livres por inteiro. Ver
HANDOFF.md ("O que aconteceu com o mapeamento da Gallica em 12-13/09") para o
resultado da rodada e a pergunta em aberto sobre os proximos passos.

Achado tecnico que importa pra quem for transformar isso num adapter de
verdade: a "categoria" que este script monta e a trilha de NAVEGACAO (a ordem
em que o rastreador visitou as paginas), nao uma classificacao confiavel - a
Gallica cruza links entre paginas de assuntos completamente diferentes (ex.:
"Manuscritos" aparece como link relacionado dentro da pagina de quadrinhos).
Um adapter de verdade provavelmente precisa: (a) tratar cada categoria de
primeiro nivel como uma arvore separada (nao compartilhar VISITADAS entre
elas), ou (b) nao tentar rotular por categoria e so guardar titulo+link+a
URL exata de onde veio.

Usa o ClienteEducado do proprio projeto (raspagem educada, User-Agent
honesto). A Gallica tem rate limit por cota acumulada no SITE INTEIRO, nao so
na API SRU - ja vimos 429 depois de so 4-5 paginas em rajada. O intervalo de
4s abaixo deu conta de uma rodada completa (3165 paginas, ~46 mil itens),
mas nao tente paralelizar isso.
"""
import sys
import json
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "src"))
from buscador.core.http_educado import ClienteEducado  # noqa: E402
from bs4 import BeautifulSoup  # noqa: E402

UA = ("BuscadorBaixador-InstitutoSaoBento/0.1 "
      "(uso nao comercial, preservacao de obras; contato: artesacra.quotidianus@gmail.com)")
BASE = "https://gallica.bnf.fr"

# Fica dentro de saidas/, que ja e ignorado pelo git inteiro (ver .gitignore) -
# tanto o cache de paginas quanto o resultado final nao vao para o repositorio.
CACHE_DIR = RAIZ / "saidas" / "_cache_gallica_selecoes"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
SAIDA_JSON = RAIZ / "saidas" / "gallica_mapa_livros.json"
SAIDA_XLSX = RAIZ / "saidas" / "gallica_mapa_livros_completo.xlsx"

cliente = ClienteEducado(UA, intervalo_segundos=4.0)

VISITADAS: set[str] = set()
NAO_SEGUIR = {"les-selections-de-gallica", "livres"}


def pegar_pagina(slug: str) -> str:
    """Busca com cache em disco - reaproveita o que ja foi baixado antes."""
    arq = CACHE_DIR / f"{slug}.html"
    if arq.exists():
        return arq.read_text(encoding="utf-8")
    url = f"{BASE}/selections/fr/html/{slug}"
    print(f"buscando: {url}")
    r = cliente.get(url)
    arq.write_text(r.text, encoding="utf-8")
    return r.text


def extrair(html: str):
    soup = BeautifulSoup(html, "html.parser")
    subcats = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.startswith("/selections/fr/html/"):
            slug = href.rsplit("/", 1)[-1]
            if slug not in NAO_SEGUIR:
                subcats.append(slug)
    itens = []
    for a in soup.find_all("a", href=True):
        if "ark:/12148" in a["href"]:
            titulo = a.get_text(strip=True)
            if titulo:
                itens.append((titulo, a["href"]))
    h1 = soup.find("h1")
    titulo_pagina = h1.get_text(strip=True) if h1 else ""
    return sorted(set(subcats)), itens, titulo_pagina


def mapear(slug: str, caminho: list[str], resultado: list):
    if slug in VISITADAS:
        return
    VISITADAS.add(slug)
    try:
        html = pegar_pagina(slug)
    except Exception as exc:  # 404/500/timeout: pula, nao derruba o mapeamento inteiro
        print(f"  [{slug}] ERRO ({exc}) - pulando")
        return
    subcats, itens, titulo_pagina = extrair(html)
    nome = titulo_pagina or slug

    if itens:
        for titulo, link in itens:
            resultado.append({
                "categoria": " > ".join(caminho + [nome]),
                "titulo": titulo,
                "link": link,
            })
        print(f"  [{slug}] {len(itens)} itens, {len(subcats)} subcategorias  "
              f"(total ate agora: {len(resultado)})")
    else:
        print(f"  [{slug}] 0 itens, {len(subcats)} subcategorias (provavel hub)")

    for sub in subcats:
        mapear(sub, caminho + [nome], resultado)
        SAIDA_JSON.write_text(json.dumps(resultado, ensure_ascii=False, indent=1), encoding="utf-8")


def exportar_xlsx(resultado: list) -> None:
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = "Gallica - Livros"
    ws.append(["Categoria", "Titulo", "Link"])
    for row in resultado:
        ws.append([row["categoria"], row["titulo"], row["link"]])
    ws.column_dimensions["A"].width = 60
    ws.column_dimensions["B"].width = 70
    ws.column_dimensions["C"].width = 50
    wb.save(SAIDA_XLSX)


if __name__ == "__main__":
    resultado: list = []
    mapear("livres", [], resultado)
    SAIDA_JSON.write_text(json.dumps(resultado, ensure_ascii=False, indent=1), encoding="utf-8")
    exportar_xlsx(resultado)
    print(f"\nTOTAL: {len(resultado)} itens em {len(VISITADAS)} paginas visitadas")
    print(f"JSON:  {SAIDA_JSON}")
    print(f"XLSX:  {SAIDA_XLSX}")
