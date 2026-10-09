# -*- coding: utf-8 -*-
"""
A checagem que a tela "Sites" faz antes de cadastrar um site novo -- é a
árvore de decisão da seção 7 do CLAUDE.md, feita de verdade:

1. Lê o robots.txt do site (o arquivo onde o dono do site diz o que robôs
   podem ou não ler). 1 pedido só, com o User-Agent honesto do projeto.
2. Pergunta ao robots.txt se o endereço informado pode ser lido. Para isso
   usamos o urllib.robotparser, que já vem com o Python.
3. Se pode, procura uma API oficial conhecida (OAI-PMH ou SRU) -- no
   máximo 2 pedidos, um para cada tipo, e só nos endereços que o próprio
   robots.txt permite.
4. Sugere o método: API (se achou) ou leitura educada do HTML; ou, se o
   robots.txt proíbe, NÃO deixa mapear e mostra os caminhos legítimos
   (pular o site ou pedir permissão aos responsáveis). Nunca burla.

Todos os pedidos passam pelo ClienteEducado (core/http_educado.py): um
de cada vez, com intervalo, se identificando honestamente. Os testes usam
um "cliente falso" no lugar dele, para não precisar de internet.
"""
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import requests

from buscador.core.http_educado import ClienteEducado

# O mesmo "cartão de visita" que os adaptadores usam (ver adapters/phpbb.py).
USER_AGENT = (
    "BuscadorBaixador-InstitutoSaoBento/0.1 "
    "(uso não comercial, preservação de obras; contato: artesacra.quotidianus@gmail.com)"
)
# Nome curto que o robots.txt pode citar numa regra "User-agent: ...".
NOME_ROBO = "BuscadorBaixador-InstitutoSaoBento"

# Endereços onde costuma morar uma API oficial, relativos à raiz do site,
# e um pedaço de texto que só aparece na resposta se for mesmo essa API.
# Testamos no máximo estes dois (um pedido cada).
SONDAS_API = [
    ("OAI-PMH", "/oai?verb=Identify", "<OAI-PMH"),
    ("SRU", "/SRU?operation=explain&version=1.2", "explainResponse"),
]

OPCOES_SE_PROIBIDO = [
    "Pular este site (não cadastrar).",
    "Pedir permissão por escrito aos responsáveis pelo site e, com a resposta, "
    "conversar com o Claude sobre o próximo passo.",
    "Procurar se o mesmo acervo está num site parceiro que permita a leitura "
    "(ex.: uma biblioteca nacional que hospede as mesmas obras).",
]


@dataclass
class ResultadoVerificacao:
    """O que a verificação descobriu -- a tela mostra estes campos."""
    endereco: str                    # endereço já "arrumado" (com https://)
    url_robots: str = ""
    robots_encontrado: bool = False  # existe um robots.txt?
    robots_permite: bool | None = None  # True/False; None = não deu para saber
    robots_texto: str = ""           # o conteúdo do robots.txt (para mostrar)
    api_encontrada: str | None = None  # "OAI-PMH", "SRU" ou None
    url_api: str = ""
    metodo_sugerido: str = ""        # "api", "html", "proibido" ou "indefinido"
    avisos: list[str] = field(default_factory=list)
    sitemaps: list[str] = field(default_factory=list)
    pedidos_feitos: int = 0

    @property
    def pode_mapear(self) -> bool:
        return self.metodo_sugerido in ("api", "html")


def normalizar_endereco(endereco: str) -> str:
    """Aceita "gallica.bnf.fr" e devolve "https://gallica.bnf.fr/".
    Levanta ValueError se não parecer um endereço de site."""
    endereco = (endereco or "").strip()
    if not endereco:
        raise ValueError("Digite o endereço do site.")
    if "://" not in endereco:
        endereco = "https://" + endereco
    partes = urlparse(endereco)
    if partes.scheme not in ("http", "https") or "." not in partes.netloc:
        raise ValueError(f"\"{endereco}\" não parece um endereço de site (ex.: https://exemplo.org).")
    if not partes.path:
        endereco += "/"
    return endereco


def verificar_site(endereco: str, cliente=None) -> ResultadoVerificacao:
    """Faz a checagem inteira (ver o topo do arquivo). "cliente" é quem faz
    os pedidos pela internet; se ninguém passar, cria um ClienteEducado."""
    endereco = normalizar_endereco(endereco)
    cliente = cliente or ClienteEducado(USER_AGENT, intervalo_segundos=2.0, timeout=15.0)
    partes = urlparse(endereco)
    raiz = f"{partes.scheme}://{partes.netloc}"
    resultado = ResultadoVerificacao(endereco=endereco, url_robots=raiz + "/robots.txt")

    # --- Passo 1: baixar o robots.txt -------------------------------------
    texto, status = _baixar(cliente, resultado.url_robots, resultado)
    leitor = RobotFileParser()
    if texto is not None:
        resultado.robots_encontrado = True
        resultado.robots_texto = texto
        leitor.parse(texto.splitlines())
    elif status in (404, 410):
        # Não ter robots.txt é normal: pela regra da internet, quer dizer
        # "sem restrições". Mesmo assim continuamos educados.
        resultado.avisos.append("O site não tem robots.txt -- pela regra, isso quer dizer que não há restrições.")
        leitor.parse([])
    elif status in (401, 403):
        # O site se recusa a mostrar até o robots.txt para nós. É um sinal
        # de que não querem robôs -- tratamos como proibido.
        resultado.robots_permite = False
        resultado.metodo_sugerido = "proibido"
        resultado.avisos.append(f"O site recusou mostrar o robots.txt (código {status}). Tratamos como proibido.")
        return resultado
    else:
        # Fora do ar, erro do servidor, sem internet... não dá para saber.
        resultado.metodo_sugerido = "indefinido"
        detalhe = f"código {status}" if status else "o site não respondeu"
        resultado.avisos.append(f"Não deu para ler o robots.txt ({detalhe}). Tente de novo mais tarde.")
        return resultado

    # --- Passo 2: o robots.txt deixa ler este endereço? --------------------
    resultado.robots_permite = leitor.can_fetch(NOME_ROBO, endereco)
    resultado.sitemaps = list(leitor.site_maps() or [])
    if _usa_curinga(texto or ""):
        # O robotparser do Python compara só o começo do caminho e não
        # entende "*" e "$" no meio das regras (ex.: "Disallow: /*?").
        # Em vez de fingir certeza, avisamos para uma pessoa conferir.
        resultado.avisos.append(
            "O robots.txt usa curingas (* ou $) nas regras, que a checagem automática não "
            "interpreta por completo. Leia as regras abaixo antes de mapear."
        )
    if not resultado.robots_permite:
        resultado.metodo_sugerido = "proibido"
        return resultado

    # --- Passo 3: procurar API oficial conhecida (no máximo 2 pedidos) -----
    for nome_api, caminho, marca in SONDAS_API:
        url = urljoin(raiz, caminho)
        if not leitor.can_fetch(NOME_ROBO, url):
            continue  # o próprio robots.txt não deixa olhar ali: nem tentamos
        corpo, _status = _baixar(cliente, url, resultado)
        if corpo and marca in corpo:
            resultado.api_encontrada = nome_api
            resultado.url_api = url
            break

    # --- Passo 4: sugerir o método ----------------------------------------
    resultado.metodo_sugerido = "api" if resultado.api_encontrada else "html"
    return resultado


def _baixar(cliente, url, resultado) -> tuple[str | None, int | None]:
    """Faz UM pedido. Devolve (texto, código). Se deu erro HTTP (404,
    500...), texto é None e o código diz qual foi; se nem respondeu
    (sem internet, tempo esgotado), os dois são None."""
    resultado.pedidos_feitos += 1
    try:
        resposta = cliente.get(url)
    except requests.HTTPError as erro:
        codigo = erro.response.status_code if erro.response is not None else None
        return None, codigo
    except requests.RequestException:
        return None, None
    return resposta.text, resposta.status_code


def _usa_curinga(texto_robots: str) -> bool:
    for linha in texto_robots.splitlines():
        linha = linha.split("#", 1)[0].strip()  # ignora comentários
        if linha.lower().startswith(("disallow:", "allow:")):
            regra = linha.split(":", 1)[1].strip()
            if "*" in regra or "$" in regra:
                return True
    return False


def explicar_metodo(resultado: ResultadoVerificacao) -> str:
    """Frase curta, para leigo, dizendo o que o aplicativo vai fazer."""
    if resultado.metodo_sugerido == "api":
        return (f"Usar a API oficial ({resultado.api_encontrada}). Costuma ser mais leve e estável "
                "que ler as páginas -- mas um adaptador para ela ainda precisa ser escrito.")
    if resultado.metodo_sugerido == "html":
        return "Leitura educada das páginas (HTML): 1 página por vez, ~2 s de intervalo, User-Agent honesto."
    if resultado.metodo_sugerido == "proibido":
        return "O robots.txt NÃO permite que robôs leiam este endereço. O aplicativo não burla essa regra."
    return "Não deu para decidir agora (o site não respondeu direito)."
