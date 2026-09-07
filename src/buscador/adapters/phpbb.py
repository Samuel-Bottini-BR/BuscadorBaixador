# -*- coding: utf-8 -*-
"""Adaptador para foruns phpBB classicos (estilo prosilver). Caso de teste:
Grand Sud Medieval (https://grand-sud-medieval.fr/forum/), sem robots.txt
publicado -- raspagem educada via ClienteEducado (secao 7 do CLAUDE.md)."""
from bs4 import BeautifulSoup, Comment, NavigableString

from buscador.adapters.base import Item, SiteAdapter
from buscador.core.http_educado import ClienteEducado

USER_AGENT = (
    "BuscadorBaixador-InstitutoSaoBento/0.1 "
    "(uso não comercial, preservação de obras; contato: artesacra.quotidianus@gmail.com)"
)


class PhpbbAdapter(SiteAdapter):
    nome = "Grand Sud Médiéval"

    def __init__(self, url_inicial, cliente=None):
        self.url_inicial = url_inicial
        self.cliente = cliente or ClienteEducado(USER_AGENT)

    def iter_itens(self):
        # Fatia atual só sabe ler uma página de tópico (viewtopic.php).
        # Listar todos os tópicos de um subfórum fica para quando precisarmos.
        yield from self._iter_topico(self.url_inicial)

    def _iter_topico(self, url):
        resposta = self.cliente.get(url)
        _titulo, _secao, itens, _proxima = self._parse_pagina(resposta.text, url)
        yield from itens

    def _parse_pagina(self, html, url_pagina):
        soup = BeautifulSoup(html, "html.parser")
        titulo = self._extrair_titulo_topico(soup)
        secao = self._extrair_secao(soup)
        itens = self._extrair_posts(soup, secao, titulo, url_pagina)
        proxima = self._proxima_pagina(soup)
        return titulo, secao, itens, proxima

    def _extrair_titulo_topico(self, soup):
        h2 = soup.find("h2")
        if h2 is None:
            return ""
        link = h2.find("a")
        return (link or h2).get_text(strip=True)

    def _extrair_secao(self, soup):
        breadcrumb = soup.select_one("ul.linklist.navlinks li.icon-home")
        if breadcrumb is None:
            return ""
        links = breadcrumb.find_all("a")
        return links[-1].get_text(strip=True) if links else ""

    def _extrair_posts(self, soup, secao, titulo_topico, url_pagina):
        itens = []
        for post in soup.select('div.post[id^="p"]'):
            autor = self._extrair_autor(post)
            data_post = self._extrair_data(post)
            explicacao = self._extrair_corpo(post)
            for link in post.select("div.content a.postlink"):
                href = (link.get("href") or "").strip()
                if not href:
                    continue
                itens.append(Item(
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
        textos = [
            t for t in p_author.contents
            if isinstance(t, NavigableString) and not isinstance(t, Comment)
        ]
        return str(textos[-1]).strip() if textos else ""

    def _extrair_corpo(self, post):
        content = post.select_one("div.postbody div.content")
        if content is None:
            return ""
        for comentario in content.find_all(string=lambda s: isinstance(s, Comment)):
            comentario.extract()
        return content.get_text(separator=" ", strip=True)

    def _proxima_pagina(self, soup):
        # Paginacao ainda nao implementada -- fatia seguinte.
        return None
