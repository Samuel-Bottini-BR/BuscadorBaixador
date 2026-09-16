# -*- coding: utf-8 -*-
"""
Este arquivo define o "molde" (em programação, isso se chama uma interface,
ou classe base / base class) que todo "adaptador" de site precisa seguir.

Um "adaptador" é o pedaço de código responsável por saber coletar
informações de UM site específico -- por exemplo, existe um adaptador para
o fórum Grand Sud (phpbb.py) e outro para a Gallica (gallica.py).

Este arquivo aqui não sabe coletar nada de site nenhum sozinho -- ele só
define as REGRAS que qualquer adaptador novo precisa seguir, tipo um
contrato. Ver a seção 8 do CLAUDE.md do projeto para mais contexto.
"""
from abc import ABC, abstractmethod  # ferramentas do Python pra criar esse "molde"/contrato
from dataclasses import dataclass, field  # dataclass: forma rápida de criar uma "caixinha" de dados
from typing import Iterator  # so usado pra documentar o tipo de dado que uma funcao devolve


@dataclass  # isso transforma a classe Item, logo abaixo, automaticamente numa "caixinha" pronta pra guardar dados -- sem precisar escrever na mão o código repetitivo de guardar cada campo
class Item:
    """Um Item representa UM achado de um adaptador -- por exemplo, um link
    de livro encontrado num site. Cada Item vira, mais pra frente, uma linha
    na planilha final (a "Fase 1" do projeto)."""

    # Cada linha abaixo é um "campo" (um pedacinho de informação) que um
    # achado pode ter. O "= ""'' no final quer dizer "se ninguém preencher,
    # o valor começa vazio" -- ou seja, não é obrigatório preencher tudo na
    # hora de criar um Item nesse campo.
    titulo_original: str        # titulo do jeito que apareceu no site (no idioma original dele)
    link: str                   # o endereço (URL) onde esse item foi encontrado
    titulo_pt: str = ""         # titulo traduzido pro português (preenchido depois, por outro pedaço do código)
    autor: str = ""
    ano: str = ""
    tipo: str = ""              # ex.: "pdf direto", "página", "precisa login" -- ver core/verificacao_links.py
    explicacao: str = ""        # um resumo/descrição do que se trata esse item
    fonte: str = ""             # de onde veio a informação (ex.: nome da editora)
    provedor: str = ""          # o nome do site/instituição que disponibiliza o item
    dominio_publico: str = ""   # "Sim"/"Não" -- se a obra já está em domínio público
    secao: str = ""             # em que parte/categoria do site esse item apareceu
    url_pagina: str = ""        # a página onde o item foi encontrado (pode ser igual a "link")
    status_link: str = ""       # se o link está funcionando, quebrado, etc. (preenchido depois)
    avaliacao_humana: str = ""  # fica vazio de propósito -- é pra você (humano) preencher na planilha
    extra: dict = field(default_factory=dict)
    # "extra" é um "dicionário" (dict -- uma caixa que guarda pares
    # nome->valor, tipo um mini-arquivo de configuração) pra cada adaptador
    # guardar informações extras que só fazem sentido pra ele (ex.: o idioma
    # original do texto), sem precisar mudar essa classe toda vez que um
    # adaptador novo precisar de um campo diferente que os outros não usam.


class SiteAdapter(ABC):  # "ABC" = Abstract Base Class: uma classe que serve só de MOLDE, nunca é usada diretamente sozinha
    """Este é o "contrato": toda vez que quisermos ensinar o programa a
    coletar de um site novo, criamos uma classe nova que HERDA (usa como
    base, em inglês "inherit") esta classe aqui, e escrevemos por dentro
    dela como aquele site específico funciona. O resto do programa
    (planilha, tradução, etc.) não precisa saber nada sobre o site
    específico -- só precisa saber que qualquer SiteAdapter tem um método
    chamado iter_itens()."""

    nome: str = "base"  # cada adaptador real vai sobrescrever isso com o nome do site (ex.: "Gallica (BnF)")

    @abstractmethod  # isso obriga qualquer adaptador novo a escrever a própria versão de iter_itens() -- sem isso, o Python nem deixa criar o adaptador
    def iter_itens(self) -> Iterator[Item]:
        """Esta função é um "gerador" (generator, em inglês) -- em vez de
        devolver uma lista inteira de uma vez só, ela vai "produzindo" um
        Item por vez, conforme quem estiver usando for pedindo o próximo.
        Isso economiza memória quando tem muitos itens (não precisa guardar
        tudo de uma vez na memória do computador).

        Cada adaptador precisa escrever essa função do seu próprio jeito --
        é aqui dentro que ele efetivamente acessa a internet, página por
        página, seguindo a regra de acesso educado descrita na seção 7 do
        CLAUDE.md (não pode simplesmente sair fazendo requisição sem
        controle nenhum)."""
        raise NotImplementedError  # isso nunca deveria rodar de verdade -- é só um aviso de "essa função tem que ser reescrita por quem herdar essa classe"

    def descrever(self, item: Item) -> str:
        """Monta um texto curto tipo "NomeDoSite > secao: titulo", só pra
        ajudar a identificar um item em mensagens de log/depuração (texto
        que aparece no terminal pra ajudar a entender o que o programa está
        fazendo). Essa função já vem pronta aqui (diferente de
        iter_itens()) porque todo adaptador vai usar o mesmo formato de
        texto, então não faz sentido cada um escrever a sua versão."""
        partes = [p for p in (self.nome, item.secao, item.titulo_original) if p]
        # a linha acima monta uma lista só com os pedaços que não estão vazios
        if not partes:
            return ""
        if len(partes) == 1:
            return partes[0]
        # ".join" gruda os pedaços com " > " no meio, deixando o último separado por ":"
        return " > ".join(partes[:-1]) + f": {partes[-1]}"
