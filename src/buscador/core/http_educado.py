# -*- coding: utf-8 -*-
"""Cliente HTTP que raspa devagar de proposito (CLAUDE.md, secao 7): uma
requisicao por vez, com intervalo minimo entre elas e um User-Agent honesto,
identificavel. Usado por qualquer adaptador que raspa HTML de um site comum."""
import time

import requests


class ClienteEducado:
    def __init__(self, user_agent, intervalo_segundos=2.0, timeout=15.0):
        self.user_agent = user_agent
        self.intervalo_segundos = intervalo_segundos
        self.timeout = timeout
        self._ultima_chamada = None

    def get(self, url):
        self._esperar_intervalo()
        self._ultima_chamada = time.monotonic()
        resposta = requests.get(url, headers={"User-Agent": self.user_agent}, timeout=self.timeout)
        resposta.raise_for_status()
        return resposta

    def _esperar_intervalo(self):
        if self._ultima_chamada is None:
            return
        decorrido = time.monotonic() - self._ultima_chamada
        faltam = self.intervalo_segundos - decorrido
        if faltam > 0:
            time.sleep(faltam)
