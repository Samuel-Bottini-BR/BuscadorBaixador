# -*- coding: utf-8 -*-
"""
Este arquivo é a "cascata" -- a peça central de todo o desenho de "tentar
vários jeitos de coletar um site, em ordem, e só avisar o Samuel quando
nada funcionar". Ela tenta cada MetodoColeta (definido logo abaixo) em
ordem. Um método indisponível, ou que levanta AcaoHumanaNecessaria no meio,
só gera um aviso discreto no log (mensagem interna, não interrompe nada) --
porque o PRÓXIMO método da lista ainda pode resolver sozinho. Só quando o
ÚLTIMO método restante falha é que a cascata levanta AcaoHumanaNecessaria
de verdade, juntando os motivos de todos os métodos que falharam, pro
Samuel saber exatamente o que fazer. Itens já produzidos por um método
antes dele falhar não se perdem (são entregues via "yield from" -- ver
explicação abaixo -- antes do erro acontecer).
"""
import logging
from abc import ABC, abstractmethod  # ferramentas do Python pra criar uma classe que serve só de "molde" (ver adapters/base.py)
from typing import Iterator  # só usado pra documentar o tipo de dado que uma função devolve

from buscador.adapters.base import Item
from buscador.core.acao_humana import TIPO_LOGIN, AcaoHumanaNecessaria

logger = logging.getLogger(__name__)


class MetodoColeta(ABC):
    """O "molde" que cada jeito de coletar um site (API, HTML cru,
    navegador automatizado) precisa seguir, pra poder entrar na lista que
    coletar_em_cascata() vai tentar em ordem."""

    nome: str = "metodo"  # cada método real vai sobrescrever isso com um nome descritivo (ex.: "API sem chave")

    def disponivel(self) -> bool:
        """Checagem rapida, sem rede -- ex.: 'tenho a chave configurada?'.
        Default: sempre disponivel (metodos que nao precisam de nada extra,
        como raspagem HTML, nao precisam sobrescrever isso)."""
        # Essa função já vem pronta aqui (ao contrário de iter_itens
        # abaixo) porque a maioria dos métodos não precisa de nenhuma
        # checagem prévia -- só os que dependem de algo (tipo uma chave
        # configurada) precisam escrever sua própria versão dessa função.
        return True

    @abstractmethod  # obriga qualquer MetodoColeta real a escrever a própria versão desta função
    def iter_itens(self) -> Iterator[Item]:
        """Pode levantar AcaoHumanaNecessaria ao descobrir, so na hora
        (ex. resposta 401), que nao consegue prosseguir."""
        raise NotImplementedError


def _montar_mensagem(motivos: list[str]) -> str:
    """Junta a lista de motivos (um texto por método que falhou) numa
    única mensagem, separando cada um com " | ", pro Samuel ver de uma vez
    só tudo que já foi tentado."""
    return "Nenhum metodo funcionou. " + " | ".join(motivos)


def coletar_em_cascata(metodos: list["MetodoColeta"], nome_site: str) -> Iterator[Item]:
    """Função principal deste arquivo. Recebe a lista de métodos (na ordem
    que devem ser tentados) e o nome do site (só pra aparecer numa
    eventual mensagem de erro), e devolve os itens encontrados -- também
    como um "gerador" (ver adapters/base.py pra entender o que é isso),
    igual qualquer iter_itens()."""
    if not metodos:
        raise ValueError("coletar_em_cascata precisa de pelo menos um metodo")

    motivos: list[str] = []  # vai guardando o motivo de cada método que não funcionou
    ultimo_tipo = TIPO_LOGIN  # valor padrão pro "tipo" do erro final, caso nunca tenhamos um erro real pra copiar o tipo dele

    for indice, metodo in enumerate(metodos):
        # "enumerate" percorre a lista já contando a posição de cada item (0, 1, 2...)
        eh_ultimo = indice == len(metodos) - 1
        # compara a posição atual com a última posição possível da lista

        if not metodo.disponivel():
            # esse método já avisou, sem nem tentar de verdade, que não dá pra usar agora
            motivo = f"{metodo.nome}: nao disponivel"
            if eh_ultimo:
                # não sobrou mais nenhum método pra tentar depois deste --
                # agora sim precisa parar tudo e avisar o Samuel de verdade
                raise AcaoHumanaNecessaria(
                    tipo=ultimo_tipo,
                    mensagem=_montar_mensagem(motivos + [motivo]),
                    site=nome_site,
                )
            # ainda tem outro método na lista pra tentar -- só registra no
            # log (mensagem interna, não trava nada) e segue pro próximo
            logger.info("Pulando %s para %s (%s); tentando o proximo.", metodo.nome, nome_site, motivo)
            motivos.append(motivo)
            continue  # pula pro próximo método da lista, sem tentar iter_itens() deste

        try:
            yield from metodo.iter_itens()
            # "yield from" repassa, um por um, cada Item que esse método
            # produzir -- se o método conseguir entregar tudo sem erro,
            # esses itens já chegam em quem estiver usando coletar_em_cascata()
            return  # esse método funcionou até o fim -- não precisa tentar mais nenhum outro
        except AcaoHumanaNecessaria as erro:
            # o método começou a produzir itens (talvez alguns, talvez
            # nenhum) mas travou no meio, precisando de ajuda humana
            ultimo_tipo = erro.tipo  # guarda o tipo desse erro, caso ele acabe sendo o motivo final
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
            # Importante: os itens que esse método já tinha produzido ANTES
            # de travar não somem -- eles já foram entregues lá em cima,
            # pelo "yield from", antes da exceção acontecer. Só o RESTO da
            # coleta (que esse método não conseguiu terminar) é que passa
            # a ser tentado pelo próximo método da lista.
