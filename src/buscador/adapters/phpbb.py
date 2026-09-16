# -*- coding: utf-8 -*-
"""
Adaptador (ver adapters/base.py pra entender o que é um adaptador) para
fóruns que usam o software "phpBB" no estilo visual clássico chamado
"prosilver" -- é um sistema de fórum bem comum, então esse código serve
pra qualquer fórum parecido, não só um específico.

Caso de teste usado pra construir isso: o fórum Grand Sud Médiéval
(https://grand-sud-medieval.fr/forum/). Esse site não publica um
robots.txt (arquivo que diz o que é permitido raspar), então seguimos a
regra padrão do projeto: raspagem educada (1 requisição de cada vez, com
intervalo entre elas, User-Agent -- o "nome" que o programa se apresenta --
honesto). Ver seção 7 do CLAUDE.md.
"""
from urllib.parse import urljoin  # junta um endereço relativo (ex. "pagina2.html") com a URL base, formando o endereço completo

from bs4 import BeautifulSoup, Comment, NavigableString
# BeautifulSoup: biblioteca que lê HTML (o código por trás de uma página
# web) e deixa a gente procurar pedaços dela facilmente (tipo "ache o
# título", "ache todos os links"). Comment e NavigableString são "tipos" de
# pedaço de texto dentro do HTML que o BeautifulSoup reconhece.

from buscador.adapters.base import Item, SiteAdapter
from buscador.core.http_educado import ClienteEducado

USER_AGENT = (
    "BuscadorBaixador-InstitutoSaoBento/0.1 "
    "(uso não comercial, preservação de obras; contato: artesacra.quotidianus@gmail.com)"
)
# Esse texto vai no cabeçalho "User-Agent" de cada requisição -- é como o
# programa se identifica pro site, de forma honesta (diz o que é e um
# contato), em vez de fingir ser um navegador comum.


class PhpbbAdapter(SiteAdapter):  # "herda" (usa como molde) o SiteAdapter -- ver adapters/base.py
    nome = "Grand Sud Médiéval"

    def __init__(self, url_inicial, cliente=None):
        # __init__ é a função especial que roda quando a gente CRIA um
        # PhpbbAdapter novo (ex.: PhpbbAdapter("https://...")). "self" é
        # como o próprio objeto se refere a si mesmo dentro da classe.
        self.url_inicial = url_inicial
        self.cliente = cliente or ClienteEducado(USER_AGENT)
        # "cliente or ClienteEducado(...)": se ninguém passou um cliente
        # pronto, cria um novo ClienteEducado (o "mensageiro" que faz as
        # requisições de internet respeitando o intervalo educado).

    def iter_itens(self):
        # Fatia atual só sabe ler uma página de tópico (viewtopic.php).
        # Listar todos os tópicos de um subfórum fica para quando precisarmos.
        yield from self._iter_topico(self.url_inicial)
        # "yield from" repassa, um por um, tudo que _iter_topico produzir --
        # sem isso teria que fazer um laço (loop) manual pra repassar cada item.

    def _iter_topico(self, url):
        # Funções que começam com "_" (underscore) são "privadas" por
        # convenção -- um jeito de avisar "isso é detalhe interno desse
        # adaptador, não é pra ser usado de fora dele".
        while url:  # continua enquanto tiver uma próxima página pra buscar
            resposta = self.cliente.get(url)
            _titulo, _secao, itens, proxima = self._parse_pagina(resposta.text, url)
            yield from itens
            url = proxima  # avança pra próxima página (ou None, que para o laço)

    def _parse_pagina(self, html, url_pagina):
        # "parse" = ler um texto (aqui, o HTML) e transformar em algo que o
        # programa consegue entender/navegar em pedaços.
        soup = BeautifulSoup(html, "html.parser")
        titulo = self._extrair_titulo_topico(soup)
        secao = self._extrair_secao(soup)
        itens = self._extrair_posts(soup, secao, titulo, url_pagina)
        proxima = self._proxima_pagina(soup, url_pagina)
        return titulo, secao, itens, proxima

    def _extrair_titulo_topico(self, soup):
        h2 = soup.find("h2")  # acha a primeira tag <h2> (título) da página
        if h2 is None:
            return ""
        link = h2.find("a")
        return (link or h2).get_text(strip=True)
        # pega o texto de dentro do link se tiver um, senão do próprio <h2>;
        # "strip=True" remove espaços em branco sobrando nas bordas

    def _extrair_secao(self, soup):
        # "breadcrumb" (literalmente "trilha de migalhas de pão") é o
        # caminho de navegação que aparece no topo de muitos sites, tipo
        # "Início > Categoria > Subcategoria".
        breadcrumb = soup.select_one("ul.linklist.navlinks li.icon-home")
        # ".select_one(...)" procura um elemento usando um "seletor CSS" --
        # a mesma linguagem usada pra estilizar páginas, aqui usada pra achar pedaço de HTML
        if breadcrumb is None:
            return ""
        links = breadcrumb.find_all("a")
        return links[-1].get_text(strip=True) if links else ""
        # links[-1] pega o ÚLTIMO link da lista (o "-1" em Python quer dizer "de trás pra frente")

    def _extrair_posts(self, soup, secao, titulo_topico, url_pagina):
        itens = []
        for post in soup.select('div.post[id^="p"]'):
            # esse seletor acha toda <div class="post"> cujo "id" comece com "p" (post1, post2, etc.)
            autor = self._extrair_autor(post)
            data_post = self._extrair_data(post)
            explicacao = self._extrair_corpo(post)
            for link in post.select("div.content a.postlink"):
                # dentro de cada mensagem (post), procura todo link marcado como "postlink"
                href = (link.get("href") or "").strip()
                if not href:
                    continue  # pula esse link e vai pro próximo, se ele nao tiver endereço nenhum
                itens.append(Item(
                    # Item é a "caixinha" de dados definida em adapters/base.py
                    titulo_original=titulo_topico,
                    link=href,
                    autor=autor,
                    explicacao=explicacao,
                    fonte=self.nome,
                    secao=secao,
                    url_pagina=url_pagina,
                    extra={"idioma_origem": "fr", "data_post": data_post},
                ))
        return itens

    def _extrair_autor(self, post):
        link = post.select_one("dl.postprofile dt a")
        return link.get_text(strip=True) if link else ""

    def _extrair_data(self, post):
        p_author = post.select_one("p.author")
        if p_author is None:
            return ""
        # ".contents" pega TODOS os pedaços dentro dessa tag (texto solto,
        # outras tags, comentários escondidos no HTML). O filtro abaixo
        # mantém só o texto "de verdade" (NavigableString), descartando
        # comentários escondidos no código (Comment).
        textos = [
            t for t in p_author.contents
            if isinstance(t, NavigableString) and not isinstance(t, Comment)
        ]
        return str(textos[-1]).strip() if textos else ""
        # pega o último pedaço de texto encontrado (normalmente é a data, depois do nome do autor)

    def _extrair_corpo(self, post):
        content = post.select_one("div.postbody div.content")
        if content is None:
            return ""
        # remove comentários HTML escondidos (tipo "<!-- assim -->") antes
        # de pegar o texto, pra eles não aparecerem misturados na explicação
        for comentario in content.find_all(string=lambda s: isinstance(s, Comment)):
            comentario.extract()  # ".extract()" remove esse pedaço da estrutura
        return content.get_text(separator=" ", strip=True)

    def _proxima_pagina(self, soup, url_atual):
        """A div.pagination do phpBB tem um <span> com a lista de paginas:
        a atual vem como <strong>, as outras como <a>. A proxima pagina e
        o primeiro <a> depois do <strong> atual (None se so tem 1 pagina)."""
        pag = soup.select_one("div.pagination")
        if pag is None:
            return None
        lista = pag.find("span")
        if lista is None:
            return None
        atual = lista.find("strong")
        if atual is None:
            return None
        proximo = atual.find_next_sibling("a")
        # "find_next_sibling" acha o próximo elemento "irmão" (mesmo nível,
        # logo depois) na estrutura do HTML -- aqui, o próximo número de página
        if proximo is None:
            return None
        href = proximo.get("href")
        return urljoin(url_atual, href) if href else None
        # transforma um endereço relativo (ex. "?start=25") num endereço completo, juntando com a URL atual
