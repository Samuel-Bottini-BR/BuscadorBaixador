# -*- coding: utf-8 -*-
"""
Motor da Etapa 2: verifica link + traduz cada item coletado pela Etapa 1,
em paralelo (várias coisas acontecendo "ao mesmo tempo", pra ir mais
rápido -- como o verificar_links.py já faz na raiz do projeto), em lotes
(grupos de itens processados juntos, em vez de todos de uma vez). Cada lote
confirmado vira uma planilha .xlsx (pra revisão humana, com cor/dropdown --
ver core/planilha.py) e entra num CSV acumulado (dado leve, pra importar em
outro programa depois). É retomável: um lote já processado (segundo o
checkpoint) é pulado, não refeito.
"""
import concurrent.futures as cf  # ferramentas do Python pra rodar várias tarefas ao mesmo tempo (em paralelo)
import csv
import json
import math
import os
import time  # usado só pra esperar um instante entre tentativas de trocar o arquivo (ver "salvar_checkpoint")
from dataclasses import asdict, dataclass

from buscador.core.enriquecimento import enriquecer_item
from buscador.core.planilha import COLUNAS as COLUNAS_PLANILHA
from buscador.core.planilha import gerar_planilha
from buscador.core.traducao import traduzir

LOTE_TAMANHO_PADRAO = 20_000
WORKERS_PADRAO = 40
# "workers" (trabalhadores) são as "threads" (linhas de execução paralelas)
# usadas pra verificar vários links ao mesmo tempo, em vez de um de cada
# vez -- 40 delas rodando juntas deixa o processo bem mais rápido.

# So os idiomas que os adaptadores realmente produzem (ver traducao.py).
# Aquecer cada um em serie, ANTES de abrir o pool de threads, evita que
# varias threads tentem instalar o mesmo pacote do argostranslate ao mesmo
# tempo -- o cache de pacotes instalados desse modulo nao tem lock.
_IDIOMA_CAMPO_EXTRA = "idioma_origem"
# "pool de threads" = um grupo de "trabalhadores" (threads) prontos pra
# pegar tarefas; "lock" = um trava de segurança que impede duas threads de
# mexerem na mesma coisa ao mesmo tempo e bagunçarem tudo.


@dataclass
class CheckpointEnriquecimento:
    # A "caixinha" de progresso desta etapa -- parecida com Checkpoint de
    # core/checkpoint.py, mas mais simples, porque aqui o progresso é só
    # "em que lote eu parei", não uma página de API.
    total_itens: int
    lote_tamanho: int
    proximo_lote: int = 0
    atualizado_em: str = ""


def carregar_ou_criar_checkpoint(caminho_json, total_itens, lote_tamanho) -> CheckpointEnriquecimento:
    if caminho_json.exists():
        dados = json.loads(caminho_json.read_text(encoding="utf-8"))
        return CheckpointEnriquecimento(**dados)
    checkpoint = CheckpointEnriquecimento(total_itens=total_itens, lote_tamanho=lote_tamanho)
    salvar_checkpoint(checkpoint, caminho_json)
    return checkpoint


TENTATIVAS_WINDOWS = 10  # quantas vezes tentar trocar o arquivo quando o Windows nega acesso por um instante
ESPERA_ENTRE_TENTATIVAS = 0.05  # segundos de espera entre uma tentativa e outra (10 x 0,05 s = meio segundo no total)


def salvar_checkpoint(checkpoint: CheckpointEnriquecimento, caminho_json) -> None:
    # Mesma técnica de core/checkpoint.py: salva primeiro num arquivo
    # temporário e só depois troca pelo definitivo, pra nunca deixar um
    # checkpoint pela metade se o programa for interrompido bem no meio.
    caminho_json.parent.mkdir(parents=True, exist_ok=True)
    caminho_tmp = caminho_json.with_suffix(caminho_json.suffix + ".tmp")
    caminho_tmp.write_text(json.dumps(asdict(checkpoint), ensure_ascii=False, indent=2), encoding="utf-8")
    # No Windows, enquanto OUTRO processo tem o checkpoint definitivo aberto (ex.:
    # o comando "status" do motor de jobs lendo o progresso), o os.replace falha
    # com PermissionError [WinError 5]. É azar de um instante, não um erro de
    # verdade -- então tenta de novo algumas vezes antes de desistir, em vez de
    # derrubar uma coleta que já rodou horas. Mesma técnica (e mesmos números) de
    # core/checkpoint.py::salvar; padrão do "_com_tentativas" de core/jobs_registro.py.
    for tentativa in range(TENTATIVAS_WINDOWS):
        try:
            os.replace(caminho_tmp, caminho_json)
            break
        except PermissionError:
            if tentativa == TENTATIVAS_WINDOWS - 1:
                raise  # todas as tentativas negadas: não é azar de um instante, deixa o erro subir
            time.sleep(ESPERA_ENTRE_TENTATIVAS)


def enriquecer_em_lotes(itens, diretorio_job, lote_tamanho=LOTE_TAMANHO_PADRAO,
                         workers=WORKERS_PADRAO, progresso_fct=None):
    """Função principal deste arquivo. Recebe TODOS os itens já coletados
    (ex.: pelo core/coleta_gallica.py) e processa lote por lote."""
    diretorio_job.mkdir(parents=True, exist_ok=True)
    caminho_checkpoint = diretorio_job / "checkpoint_enriquecimento.json"
    caminho_csv_enriquecido = diretorio_job / "itens_enriquecidos.csv"
    checkpoint = carregar_ou_criar_checkpoint(caminho_checkpoint, len(itens), lote_tamanho)
    total_lotes = math.ceil(len(itens) / lote_tamanho) if itens else 0
    # "math.ceil" arredonda PRA CIMA -- se sobrar um resto de itens que não
    # completa um lote inteiro, ainda conta como mais um lote (ex.: 45.000
    # itens com lotes de 20.000 dá 3 lotes: 20k + 20k + 5k restantes)

    _pre_aquecer_traducao(itens)

    with _EscritorCsvEnriquecido(caminho_csv_enriquecido) as escritor_csv:
        for indice in range(checkpoint.proximo_lote, total_lotes):
            # começa do lote onde o checkpoint disse que parou, não do zero
            lote = itens[indice * lote_tamanho: (indice + 1) * lote_tamanho]
            # essa é a forma do Python de "fatiar" uma lista -- pega só um
            # pedaço dela, do índice inicial até (sem incluir) o índice final
            caminho_planilha = diretorio_job / f"planilha_lote_{indice + 1:04d}.xlsx"
            # ":04d" formata o número do lote com 4 dígitos e zero na
            # frente se precisar (ex.: "0001", "0002"), pra os arquivos
            # ficarem em ordem certa quando listados por nome

            with cf.ThreadPoolExecutor(max_workers=workers) as executor:
                # cria o grupo de "trabalhadores" (threads) e distribui o
                # trabalho de enriquecer cada item do lote entre eles
                lote_enriquecido = list(executor.map(enriquecer_item, lote))
                # "executor.map" aplica a função enriquecer_item em cada
                # item do lote, em paralelo, e devolve os resultados na
                # mesma ordem de entrada (mesmo rodando fora de ordem por dentro)

            gerar_planilha(lote_enriquecido, caminho_planilha)
            escritor_csv.escrever_itens(lote_enriquecido)
            checkpoint.proximo_lote = indice + 1
            salvar_checkpoint(checkpoint, caminho_checkpoint)
            if progresso_fct is not None:
                progresso_fct(checkpoint, total_lotes)

    return checkpoint


def _pre_aquecer_traducao(itens):
    """Antes de abrir o pool de threads, garante que o pacote de tradução
    offline de cada idioma que vai aparecer já está instalado -- feito UM
    idioma de cada vez, em série (não em paralelo), porque a parte do
    argostranslate que controla quais pacotes já estão instalados não é
    segura pra várias threads mexerem ao mesmo tempo (poderiam tentar
    instalar o mesmo pacote duas vezes ao mesmo tempo e se atrapalhar)."""
    idiomas = {item.extra.get(_IDIOMA_CAMPO_EXTRA) for item in itens if item.extra.get(_IDIOMA_CAMPO_EXTRA)}
    # "set comprehension" -- monta um conjunto (sem repetir) com cada
    # idioma diferente que aparece nos itens, ignorando os que não têm idioma definido
    for idioma in idiomas:
        traduzir("teste", idioma_origem=idioma)
        # traduz uma palavra qualquer só pra forçar a instalação do pacote
        # necessário AGORA, antes das threads começarem a rodar em paralelo


class _EscritorCsvEnriquecido:
    """Grava o resultado final (ja verificado e traduzido) em CSV, lote por
    lote -- as mesmas colunas do .xlsx, sem cor/dropdown, pensado pra
    importar em outro programa (planilha, banco de dados, etc.)."""

    def __init__(self, caminho_csv):
        arquivo_novo = not caminho_csv.exists() or caminho_csv.stat().st_size == 0
        caminho_csv.parent.mkdir(parents=True, exist_ok=True)
        self._arquivo = open(caminho_csv, "a", newline="", encoding="utf-8")
        self._escritor = csv.DictWriter(self._arquivo, fieldnames=COLUNAS_PLANILHA)
        if arquivo_novo:
            self._escritor.writeheader()
            self._sincronizar()

    def escrever_itens(self, itens):
        for item in itens:
            self._escritor.writerow({coluna: getattr(item, coluna) for coluna in COLUNAS_PLANILHA})
            # "getattr(item, coluna)" pega o valor do campo do Item cujo
            # NOME é igual ao texto guardado em "coluna" -- um jeito de
            # ler um campo do objeto sem precisar escrever "item.NOME" pra
            # cada uma das colunas na mão, uma por uma
        self._sincronizar()

    def _sincronizar(self):
        self._arquivo.flush()
        os.fsync(self._arquivo.fileno())

    def fechar(self):
        self._arquivo.close()

    def __enter__(self):
        return self

    def __exit__(self, tipo_erro, erro, traceback):
        self.fechar()
