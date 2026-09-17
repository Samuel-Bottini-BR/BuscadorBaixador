# -*- coding: utf-8 -*-
"""
Adaptador (ver adapters/base.py) para o Internet Archive (archive.org) --
uma biblioteca digital enorme, com API oficial de busca (a "Advanced
Search API"), documentada, sem chave. Confirmado antes de construir isso
(protocolo da seção 7 do CLAUDE.md): o robots.txt do archive.org só
bloqueia `/control/` e `/report/` (áreas administrativas), sem nenhuma
restrição contra automação/IA -- bem diferente do Scribd, que foi
descartado como fonte.

Este arquivo tem duas peças:
1. `MetodoApiInternetArchive`: o "método" de verdade (ver
   core/metodo_coleta.py), que sabe conversar com a API de busca.
2. `InternetArchiveAdapter`: um embrulho fino que pluga esse método numa
   cascata de 1 item só (core/metodo_coleta.coletar_em_cascata), só pra
   esse adaptador poder ser usado com o cli.py existente do mesmo jeito
   que PhpbbAdapter/GallicaAdapter -- é a aplicação real da cascata,
   provando que o desenho funciona ponta a ponta (não é só teoria).

Uma parte do acervo do Internet Archive é "biblioteca de empréstimo"
(Controlled Digital Lending) -- só dá pra abrir de verdade com conta
gratuita e um empréstimo por tempo limitado, do jeito que uma biblioteca
física funciona. Isso aparece marcado no metadado como
"access-restricted-item". Esta Fase 1 (mapear pra planilha) NÃO baixa
nada, só lista -- por isso não precisamos resolver login aqui; cada item
já sai marcado com essa informação (extra["access_restricted"]), pra
quem for baixar depois (Fase 2) saber o que vai precisar de empréstimo.
"""
import json  # a resposta da API vem em JSON -- essa biblioteca padrao do Python le/escreve nesse formato
from urllib.parse import urlencode  # transforma um dicionario de parametros em texto de URL (ex.: {"a": "b"} vira "a=b")

from buscador.adapters.base import Item, SiteAdapter
from buscador.core.http_educado import ClienteEducado
from buscador.core.metodo_coleta import MetodoColeta, coletar_em_cascata

USER_AGENT = (
    "BuscadorBaixador-InstitutoSaoBento/0.1 "
    "(uso não comercial, preservação de obras; contato: artesacra.quotidianus@gmail.com)"
)
API_BUSCA = "https://archive.org/advancedsearch.php"
MAXIMO_POR_PAGINA = 100  # sem limite oficial estrito documentado; 100 e' um primeiro palpite conservador (igual espirito do limite da Gallica)

# Campos pedidos pra API devolver por item -- "fl[]" na URL (field list).
CAMPOS = [
    "identifier", "title", "creator", "date", "language",
    "licenseurl", "access-restricted-item", "publisher",
]

# Mapa de código de idioma pro padrao de 2 letras que o resto do programa
# usa -- o Internet Archive as vezes devolve o nome por extenso em ingles.
_MAPA_IDIOMA = {
    "english": "en", "eng": "en", "en": "en",
    "french": "fr", "fre": "fr", "fra": "fr", "fr": "fr",
    "latin": "la", "lat": "la", "la": "la",
    "portuguese": "pt", "por": "pt", "pt": "pt",
    "spanish": "es", "spa": "es", "es": "es",
    "german": "de", "ger": "de", "deu": "de", "de": "de",
    "greek": "el", "gre": "el", "grc": "el", "el": "el",
    "italian": "it", "ita": "it", "it": "it",
}


class MetodoApiInternetArchive(MetodoColeta):
    """O metodo de coleta de verdade: fala com a Advanced Search API do
    Internet Archive. Nao precisa de chave nenhuma -- disponivel() fica no
    padrao (sempre True, herdado de MetodoColeta)."""

    nome = "Internet Archive (API de busca)"

    def __init__(self, consulta, cliente=None, max_resultados=MAXIMO_POR_PAGINA,
                 tamanho_pagina=MAXIMO_POR_PAGINA):
        # __init__ roda quando criamos um MetodoApiInternetArchive novo.
        self.consulta = consulta  # o texto de busca (ex.: 'subject:"theology" AND mediatype:texts')
        self.cliente = cliente or ClienteEducado(USER_AGENT, intervalo_segundos=2.0)
        self.max_resultados = max_resultados  # teto de quantos itens coletar no total
        self.tamanho_pagina = min(tamanho_pagina, MAXIMO_POR_PAGINA)  # nunca deixa passar do teto, mesmo se alguem pedir mais

    def iter_itens(self):
        # Gerador (ver adapters/base.py): vai pedindo pagina por pagina pra
        # API ate atingir max_resultados OU a API dizer que acabou (pagina vazia).
        pagina = 1
        coletados = 0
        while coletados < self.max_resultados:
            docs = self._buscar_pagina(pagina)
            if not docs:
                return  # nao ha mais resultados
            for doc in docs:
                yield self._item_de_doc(doc)
                coletados += 1
                if coletados >= self.max_resultados:
                    return
            pagina += 1

    def _buscar_pagina(self, pagina):
        # Monta a URL da Advanced Search API e faz a chamada de verdade.
        params = {
            "q": self.consulta,             # a busca em si
            "fl[]": CAMPOS,                 # quais campos queremos que cada item devolva
            "rows": self.tamanho_pagina,    # quantos itens por pagina
            "page": pagina,                 # qual pagina pedir
            "output": "json",               # formato da resposta
        }
        url = f"{API_BUSCA}?{urlencode(params, doseq=True)}"
        # "doseq=True" faz o urlencode repetir "fl[]=campo1&fl[]=campo2..."
        # pra cada item da lista CAMPOS, em vez de tentar juntar tudo numa
        # string so (e' o formato que essa API espera pra pedir varios campos)
        resposta = self.cliente.get(url)
        dados = json.loads(resposta.text)  # transforma o texto JSON devolvido numa estrutura navegavel (dicionarios/listas)
        return dados["response"]["docs"]  # "docs" e' a lista de itens encontrados nessa pagina

    def _item_de_doc(self, doc):
        # Extrai cada campo de um "doc" (um item devolvido pela API) e
        # monta um Item (a "caixinha" padrao de achado, definida em adapters/base.py).
        identifier = doc.get("identifier", "")  # o codigo unico do item no Internet Archive
        link = f"https://archive.org/details/{identifier}"  # pagina publica do item, monta a partir do identifier
        restrito = doc.get("access-restricted-item") in (True, "true", "True")
        # a API pode devolver esse campo como True (booleano de verdade) ou
        # como texto "true"/"True", dependendo do caso -- checamos os tres
        ano = str(doc.get("date", ""))[:4]  # a API devolve data completa tipo "2025-01-01T00:00:00Z"; pegamos so o ano
        extra = {"access_restricted": restrito}
        idioma = _idioma_iso(doc.get("language"))
        if idioma:
            # so preenchemos a chave quando sabemos o idioma de verdade --
            # deixar ela de fora (em vez de guardar string vazia) e' o que
            # faz enriquecer_item cair no "auto" (deixa o tradutor tentar
            # adivinhar), ver core/enriquecimento.py
            extra["idioma_origem"] = idioma
        return Item(
            titulo_original=doc.get("title", ""),
            link=link,
            autor=doc.get("creator", ""),
            ano=ano,
            fonte=doc.get("publisher", "") or "Internet Archive",
            provedor="Internet Archive",
            dominio_publico=_dominio_publico(doc.get("licenseurl")),
            url_pagina=link,
            extra=extra,
        )


def _dominio_publico(licenseurl):
    """Ao contrario da Gallica (que confirma dominio publico explicitamente
    no campo 'rights' de cada item), o Internet Archive nem sempre declara
    isso -- por honestidade, so marcamos "Sim" quando o licenseurl aponta
    claramente pra dominio publico; sem essa informacao, deixamos em
    branco (desconhecido) em vez de supor."""
    if licenseurl and "publicdomain" in licenseurl.lower():
        return "Sim"
    return ""


def _idioma_iso(idioma):
    # Traduz o valor de idioma que a API devolveu (pode vir vazio, por
    # extenso em ingles, ou ja abreviado) pro codigo de 2 letras que o
    # resto do programa usa, usando o _MAPA_IDIOMA definido la em cima.
    if not idioma:
        return ""
    return _MAPA_IDIOMA.get(str(idioma).strip().lower(), "")


class InternetArchiveAdapter(SiteAdapter):  # "herda" (usa como molde) o SiteAdapter -- ver adapters/base.py
    """Embrulho fino que pluga MetodoApiInternetArchive numa cascata de 1
    metodo so, pra este adaptador funcionar com o cli.py existente
    (iter_itens simples) e, ao mesmo tempo, ja nascer usando a cascata de
    verdade (core/metodo_coleta.py) -- a aplicacao real do passo 11 do
    plano de coleta em cascata."""

    nome = "Internet Archive"

    def __init__(self, consulta, cliente=None):
        # __init__ roda quando criamos um InternetArchiveAdapter novo
        # (ex.: pelo cli.py, quando alguem roda o comando pra esse site).
        self.consulta = consulta
        self.cliente = cliente

    def iter_itens(self):
        # Monta a lista de metodos (aqui, so 1: a API) e entrega pra
        # cascata (core/metodo_coleta.py) tentar em ordem. Hoje so tem um
        # metodo, mas se um dia esse site precisar de navegador automatizado
        # tambem (ver core/navegador.py), bastaria adicionar ele nessa
        # lista, na ordem certa -- o resto do adaptador nao muda nada.
        metodo = MetodoApiInternetArchive(self.consulta, cliente=self.cliente)
        yield from coletar_em_cascata([metodo], self.nome)
