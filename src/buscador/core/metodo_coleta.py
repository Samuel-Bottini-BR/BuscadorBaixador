# -*- coding: utf-8 -*-
"""A cascata: tenta cada MetodoColeta em ordem. Um metodo indisponivel ou que
levanta AcaoHumanaNecessaria no meio so gera um aviso discreto no log -- o
proximo metodo ainda pode resolver sozinho. So quando o ULTIMO metodo restante
falha e que a cascata levanta AcaoHumanaNecessaria de verdade, juntando os
motivos de todos, para o Samuel saber exatamente o que fazer. Itens ja
produzidos por um metodo antes dele falhar nao se perdem (sao entregues via
yield from antes da excecao)."""
import logging
from abc import ABC, abstractmethod
from typing import Iterator

from buscador.adapters.base import Item
from buscador.core.acao_humana import TIPO_LOGIN, AcaoHumanaNecessaria

logger = logging.getLogger(__name__)


class MetodoColeta(ABC):
    nome: str = "metodo"

    def disponivel(self) -> bool:
        """Checagem rapida, sem rede -- ex.: 'tenho a chave configurada?'.
        Default: sempre disponivel (metodos que nao precisam de nada extra,
        como raspagem HTML, nao precisam sobrescrever isso)."""
        return True

    @abstractmethod
    def iter_itens(self) -> Iterator[Item]:
        """Pode levantar AcaoHumanaNecessaria ao descobrir, so na hora
        (ex. resposta 401), que nao consegue prosseguir."""
        raise NotImplementedError


def _montar_mensagem(motivos: list[str]) -> str:
    return "Nenhum metodo funcionou. " + " | ".join(motivos)


def coletar_em_cascata(metodos: list["MetodoColeta"], nome_site: str) -> Iterator[Item]:
    if not metodos:
        raise ValueError("coletar_em_cascata precisa de pelo menos um metodo")

    motivos: list[str] = []
    ultimo_tipo = TIPO_LOGIN

    for indice, metodo in enumerate(metodos):
        eh_ultimo = indice == len(metodos) - 1

        if not metodo.disponivel():
            motivo = f"{metodo.nome}: nao disponivel"
            if eh_ultimo:
                raise AcaoHumanaNecessaria(
                    tipo=ultimo_tipo,
                    mensagem=_montar_mensagem(motivos + [motivo]),
                    site=nome_site,
                )
            logger.info("Pulando %s para %s (%s); tentando o proximo.", metodo.nome, nome_site, motivo)
            motivos.append(motivo)
            continue

        try:
            yield from metodo.iter_itens()
            return
        except AcaoHumanaNecessaria as erro:
            ultimo_tipo = erro.tipo
            motivo = f"{metodo.nome}: {erro.mensagem}"
            if eh_ultimo:
                raise AcaoHumanaNecessaria(
                    tipo=erro.tipo,
                    mensagem=_montar_mensagem(motivos + [motivo]),
                    site=nome_site,
                )
            logger.info("Metodo %s parou para %s (%s); tentando o proximo.", metodo.nome, nome_site, erro.mensagem)
            motivos.append(motivo)
            continue
