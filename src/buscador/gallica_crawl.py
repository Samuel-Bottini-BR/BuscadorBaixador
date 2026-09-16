# -*- coding: utf-8 -*-
"""
Ponto de entrada de linha de comando (o "comando" que você digita no
terminal) da Etapa 1: coleta bruta (sem verificar link nem traduzir ainda
-- isso é a Etapa 2, gallica_enriquecer.py) de uma consulta INTEIRA da
Gallica (ex.: todos os livros do catálogo, centenas de milhares). É
retomável entre execuções -- pode ser interrompido (fechar o terminal,
Ctrl+C, o computador desligar) e rodado de novo a qualquer momento que ele
continua de onde parou, graças ao checkpoint. Ver core/coleta_gallica.py
pra entender o motor por trás disso.
"""
import argparse
import shutil  # biblioteca padrão do Python com funções de arquivo/pasta "de alto nível", como apagar uma pasta inteira
from pathlib import Path

from buscador.core.acao_humana import AcaoHumanaNecessaria, formatar_aviso
from buscador.core.checkpoint import ConsultaDivergenteError, slug_consulta
from buscador.core.coleta_gallica import COOLDOWN_429_PADRAO_SEGUNDOS, coletar

SAIDAS = Path(__file__).resolve().parent.parent.parent / "saidas"
DIRETORIO_COLETAS = SAIDAS / "gallica_crawl"
# Cada consulta diferente ganha sua própria subpasta dentro de
# "saidas/gallica_crawl/", com o checkpoint e o CSV dela.


def _diretorio_do_job(consulta, job_forcado=None):
    """Decide o nome da pasta onde o progresso dessa coleta vai ficar.
    "Job" é o termo comum pra "uma tarefa/trabalho que o programa está
    rodando". Se o Samuel não escolher um nome (--job), o programa gera um
    automaticamente a partir da própria consulta (ver core/checkpoint.py,
    slug_consulta)."""
    nome = job_forcado or slug_consulta(consulta)
    return DIRETORIO_COLETAS / nome


def _mostrar_progresso(checkpoint):
    """Imprime uma linha de status no terminal -- passada pro motor
    (core/coleta_gallica.py) como a função que ele deve chamar toda vez
    que uma página nova for salva, pra o Samuel acompanhar o andamento."""
    if checkpoint.total_registros_api:
        percentual = 100 * checkpoint.itens_gravados / checkpoint.total_registros_api
        print(f"  {checkpoint.itens_gravados}/{checkpoint.total_registros_api} itens ({percentual:.1f}%)")
    else:
        # ainda não sabemos o total (só descobrimos depois da primeira
        # página) -- mostra só a contagem, sem porcentagem
        print(f"  {checkpoint.itens_gravados} itens coletados")


def _confirmar_reinicio(diretorio_job):
    """Usada quando o Samuel pede --reiniciar: pergunta de verdade antes
    de apagar qualquer progresso já salvo, pra evitar apagar sem querer
    horas (ou dias) de coleta."""
    if not diretorio_job.exists():
        return True  # não tem nada salvo ainda -- não precisa nem perguntar
    resposta = input(
        f"Isso vai apagar todo o progresso salvo em '{diretorio_job}' e comecar do zero. "
        "Tem certeza? (digite 'sim' para confirmar): "
    )
    return resposta.strip().lower() == "sim"
    # só considera confirmado se a resposta for exatamente "sim" (sem
    # espaço, sem maiúscula) -- qualquer outra coisa cancela por segurança


def main(argv=None):
    """Função principal deste arquivo -- roda quando você digita
    "python -m buscador.gallica_crawl <consulta>" no terminal."""
    parser = argparse.ArgumentParser(
        description="Etapa 1: coleta bruta de uma consulta inteira da Gallica (retomavel)."
    )
    parser.add_argument("consulta", help='Consulta CQL da Gallica (ex.: dc.type all "monographie")')
    parser.add_argument("--job", help="Nome da pasta de progresso (padrao: gerado a partir da consulta)")
    parser.add_argument("--max-resultados", type=int, default=10_000_000,
                         help="Teto de registros a buscar (padrao: bem acima do catalogo inteiro)")
    parser.add_argument("--tamanho-pagina", type=int, default=50,
                         help="Itens por pagina (maximo 50, limite da BnF)")
    parser.add_argument("--cooldown-429-minutos", type=float, default=COOLDOWN_429_PADRAO_SEGUNDOS / 60,
                         help="Minutos de pausa quando a Gallica bloquear por excesso de requisicoes")
    parser.add_argument("--reiniciar", action="store_true",
                         help="Apaga o progresso salvo desse job e comeca do zero (pede confirmacao)")
    # "action='store_true'" quer dizer: essa opção não recebe valor
    # nenhum, só liga (True) se o --reiniciar for digitado, senão fica False
    args = parser.parse_args(argv)

    diretorio_job = _diretorio_do_job(args.consulta, args.job)

    if args.reiniciar:
        if not _confirmar_reinicio(diretorio_job):
            print("Cancelado -- nada foi apagado.")
            return 1
        shutil.rmtree(diretorio_job, ignore_errors=True)
        # apaga a pasta inteira (e tudo dentro dela); "ignore_errors=True"
        # evita erro se, por algum motivo, a pasta já não existir mais

    try:
        checkpoint = coletar(
            args.consulta, diretorio_job, tamanho_pagina=args.tamanho_pagina,
            max_registros_alvo=args.max_resultados,
            cooldown_429_segundos=args.cooldown_429_minutos * 60,  # converte minutos (digitados) pra segundos (usado internamente)
            progresso_fct=_mostrar_progresso,
        )
    except ConsultaDivergenteError as erro:
        # a consulta pedida agora é diferente da que estava salva nesse
        # job -- ver core/checkpoint.py pra entender essa trava de segurança
        print(f"Não deu para continuar: {erro}")
        return 1
    except AcaoHumanaNecessaria as erro:
        # sinal especial (ver core/acao_humana.py): precisa que o Samuel
        # faça algo antes de continuar. Como o progresso já está salvo em
        # disco (checkpoint + CSV), não se perde nada -- só avisa onde
        # está, pra ele rodar o mesmo comando de novo depois de resolver.
        print(formatar_aviso(erro))
        print(f"O progresso ja salvo continua em {diretorio_job} -- rode este comando de novo depois de resolver.")
        return 1

    print(f"Coleta concluída: {checkpoint.itens_gravados} itens salvos em {diretorio_job / 'itens.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
