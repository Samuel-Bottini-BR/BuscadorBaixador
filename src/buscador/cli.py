# -*- coding: utf-8 -*-
"""
Este é o "ponto de entrada" (entry point -- o lugar por onde o programa
começa a rodar) de linha de comando (CLI -- Command Line Interface, o jeito
de usar um programa digitando comando no terminal em vez de clicar em
botão). Você roda algo tipo:

    python -m buscador.cli "https://algum-site.com/..."

E este arquivo, por dentro: escolhe qual adaptador usar pra aquele site,
verifica cada link achado, traduz o título, e gera a planilha final da
Fase 1 do projeto.
"""
import argparse  # biblioteca padrão do Python pra ler argumentos digitados no terminal (tipo --adapter, --saida)
import datetime
import re  # "regex"/expressão regular -- linguagem pra descrever padrões de texto (usado aqui pra "limpar" um nome de arquivo)
from pathlib import Path  # jeito moderno do Python de lidar com caminhos de arquivo/pasta
from urllib.parse import parse_qs, urlparse  # ferramentas pra desmontar uma URL em pedaços (domínio, parâmetros, etc.)

from buscador.adapters.gallica import GallicaAdapter
from buscador.adapters.phpbb import PhpbbAdapter
from buscador.core.acao_humana import AcaoHumanaNecessaria, formatar_aviso
from buscador.core.enriquecimento import enriquecer_item
from buscador.core.planilha import gerar_planilha

# Dicionário (dict -- uma "tabela" nome->valor) que liga o domínio de um
# site ao nome do adaptador certo pra ele. Pra ensinar o programa sobre um
# site novo, seria aqui que apareceria uma linha nova.
ADAPTERS_POR_DOMINIO = {
    "grand-sud-medieval.fr": "phpbb",
    "gallica.bnf.fr": "gallica",
}

# Pasta onde as planilhas geradas são salvas. "Path(__file__)" é o caminho
# deste próprio arquivo; ".resolve()" transforma num caminho completo (sem
# "..", por exemplo); cada ".parent" sobe uma pasta, até chegar na raiz do
# projeto, onde então entra na pasta "saidas".
SAIDAS = Path(__file__).resolve().parent.parent.parent / "saidas"


def escolher_adapter(url, forcado=None):
    """Decide qual adaptador usar pra uma URL, olhando o domínio dela.
    Se "forcado" foi passado (via --adapter no terminal), usa esse direto,
    sem nem olhar a URL."""
    if forcado:
        return forcado
    dominio = urlparse(url).netloc.lower()  # "netloc" é a parte da URL com o domínio (ex.: "gallica.bnf.fr")
    for sufixo, nome in ADAPTERS_POR_DOMINIO.items():
        if dominio == sufixo or dominio.endswith("." + sufixo):
            # o "endswith" cobre subdomínios, tipo "www.gallica.bnf.fr" também bater com "gallica.bnf.fr"
            return nome
    raise ValueError(f"Não sei qual adaptador usar para '{url}'. Use --adapter.")


def construir_adapter(nome_adapter, url_ou_consulta):
    """Cria de fato um objeto adaptador (PhpbbAdapter ou GallicaAdapter),
    já configurado com a URL ou consulta que a gente quer processar."""
    if nome_adapter == "phpbb":
        return PhpbbAdapter(url_ou_consulta)
    if nome_adapter == "gallica":
        return GallicaAdapter(_extrair_consulta_gallica(url_ou_consulta))
    raise ValueError(f"Adaptador desconhecido: {nome_adapter}")


def _extrair_consulta_gallica(valor):
    """Aceita tanto uma consulta CQL direta ('gallica all "Clavius"') quanto
    uma URL do SRU copiada do navegador (usa o parametro 'query' dela)."""
    if valor.startswith("http://") or valor.startswith("https://"):
        parametros = parse_qs(urlparse(valor).query)
        # parse_qs devolve um dicionário onde cada parâmetro vira uma LISTA
        # de valores (uma URL pode repetir o mesmo parâmetro mais de uma
        # vez) -- por isso o "[0]" abaixo, pra pegar só o primeiro valor.
        if parametros.get("query"):
            return parametros["query"][0]
    return valor


def _slug_do_dominio(url_ou_consulta):
    """Nome de arquivo a partir do dominio da URL; se a entrada nao for uma
    URL (ex.: uma consulta CQL da Gallica), usa o proprio texto da consulta."""
    # "slug" é o termo comum pra um texto convertido pra um formato seguro
    # de usar em nome de arquivo/URL (só letras minúsculas, número e hífen).
    dominio = urlparse(url_ou_consulta).netloc.lower().replace("www.", "")
    base = dominio or url_ou_consulta[:40]  # se não tiver domínio (não é uma URL), usa os 40 primeiros caracteres do texto
    slug = re.sub(r"[^a-z0-9]+", "-", base.lower()).strip("-")
    # a linha acima troca (usando regex) qualquer sequência de caracteres
    # que NÃO seja letra minúscula ou número por um hífen "-", e depois tira
    # hífen sobrando nas pontas
    return slug or "saida"


def main(argv=None):
    """Função principal -- é o que roda de verdade quando você chama
    "python -m buscador.cli ...". "argv=None" quer dizer: se ninguém passar
    uma lista de argumentos na mão (usado nos testes automatizados), lê os
    argumentos digitados de verdade no terminal."""
    parser = argparse.ArgumentParser(description="Mapeia um site para uma planilha (Fase 1).")
    parser.add_argument("url", help="URL de entrada (topico ou busca do site)")
    parser.add_argument("--adapter", choices=["phpbb", "gallica"], help="Força um adaptador específico")
    parser.add_argument("--saida", help="Caminho do .xlsx de saída (padrão: saidas/<site>_<data>.xlsx)")
    args = parser.parse_args(argv)  # lê e organiza o que foi digitado no terminal

    try:
        nome_adapter = escolher_adapter(args.url, args.adapter)
        adapter = construir_adapter(nome_adapter, args.url)
        # a linha abaixo é uma "list comprehension" -- um jeito compacto do
        # Python de escrever "pra cada item que o adapter encontrar, já vai
        # enriquecendo (verificando link + traduzindo) e guardando numa lista"
        itens = [enriquecer_item(item) for item in adapter.iter_itens()]
    except ValueError as erro:
        # Erro "normal", esperado (ex.: site não cadastrado) -- mostra
        # mensagem amigável e para, sem mostrar o erro técnico feio (stack
        # trace) pra quem estiver usando o programa.
        print(f"Não deu para continuar: {erro}")
        return 1
    except AcaoHumanaNecessaria as erro:
        # Sinal especial (ver core/acao_humana.py): o programa precisa que
        # o Samuel faça algo (conseguir uma chave, logar, resolver um
        # CAPTCHA) antes de continuar. Mostra a instrução e para de forma
        # limpa -- rodar o comando de novo depois resolve.
        print(formatar_aviso(erro))
        return 1

    if args.saida:
        caminho_saida = Path(args.saida)
    else:
        data = datetime.date.today().isoformat()  # data de hoje em texto, formato AAAA-MM-DD
        caminho_saida = SAIDAS / f"{_slug_do_dominio(args.url)}_{data}.xlsx"

    caminho_final = gerar_planilha(itens, caminho_saida)
    print(f"{len(itens)} itens encontrados. Planilha salva em: {caminho_final}")
    return 0  # 0 quer dizer "tudo certo" pro sistema operacional (1 quer dizer "deu erro")


if __name__ == "__main__":
    # Esse "if" só é verdadeiro quando o arquivo é executado diretamente
    # (não quando é só importado por outro arquivo) -- é o jeito padrão do
    # Python de dizer "isso aqui é o ponto de partida do programa".
    raise SystemExit(main())
