# -*- coding: utf-8 -*-
"""Cliente HTTP que raspa devagar de proposito (CLAUDE.md, secao 7): uma
requisicao por vez, com intervalo minimo entre elas e um User-Agent honesto,
identificavel. Usado por qualquer adaptador que raspa HTML de um site comum."""
import time

import requests


class ClienteEducado:
    TENTATIVAS_429 = 4
    ESPERA_PADRAO_429 = 5.0  # dobra a cada nova tentativa: 5s, 10s, 20s

    def __init__(self, user_agent, intervalo_segundos=2.0, timeout=15.0):
        self.user_agent = user_agent
        self.intervalo_segundos = intervalo_segundos
        self.timeout = timeout
        self._ultima_chamada = None

    def get(self, url):
        for tentativa in range(1, self.TENTATIVAS_429 + 1):
            self._esperar_intervalo()
            self._ultima_chamada = time.monotonic()
            resposta = requests.get(url, headers={"User-Agent": self.user_agent}, timeout=self.timeout)
            if resposta.status_code == 429 and tentativa < self.TENTATIVAS_429:
                padrao = self.ESPERA_PADRAO_429 * (2 ** (tentativa - 1))
                espera = _tempo_de_espera(resposta.headers.get("Retry-After"), padrao)
                time.sleep(espera)
                continue
            resposta.raise_for_status()
            return resposta

    def _esperar_intervalo(self):
        if self._ultima_chamada is None:
            return
        decorrido = time.monotonic() - self._ultima_chamada
        faltam = self.intervalo_segundos - decorrido
        if faltam > 0:
            time.sleep(faltam)


def _tempo_de_espera(cabecalho_retry_after, padrao):
    """O cabecalho Retry-After normalmente e um numero de segundos; se vier
    em outro formato (data HTTP) ou nao vier, usa o padrao."""
    if cabecalho_retry_after and cabecalho_retry_after.strip().isdigit():
        return float(cabecalho_retry_after)
    return padrao
