# -*- coding: utf-8 -*-
"""
Este arquivo define o "ClienteEducado" -- o "mensageiro" que qualquer
adaptador usa pra pedir páginas/dados pela internet (fazer uma
"requisição HTTP", que é como o navegador pede uma página quando você
digita um endereço).

Ele é "educado" de propósito (ver seção 7 do CLAUDE.md): pede uma coisa de
cada vez, espera um tempinho mínimo entre um pedido e outro, e se
identifica honestamente pro site (User-Agent -- o "nome" que o programa diz
que é), em vez de disfarçar como se fosse um navegador comum sendo usado
por uma pessoa.
"""
import time

import requests  # biblioteca padrão da comunidade Python pra fazer requisições HTTP (pedidos pela internet)


class ClienteEducado:
    TENTATIVAS_429 = 4
    # "429" é um código de status HTTP que quer dizer "Too Many Requests"
    # (você pediu demais, espera um pouco) -- o site usa isso pra se
    # defender de sobrecarga. TENTATIVAS_429 é quantas vezes tentamos de
    # novo antes de desistir de vez.
    ESPERA_PADRAO_429 = 5.0  # dobra a cada nova tentativa: 5s, 10s, 20s

    def __init__(self, user_agent, intervalo_segundos=2.0, timeout=15.0):
        # __init__ roda quando criamos um ClienteEducado novo, tipo
        # ClienteEducado("meu-nome-de-programa").
        self.user_agent = user_agent
        self.intervalo_segundos = intervalo_segundos  # tempo mínimo (em segundos) entre um pedido e outro
        self.timeout = timeout  # depois de quantos segundos desistir de esperar resposta de um pedido
        self._ultima_chamada = None  # guarda quando foi o último pedido feito, pra saber se já passou tempo suficiente

    def get(self, url):
        # "get" é o tipo de pedido HTTP usado pra simplesmente LER algo
        # (diferente de "post", que normalmente ENVIA dado pra um site).
        for tentativa in range(1, self.TENTATIVAS_429 + 1):
            self._esperar_intervalo()  # espera o tempo mínimo, se ainda não tiver passado
            self._ultima_chamada = time.monotonic()
            # "time.monotonic()" é um relógio que só anda pra frente, nunca
            # "pula" pra trás -- melhor que a hora normal do computador pra
            # medir quanto tempo passou entre dois momentos.
            resposta = requests.get(url, headers={"User-Agent": self.user_agent}, timeout=self.timeout)
            if resposta.status_code == 429 and tentativa < self.TENTATIVAS_429:
                # o site pediu pra esperar -- calcula quanto tempo e tenta de novo
                padrao = self.ESPERA_PADRAO_429 * (2 ** (tentativa - 1))
                # "2 ** (tentativa - 1)" é "2 elevado a (tentativa - 1)" --
                # dobra o tempo de espera a cada nova tentativa (1x, 2x, 4x)
                espera = _tempo_de_espera(resposta.headers.get("Retry-After"), padrao)
                time.sleep(espera)
                continue  # volta pro início do "for" e tenta de novo
            resposta.raise_for_status()
            # ".raise_for_status()" levanta um erro automaticamente se a
            # resposta veio com um código de "deu errado" (404, 500, etc.)
            # -- assim quem usa esse cliente não precisa checar isso na mão.
            return resposta

    def _esperar_intervalo(self):
        # Garante que passou pelo menos "intervalo_segundos" desde o último
        # pedido -- se não, dorme (pausa a execução) o tempo que falta.
        if self._ultima_chamada is None:
            return  # primeira chamada de todas -- não tem intervalo anterior pra respeitar
        decorrido = time.monotonic() - self._ultima_chamada
        faltam = self.intervalo_segundos - decorrido
        if faltam > 0:
            time.sleep(faltam)


def _tempo_de_espera(cabecalho_retry_after, padrao):
    """O cabecalho Retry-After normalmente e um numero de segundos; se vier
    em outro formato (data HTTP) ou nao vier, usa o padrao."""
    # "Retry-After" é um cabeçalho (informação extra que vem junto da
    # resposta HTTP, fora do conteúdo principal) que alguns sites mandam
    # avisando exatamente quanto tempo esperar antes de tentar de novo.
    if cabecalho_retry_after and cabecalho_retry_after.strip().isdigit():
        return float(cabecalho_retry_after)
    return padrao
