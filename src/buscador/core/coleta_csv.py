# -*- coding: utf-8 -*-
"""
Escritor "incremental" (que vai salvando aos pouquinhos, em vez de tudo de
uma vez no final) de CSV (um formato simples de planilha, só texto separado
por vírgula) para a coleta bruta da Gallica (Etapa 1): grava cada página
assim que chega, em vez de guardar tudo na memória do computador até o fim
-- ver core/checkpoint.py para a peça irmã que lembra em que página parou.

O CSV também serve como saída "leve", fácil de importar em outros
programas (diferente do .xlsx colorido, que só existe depois, na Etapa 2).
"""
import csv  # biblioteca padrão do Python pra ler/escrever arquivos CSV
import os

from buscador.adapters.base import Item

# Aumentar o limite de tamanho de campo CSV: um campo "explicacao" real na
# coleta da Gallica tinha 171.499 caracteres, explodindo o padrão de 131.072.
# O uso de sys.maxsize causa OverflowError no Windows (inteiro C é 32-bit mesmo
# em sistema 64-bit), então usamos 10 milhões, que cobre o caso real com folga.
csv.field_size_limit(10_000_000)

# Nomes das colunas do CSV, na ordem em que vão ser escritas.
COLUNAS = [
    "titulo_original", "link", "autor", "ano", "explicacao", "fonte",
    "provedor", "dominio_publico", "url_pagina", "idioma_origem", "tipo_doc",
]


class EscritorCsvIncremental:
    """Abre o CSV em modo 'acrescentar': se o arquivo ja existe (retomando
    uma coleta interrompida), continua escrevendo no fim dele em vez de
    apagar o que ja tinha."""

    def __init__(self, caminho_csv):
        # __init__ roda quando criamos um EscritorCsvIncremental novo --
        # já deixa o arquivo aberto e pronto pra escrever.
        self.caminho_csv = caminho_csv
        arquivo_novo = not caminho_csv.exists() or caminho_csv.stat().st_size == 0
        # é um arquivo novo se ele simplesmente não existe ainda, OU se
        # existe mas está vazio (0 bytes de tamanho)
        caminho_csv.parent.mkdir(parents=True, exist_ok=True)
        self._arquivo = open(caminho_csv, "a", newline="", encoding="utf-8")
        # "a" = modo "append" (acrescentar no final), diferente de "w"
        # (que apagaria o conteúdo anterior). "newline=""" evita que o
        # Python insira quebra de linha extra por conta própria no Windows.
        self._escritor = csv.DictWriter(self._arquivo, fieldnames=COLUNAS)
        # DictWriter escreve linhas a partir de um dicionário (nome da
        # coluna -> valor), em vez de precisar montar a ordem na mão
        if arquivo_novo:
            self._escritor.writeheader()  # escreve a linha de cabeçalho (nomes das colunas) só se o arquivo for novo
            self._sincronizar()

    def escrever_pagina(self, itens):
        """Recebe uma lista de Item (normalmente, os itens de UMA página da
        Gallica) e escreve uma linha no CSV pra cada um."""
        for item in itens:
            self._escritor.writerow(_linha_de(item))
        self._sincronizar()

    def _sincronizar(self):
        # Garante que o que foi escrito realmente foi salvo no disco de
        # verdade, não só guardado temporariamente na memória do sistema
        # operacional -- importante pra coleta longa, que pode ser
        # interrompida a qualquer momento sem aviso.
        self._arquivo.flush()  # manda o Python entregar pro sistema operacional o que já escreveu
        os.fsync(self._arquivo.fileno())  # manda o sistema operacional gravar isso no disco físico de verdade

    def fechar(self):
        self._arquivo.close()

    def __enter__(self):
        # "__enter__" e "__exit__" juntos permitem usar essa classe com
        # "with EscritorCsvIncremental(...) as escritor:" -- o Python
        # garante que fechar() é chamado no final automaticamente, mesmo
        # se der algum erro no meio.
        return self

    def __exit__(self, tipo_erro, erro, traceback):
        self.fechar()


def carregar_itens_csv(caminho_csv):
    """Le o CSV inteiro e devolve uma lista de Item, descartando links
    repetidos (mantendo a primeira ocorrencia). Isso protege contra o unico
    jeito de duplicar uma linha nesse desenho: o programa ser interrompido
    bem entre 'gravei a pagina no CSV' e 'salvei o checkpoint dela' -- ao
    retomar, a pagina e buscada de novo e a linha aparece duas vezes."""
    vistos = set()  # guarda os links que já apareceram, pra detectar repetição
    itens = []
    with open(caminho_csv, newline="", encoding="utf-8") as arquivo:
        for linha in csv.DictReader(arquivo):
            # DictReader lê cada linha do CSV já como um dicionário
            # (nome da coluna -> valor), usando a primeira linha do
            # arquivo (o cabeçalho) pra saber os nomes das colunas
            if linha["link"] in vistos:
                continue  # já vimos esse link antes -- pula essa linha repetida
            vistos.add(linha["link"])
            itens.append(_item_de(linha))
    return itens


def _linha_de(item: Item) -> dict:
    """Transforma um objeto Item num dicionário simples, pronto pro
    DictWriter escrever como uma linha do CSV."""
    return {
        "titulo_original": item.titulo_original,
        "link": item.link,
        "autor": item.autor,
        "ano": item.ano,
        "explicacao": item.explicacao,
        "fonte": item.fonte,
        "provedor": item.provedor,
        "dominio_publico": item.dominio_publico,
        "url_pagina": item.url_pagina,
        "idioma_origem": item.extra.get("idioma_origem", ""),
        "tipo_doc": item.extra.get("tipo_doc", ""),
    }


def _item_de(linha: dict) -> Item:
    """O caminho inverso de _linha_de: transforma uma linha lida do CSV
    (um dicionário) de volta num objeto Item."""
    return Item(
        titulo_original=linha["titulo_original"],
        link=linha["link"],
        autor=linha["autor"],
        ano=linha["ano"],
        explicacao=linha["explicacao"],
        fonte=linha["fonte"],
        provedor=linha["provedor"],
        dominio_publico=linha["dominio_publico"],
        url_pagina=linha["url_pagina"],
        extra={"idioma_origem": linha["idioma_origem"], "tipo_doc": linha["tipo_doc"]},
    )
