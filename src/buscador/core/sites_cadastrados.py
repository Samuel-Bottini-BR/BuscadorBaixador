# -*- coding: utf-8 -*-
"""
A lista de sites que o Samuel e o Kaique cadastraram no aplicativo (tela
"Sites"). Fica guardada num arquivo JSON local, saidas/sites_cadastrados.json
-- a pasta saidas/ já está no .gitignore, então essa lista nunca vai para o
GitHub (é do computador de vocês).

JSON é um formato de texto simples para guardar listas e "fichas"
(dicionários nome -> valor). Dá até para abrir no Bloco de Notas.

Na primeira vez (quando o arquivo ainda não existe), a lista começa com os
sites que o motor JÁ sabe mapear (têm adaptador próprio, ver cli.py):
Gallica, Grand Sud Médiéval e Internet Archive.

Cada site é um dicionário com estes campos:
- id: apelido curto, sem espaço nem acento (ex.: "gallica"). Também é o
  nome do perfil de navegador usado no login (ver logar.py).
- nome, endereco: o que aparece na tela.
- metodo: como o aplicativo acessa o site -- "api" (API oficial), "html"
  (leitura educada das páginas) ou "proibido" (robots.txt não deixa).
- adapter: nome do adaptador do motor que sabe mapear o site ("gallica",
  "phpbb", "internet_archive"), ou None se ainda não existe um.
- entrada: o que o usuário digita na tela Mapear -- "consulta" (texto de
  busca) ou "url" (endereço de uma página do site).
- exemplo: um exemplo do que digitar, para ajudar.
- url_login: página de login do site (vazio se não precisa).
- observacao: texto livre explicando regras e cuidados do site.
"""
import copy
import json
import re
import unicodedata
from pathlib import Path

from buscador.core import resumo_saidas
from buscador.core.escrita_atomica import salvar_json_atomico

NOME_ARQUIVO = "sites_cadastrados.json"

METODOS_TEXTO = {
    "api": "API oficial",
    "html": "Leitura das páginas (HTML)",
    "proibido": "Proibido pelo robots.txt",
}

# Os sites que o motor já conhece. "copy.deepcopy" é usado mais abaixo para
# a tela nunca mexer nesta lista original sem querer.
SITES_PADRAO = [
    {
        "id": "gallica",
        "nome": "Gallica (BnF)",
        "endereco": "https://gallica.bnf.fr/SRU",
        "metodo": "api",
        "adapter": "gallica",
        "entrada": "consulta",
        "exemplo": "Clavius",
        "url_login": "",
        "observacao": (
            "API SRU oficial da Biblioteca Nacional da França, sem chave e sem login. "
            "O site recusa pedidos rápidos: o aplicativo espera 6 s entre um pedido e outro. "
            "Mapear funciona; o download em lote está bloqueado pelo lado deles (ver tela Baixar)."
        ),
    },
    {
        "id": "grand_sud",
        "nome": "Grand Sud Médiéval",
        "endereco": "https://grand-sud-medieval.fr/forum/",
        "metodo": "html",
        "adapter": "phpbb",
        "entrada": "url",
        "exemplo": "https://grand-sud-medieval.fr/forum/viewtopic.php?f=14&t=9264",
        "url_login": "",
        "observacao": (
            "Fórum phpBB. O robots.txt permite a leitura; o aplicativo lê uma página por vez, "
            "com ~2 s de intervalo. Por enquanto mapeia UM tópico por vez (cole o endereço do tópico)."
        ),
    },
    {
        "id": "internet_archive",
        "nome": "Internet Archive",
        "endereco": "https://archive.org",
        "metodo": "api",
        "adapter": "internet_archive",
        "entrada": "consulta",
        "exemplo": 'subject:"theology" AND mediatype:texts',
        "url_login": "https://archive.org/account/login",
        "observacao": (
            "API oficial de busca (Advanced Search), sem chave. Listar não precisa de login; "
            "alguns livros são de \"empréstimo\" e pedem login para baixar (isso é da Fase 2)."
        ),
    },
]


def caminho_padrao() -> Path:
    """Onde o arquivo fica: saidas/sites_cadastrados.json (lido na hora)."""
    return resumo_saidas.pasta_saidas() / NOME_ARQUIVO


def carregar_sites(caminho: Path | None = None) -> list[dict]:
    """Lê a lista de sites. Se o arquivo ainda não existe, devolve os
    sites padrão (sem gravar nada -- só grava quando alguém salva).
    Se o arquivo existir mas estiver estragado (ex.: alguém editou à mão e
    apagou uma vírgula), levanta ValueError com uma mensagem clara, em vez
    de jogar fora o que estava lá."""
    caminho = Path(caminho) if caminho else caminho_padrao()
    if not caminho.exists():
        return copy.deepcopy(SITES_PADRAO)
    try:
        dados = json.loads(caminho.read_text(encoding="utf-8"))
    except json.JSONDecodeError as erro:
        raise ValueError(
            f"O arquivo {caminho} está com defeito (linha {erro.lineno}). "
            "Conserte ou apague o arquivo (apagando, a lista volta aos sites padrão)."
        ) from erro
    if not isinstance(dados, list):
        raise ValueError(f"O arquivo {caminho} não tem uma lista de sites.")
    return dados


def salvar_sites(sites: list[dict], caminho: Path | None = None) -> None:
    """Grava a lista inteira (de forma "atômica": nunca deixa o arquivo
    pela metade se o programa for fechado no meio -- ver escrita_atomica.py)."""
    caminho = Path(caminho) if caminho else caminho_padrao()
    salvar_json_atomico(sites, caminho)


def gerar_id(nome: str) -> str:
    """Transforma um nome em apelido seguro: "Biblioteca São José!" ->
    "biblioteca_sao_jose". Tira acentos, troca o resto por "_"."""
    sem_acento = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode("ascii")
    # "NFKD" separa a letra do acento (ã -> a + ~); o encode("ascii", "ignore")
    # joga fora o que não é letra simples (o acento solto)
    apelido = re.sub(r"[^a-z0-9]+", "_", sem_acento.lower()).strip("_")
    return apelido or "site"


def adicionar_site(sites: list[dict], novo: dict) -> list[dict]:
    """Devolve uma lista NOVA com o site "novo" no fim. Recusa (ValueError)
    nome vazio e nome/endereço repetidos -- assim não aparecem dois cartões
    iguais na tela. O id é criado a partir do nome se não vier pronto."""
    nome = (novo.get("nome") or "").strip()
    endereco = (novo.get("endereco") or "").strip()
    if not nome:
        raise ValueError("Falta o nome do site.")
    if not endereco:
        raise ValueError("Falta o endereço do site.")
    for site in sites:
        if site.get("nome", "").strip().lower() == nome.lower():
            raise ValueError(f"Já existe um site chamado \"{nome}\".")
        if _sem_barra(site.get("endereco", "")) == _sem_barra(endereco):
            raise ValueError(f"Este endereço já está cadastrado como \"{site.get('nome')}\".")

    ficha = {
        "id": "", "nome": nome, "endereco": endereco, "metodo": "html", "adapter": None,
        "entrada": "url", "exemplo": endereco, "url_login": "", "observacao": "",
    }
    ficha.update({k: v for k, v in novo.items() if v is not None})
    ficha["nome"], ficha["endereco"] = nome, endereco

    # garante um id único (se "biblioteca" já existe, usa "biblioteca_2")
    base = ficha["id"] or gerar_id(nome)
    ids_usados = {s.get("id") for s in sites}
    candidato, numero = base, 2
    while candidato in ids_usados:
        candidato = f"{base}_{numero}"
        numero += 1
    ficha["id"] = candidato
    return [*sites, ficha]


def remover_site(sites: list[dict], id_site: str) -> list[dict]:
    """Devolve uma lista NOVA sem o site de id "id_site"."""
    return [s for s in sites if s.get("id") != id_site]


def achar_site(sites: list[dict], id_site: str) -> dict | None:
    for site in sites:
        if site.get("id") == id_site:
            return site
    return None


def _sem_barra(endereco: str) -> str:
    """Para comparar endereços: ignora maiúsculas e a barra "/" do final."""
    return endereco.strip().lower().rstrip("/")
