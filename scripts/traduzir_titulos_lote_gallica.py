# -*- coding: utf-8 -*-
"""Traduz (fr->pt) os titulos das 26.544 obras unicas (ja deduplicadas por
ark_id e categorizadas por categorizar_amostra_gallica.py), em lotes
retomaveis - nao numa chamada so.

Atualizado em 23/09/2026: le gallica_categorizado_dedupado.json (26.544
obras unicas) em vez do antigo gallica_categorizado_completo.json (46.222
itens brutos, com duplicata) - ver scripts/deduplicar_gallica_por_ark.py.

DUAS DECISOES tomadas nesta sessao (17/09/2026), registradas aqui porque
mudam o comportamento padrao de core/traducao.py:traduzir() - ver
HANDOFF.md pra mais contexto.

1) Offline em vez da cascata online->offline. Medido ao vivo contra os 46
   mil titulos reais: Google Translate falhou 429 (cota esgotada) em 100%
   das chamadas mesmo com so 1 tentativa; MyMemory comecou funcionando mas
   parou no meio (cota diaria gratuita); depois disso tudo cai pro offline
   de qualquer jeito. Custo medido: cascata online ~4-10s/item; offline
   direto (argostranslate, pacote fr->en->pt ja instalado) ~0.1-0.7s/item.
   Com 46 mil itens: ~1,5-2h so offline contra 5-12h tentando online
   primeiro em toda chamada. Decisao: chama _traduzir_offline() direto -
   mesma funcao que traduzir() usaria por ultimo na cascata dela, so
   pulando a etapa online que se mostrou inutil neste volume/sessao.
   Qualidade menor que o Google (pivo fr->en->pt em vez de fr->pt direto).

2) Timeout por lote, nao so por checkpoint. Descoberta ao vivo: um punhado
   de titulos "fora do frances comum" (poesia occitana/provencal
   medieval tipo "Amics, s'ie'us trobes avinen", ou transliteracao arabe
   tipo "'Aga'ib al-maḫluqat...") faz o modelo de traducao (pensado pra
   frances moderno) demorar MUITO mais que o normal (minutos em vez de
   fracoes de segundo) - nao trava para sempre (o processo seguia consumindo
   CPU de verdade, so muito devagar), mas como esses titulos tendem a
   aparecer AGRUPADOS (a Gallica organiza manuscritos medievais do mesmo
   jeito/epoca juntos), um lote inteiro podia ficar minutos sem terminar
   nenhum item, represando o checkpoint. _traduzir_lote() abaixo usa
   as_completed() (pega resultado de quem terminar primeiro, no importa a
   ordem) em vez de map() (que so entrega resultado na ordem de entrada,
   e trava tudo atras de um item lento) e desiste de esperar o resto do
   lote depois de TIMEOUT_LOTE_SEGUNDOS - o que nao terminou fica pendente
   pra proxima rodada (a thread de fato ainda roda em segundo plano ate
   terminar sozinha, so o script nao espera mais por ela).

Resumivel de verdade: a cada lote, o resultado (titulo_traduzido gravado
em cada item que terminou a tempo) e salvo por cima do arquivo de saida -
se o processo for interrompido, ou se um item ficar pendente por timeout,
rodar de novo pula quem ja tem titulo_traduzido e tenta de novo quem nao
tem (inclusive os poucos itens lentos, que eventualmente conseguem
terminar dentro da janela de timeout de algum lote).
"""
import json
import sys
import time
import concurrent.futures as cf
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "src"))
from buscador.core.traducao import _traduzir_offline, _garantir_modelo_argos  # noqa: E402

ORIGEM = RAIZ / "saidas" / "gallica_categorizado_dedupado.json"
SAIDA = RAIZ / "saidas" / "gallica_categorizado_traduzido.json"

LOTE_TAMANHO = 500
WORKERS = 8  # acima disso o ganho medido foi quase nulo (GIL) - ver docstring
TIMEOUT_LOTE_SEGUNDOS = 180  # desiste de esperar o lote inteiro depois disso
PAUSA_ENTRE_LOTES_SEGUNDOS = 1.0


def _traduzir_um_titulo(titulo):
    try:
        return _traduzir_offline(titulo, "fr", "pt")
    except Exception:
        # mesma garantia de traduzir(): nunca deixa um titulo problematico
        # derrubar o lote - devolve o original.
        return titulo


def _traduzir_lote(itens, fatia_indices):
    """Traduz um lote de indices de `itens`, gravando titulo_traduzido em
    cada item que terminar a tempo. Devolve (concluidos, pendentes) so pra
    log - `itens` ja fica atualizado por referencia."""
    executor = cf.ThreadPoolExecutor(max_workers=WORKERS)
    futuro_para_indice = {
        executor.submit(_traduzir_um_titulo, itens[i]["titulo"]): i for i in fatia_indices
    }
    concluidos = 0
    try:
        for futuro in cf.as_completed(futuro_para_indice, timeout=TIMEOUT_LOTE_SEGUNDOS):
            i = futuro_para_indice[futuro]
            itens[i]["titulo_traduzido"] = futuro.result()
            concluidos += 1
    except cf.TimeoutError:
        pass  # alguns itens (provavelmente com texto fora do frances comum)
        # nao terminaram a tempo - ficam sem titulo_traduzido, tentados de
        # novo numa proxima rodada (ver docstring do modulo, item 2).
    finally:
        # cancel_futures=True descarta quem ainda nem tinha COMECADO a
        # rodar; quem ja estava EM ANDAMENTO continua ate terminar sozinho
        # (Python nao mata thread no meio), so o script nao fica esperando.
        executor.shutdown(wait=False, cancel_futures=True)
    return concluidos, len(fatia_indices) - concluidos


def main():
    if SAIDA.exists():
        itens = json.loads(SAIDA.read_text(encoding="utf-8"))
        print(f"Retomando: {SAIDA.name} ja existe com {len(itens)} itens.")
    else:
        itens = json.loads(ORIGEM.read_text(encoding="utf-8"))
        print(f"Comecando do zero: {len(itens)} itens carregados de {ORIGEM.name}.")

    # "titulo_traduzido" nao em item (nao so falsy) - um titulo com texto
    # fora do frances comum (ex.: transliteracao arabe) pode legitimamente
    # traduzir pra string vazia; contar isso como "ainda pendente" faria
    # esse item especifico ser tentado de novo pra sempre, toda rodada.
    pendentes_idx = [i for i, item in enumerate(itens) if "titulo_traduzido" not in item]
    total_pendentes = len(pendentes_idx)
    print(f"{len(itens) - total_pendentes} ja traduzidos, {total_pendentes} pendentes.")
    if not total_pendentes:
        print("Nada a fazer.")
        return

    # Garante o pacote fr->en->pt instalado ANTES de abrir threads (o
    # controle de pacotes instalados do argostranslate nao e seguro pra
    # varias threads mexerem ao mesmo tempo - mesma cautela de
    # enriquecimento_lote.py:_pre_aquecer_traducao).
    _garantir_modelo_argos("fr", "en")
    _garantir_modelo_argos("en", "pt")

    total_lotes = (total_pendentes + LOTE_TAMANHO - 1) // LOTE_TAMANHO
    inicio_geral = time.time()
    feitos_ate_agora = 0
    for indice_lote in range(total_lotes):
        fatia = pendentes_idx[indice_lote * LOTE_TAMANHO: (indice_lote + 1) * LOTE_TAMANHO]
        t0 = time.time()
        concluidos, pendentes_no_lote = _traduzir_lote(itens, fatia)
        feitos_ate_agora += concluidos

        SAIDA.write_text(json.dumps(itens, ensure_ascii=False, indent=1), encoding="utf-8")
        dt = time.time() - t0
        aviso = f" ({pendentes_no_lote} ficaram pendentes por timeout)" if pendentes_no_lote else ""
        print(f"Lote {indice_lote + 1}/{total_lotes} salvo: {concluidos}/{len(fatia)} traduzidos "
              f"em {dt:.0f}s{aviso}. Total geral: {feitos_ate_agora}/{total_pendentes}.")
        if indice_lote + 1 < total_lotes:
            time.sleep(PAUSA_ENTRE_LOTES_SEGUNDOS)

    print(f"\nRodada completa em {(time.time() - inicio_geral) / 60:.1f} min. Salvo: {SAIDA}")
    restantes = sum(1 for item in itens if "titulo_traduzido" not in item)
    if restantes:
        print(f"{restantes} itens ainda sem titulo_traduzido (ficaram pendentes por timeout "
              f"em algum lote) - rode o script de novo pra tentar so esses.")


if __name__ == "__main__":
    main()
