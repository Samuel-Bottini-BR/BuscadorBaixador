# -*- coding: utf-8 -*-
"""Motor da coleta longa da Gallica (Etapa 1): junta o checkpoint, o
escritor de CSV e a paginacao retomavel do GallicaAdapter para buscar uma
consulta inteira -- ex.: os 933 mil livros do catalogo. Ver CLAUDE.md,
secao sobre mapear o catalogo inteiro da Gallica, e a pergunta em aberto
que originou essa peca."""
import time

import requests

from buscador.adapters.gallica import GallicaAdapter, RespostaVaziaInesperadaError
from buscador.core.checkpoint import carregar_ou_criar, salvar
from buscador.core.coleta_csv import EscritorCsvIncremental

# Sem numero oficial publicado pela BnF para a API de busca (SRU) -- so
# achamos um limite documentado de uma API DIFERENTE (imagens IIIF, 5
# chamadas/minuto), que nao da pra assumir que vale igual aqui. 10 minutos
# e um primeiro palpite pra recalibrar depois do primeiro teste real longo.
COOLDOWN_429_PADRAO_SEGUNDOS = 10 * 60

# Visto ao vivo (2026-09-08): uma pagina no meio de uma coleta real voltou
# vazia por uma falha temporaria da Gallica -- tentar de novo alguns minutos
# depois, manualmente, resolveu em segundos. 30s e' um primeiro palpite bem
# mais curto que o do 429 (que e' sobre cota esgotada, um problema diferente
# e mais demorado de resolver) -- recalibrar se isso se repetir com frequencia.
COOLDOWN_PAGINA_VAZIA_PADRAO_SEGUNDOS = 30

# Visto ao vivo (2026-09-08): depois de ~35 mil itens, um timeout de conexao
# (rede caiu por um instante) derrubou o processo inteiro; pouco depois, um
# 500 do proprio servidor da Gallica fez o mesmo. Numa coleta de dias,
# infraestrutura externa falhando por um instante (wifi, roteador, provedor,
# ou o servidor da Gallica) e' praticamente garantido de acontecer varias
# vezes -- tratamos os dois igual. 60s e' um primeiro palpite pra dar tempo
# de se recuperar sozinho; como a tentativa recomeca sempre do checkpoint,
# uma falha mais longa so significa mais ciclos de espera, nao perda de dado.
COOLDOWN_INFRA_PADRAO_SEGUNDOS = 60


def coletar(consulta, diretorio_job, tamanho_pagina=50, max_registros_alvo=10_000_000,
            cooldown_429_segundos=COOLDOWN_429_PADRAO_SEGUNDOS,
            cooldown_pagina_vazia_segundos=COOLDOWN_PAGINA_VAZIA_PADRAO_SEGUNDOS,
            cooldown_infra_segundos=COOLDOWN_INFRA_PADRAO_SEGUNDOS,
            cliente=None, dormir=time.sleep, progresso_fct=None):
    """Roda ou retoma a coleta bruta de uma consulta inteira. Para cada
    pagina confirmada: grava no CSV e SO DEPOIS avanca e salva o checkpoint
    -- nessa ordem, o pior caso de uma interrupcao e repetir 1 pagina no
    proximo carregar_itens_csv (que ja descarta duplicata por link), nunca
    perder uma pagina inteira. Se um 429 sobreviver as tentativas do
    ClienteEducado (cota esgotada, nao so intervalo curto entre chamadas),
    pausa por cooldown_429_segundos e recomeca do ultimo checkpoint salvo.
    Se uma pagina voltar vazia antes da hora (RespostaVaziaInesperadaError --
    falha temporaria da Gallica, nao o fim real da busca), pausa por
    cooldown_pagina_vazia_segundos e faz o mesmo. Se a infraestrutura falhar
    (rede: timeout/erro de conexao; ou servidor: 5xx), pausa por
    cooldown_infra_segundos e faz o mesmo. So um 4xx que NAO seja 429 propaga
    de verdade -- isso indica problema na nossa propria requisicao (consulta
    mal formada, por exemplo), que tentar de novo pra sempre nao resolve."""
    diretorio_job.mkdir(parents=True, exist_ok=True)
    caminho_checkpoint = diretorio_job / "checkpoint.json"
    caminho_csv = diretorio_job / "itens.csv"
    checkpoint = carregar_ou_criar(caminho_checkpoint, consulta, tamanho_pagina)
    if checkpoint.concluido:
        return checkpoint

    with EscritorCsvIncremental(caminho_csv) as escritor:
        while not checkpoint.concluido:
            adapter = GallicaAdapter(
                consulta, cliente=cliente, max_resultados=max_registros_alvo,
                tamanho_pagina=tamanho_pagina, startrecord_inicial=checkpoint.proximo_start_record,
            )
            try:
                _coletar_paginas_restantes(adapter, escritor, checkpoint, caminho_checkpoint, progresso_fct)
            except requests.HTTPError as erro:
                codigo = erro.response.status_code if erro.response is not None else None
                if codigo == 429:
                    print(f"429 persistente em startRecord={checkpoint.proximo_start_record}; "
                          f"pausando {cooldown_429_segundos}s antes de tentar de novo...")
                    dormir(cooldown_429_segundos)
                    continue
                if codigo is not None and codigo >= 500:
                    print(f"Erro do servidor da Gallica ({codigo}) em startRecord="
                          f"{checkpoint.proximo_start_record}; pausando {cooldown_infra_segundos}s "
                          "antes de tentar de novo...")
                    dormir(cooldown_infra_segundos)
                    continue
                raise  # 4xx que nao e' 429: problema na nossa requisicao, nao adianta tentar de novo
            except RespostaVaziaInesperadaError as erro:
                print(f"{erro} Pausando {cooldown_pagina_vazia_segundos}s antes de tentar de novo...")
                dormir(cooldown_pagina_vazia_segundos)
                continue
            except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as erro:
                print(f"Falha de rede ({erro.__class__.__name__}) em startRecord="
                      f"{checkpoint.proximo_start_record}; pausando {cooldown_infra_segundos}s "
                      "antes de tentar de novo...")
                dormir(cooldown_infra_segundos)
                continue
            checkpoint.concluido = True
            salvar(checkpoint, caminho_checkpoint)
    return checkpoint


def _coletar_paginas_restantes(adapter, escritor, checkpoint, caminho_checkpoint, progresso_fct):
    for inicio_pagina, itens_pagina in adapter.iter_paginas():
        escritor.escrever_pagina(itens_pagina)
        checkpoint.proximo_start_record = inicio_pagina + len(itens_pagina)
        checkpoint.itens_gravados += len(itens_pagina)
        if adapter.total_ultima_busca is not None:
            checkpoint.total_registros_api = adapter.total_ultima_busca
        salvar(checkpoint, caminho_checkpoint)
        if progresso_fct is not None:
            progresso_fct(checkpoint)
