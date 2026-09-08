# -*- coding: utf-8 -*-
"""Interface comum que todo adaptador de site precisa seguir (CLAUDE.md, secao 8)."""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Iterator


@dataclass
class Item:
    """Um achado de um adaptador: um link a caminho da planilha da Fase 1."""
    titulo_original: str
    link: str
    titulo_pt: str = ""
    autor: str = ""
    ano: str = ""
    tipo: str = ""
    explicacao: str = ""
    fonte: str = ""
    provedor: str = ""
    dominio_publico: str = ""
    secao: str = ""
    url_pagina: str = ""
    status_link: str = ""
    avaliacao_humana: str = ""
    extra: dict = field(default_factory=dict)


class SiteAdapter(ABC):
    """Cada site cadastrado ganha um adaptador. Adicionar um site novo =
    escrever uma classe nova aqui dentro, sem mexer no resto do motor."""

    nome: str = "base"

    @abstractmethod
    def iter_itens(self) -> Iterator[Item]:
        """Gerador: produz um Item por achado. Deve fazer as proprias
        requisicoes de rede, respeitando a regra de acesso do site (secao 7
        do CLAUDE.md)."""
        raise NotImplementedError

    def descrever(self, item: Item) -> str:
        partes = [p for p in (self.nome, item.secao, item.titulo_original) if p]
        if not partes:
            return ""
        if len(partes) == 1:
            return partes[0]
        return " > ".join(partes[:-1]) + f": {partes[-1]}"
