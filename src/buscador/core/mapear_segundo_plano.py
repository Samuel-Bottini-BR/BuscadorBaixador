# -*- coding: utf-8 -*-
"""
Roda o mapeamento (o mesmo comando do terminal, "python -m buscador.cli")
em SEGUNDO PLANO, para a tela "Mapear" não ficar congelada enquanto o motor
trabalha -- mapear 50 itens da Gallica leva alguns minutos, porque cada
link é testado com calma.

Como funciona, em palavras simples:
- "subprocess.Popen" abre um outro programa Python, separado do aplicativo,
  e NÃO espera ele terminar (diferente de subprocess.run, que espera).
- Tudo o que esse programa escreveria no terminal vai para um arquivo de
  log (registro) em saidas/mapeamentos/. A tela lê esse arquivo para
  mostrar o andamento.
- Uma "ficha" (.json) ao lado do log guarda o que foi pedido e onde a
  planilha vai ficar. Assim, mesmo se você recarregar a página do
  navegador, a tela continua sabendo qual foi o último mapeamento.
"""
import datetime
import json
import os
import re
import subprocess
import sys
from pathlib import Path

from buscador.core import resumo_saidas
from buscador.core.escrita_atomica import salvar_json_atomico

# Raiz do projeto (onde fica o CLAUDE.md) -- o comando roda a partir dela.
RAIZ = Path(__file__).resolve().parent.parent.parent.parent

# Os processos que ESTE aplicativo abriu, guardados na memória enquanto o
# aplicativo está aberto: id do mapeamento -> objeto Popen. Com ele dá para
# perguntar "já terminou?" (poll). Se o aplicativo for fechado e aberto de
# novo, esta lista começa vazia, e a situação é deduzida pelo log.
_PROCESSOS: dict[str, subprocess.Popen] = {}

FRASE_SUCESSO = "Planilha salva em:"
# Frases que o cli.py escreve quando para sem gerar a planilha:
# erro técnico (Traceback), erro "normal" e pedido de ajuda humana
# (ver core/acao_humana.py::formatar_aviso).
FRASES_ERRO = ("Traceback", "Não deu para continuar", "Preciso da sua ajuda")


def pasta_mapeamentos() -> Path:
    return resumo_saidas.pasta_saidas() / "mapeamentos"


def montar_consulta(adapter: str, texto: str) -> str:
    """Transforma o que a pessoa digitou na entrada que o motor espera.
    Na Gallica, um nome simples ("Clavius") vira a consulta CQL
    gallica all "Clavius"; quem já sabe CQL (ou cola uma URL do SRU) pode
    digitar a consulta completa, e ela passa sem mudança."""
    texto = (texto or "").strip()
    if not texto:
        raise ValueError("Digite o que procurar (ou o endereço da página).")
    if adapter == "gallica":
        parece_cql = texto.startswith("http") or re.search(r"\s(all|any|adj)\s|=", texto)
        if not parece_cql:
            return f'gallica all "{texto}"'
    if adapter == "phpbb" and not texto.startswith("http"):
        raise ValueError("Para o fórum, cole o endereço (URL) de um tópico, começando com https://")
    return texto


def nome_da_saida(adapter: str, agora: datetime.datetime | None = None) -> str:
    """Nome da planilha: <adapter>_<data>_<hora>.xlsx -- a hora no nome
    evita que dois mapeamentos do mesmo dia escrevam um por cima do outro."""
    agora = agora or datetime.datetime.now()
    return f"{adapter}_{agora:%Y-%m-%d_%H%M%S}.xlsx"


def montar_comando(adapter: str, entrada: str, caminho_saida: Path, python: str | None = None) -> list[str]:
    """A lista de "palavras" do comando, exatamente como seria digitado no
    terminal: python -m buscador.cli <entrada> --adapter X --saida Y."""
    return [python or sys.executable, "-m", "buscador.cli", entrada,
            "--adapter", adapter, "--saida", str(caminho_saida)]


def iniciar_mapeamento(adapter: str, entrada: str, nome_site: str = "", abrir_processo=subprocess.Popen) -> dict:
    """Abre o mapeamento em segundo plano e devolve a ficha dele.
    "abrir_processo" existe só para os testes trocarem o Popen de verdade
    por um falso (sem rodar nada)."""
    agora = datetime.datetime.now()
    pasta = pasta_mapeamentos()
    pasta.mkdir(parents=True, exist_ok=True)
    id_mapeamento = f"{adapter}_{agora:%Y-%m-%d_%H%M%S}"
    caminho_saida = resumo_saidas.pasta_saidas() / nome_da_saida(adapter, agora)
    caminho_log = pasta / f"{id_mapeamento}.log"
    comando = montar_comando(adapter, entrada, caminho_saida)

    ambiente = dict(os.environ)
    ambiente["PYTHONUNBUFFERED"] = "1"  # escreve no log na hora, sem guardar em "buffer"
    ambiente["PYTHONIOENCODING"] = "utf-8"  # acentos certos no log, inclusive no Windows
    # No Windows, sem isto apareceria uma janela preta de terminal.
    sem_janela = getattr(subprocess, "CREATE_NO_WINDOW", 0)

    with open(caminho_log, "w", encoding="utf-8") as log:
        log.write(f"Comando: {' '.join(comando)}\n")
        log.flush()
        processo = abrir_processo(
            comando, stdout=log, stderr=subprocess.STDOUT, cwd=str(RAIZ),
            env=ambiente, creationflags=sem_janela,
        )
    # (o "with" fecha o arquivo só do lado do aplicativo; o processo filho
    # tem a sua própria cópia aberta e continua escrevendo nela)

    _PROCESSOS[id_mapeamento] = processo
    ficha = {
        "id": id_mapeamento, "site": nome_site, "adapter": adapter, "entrada": entrada,
        "saida": str(caminho_saida), "log": str(caminho_log),
        "iniciado_em": agora.isoformat(timespec="seconds"), "pid": getattr(processo, "pid", None),
    }
    salvar_json_atomico(ficha, pasta / f"{id_mapeamento}.json")
    return ficha


def ultimo_mapeamento() -> dict | None:
    """A ficha do mapeamento mais recente (ou None se nunca rodou nenhum)."""
    fichas = sorted(pasta_mapeamentos().glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    for caminho in fichas:
        try:
            return json.loads(caminho.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
    return None


def ler_fim_do_log(ficha: dict, linhas: int = 15) -> str:
    """As últimas linhas do log (é o "andamento" que a tela mostra)."""
    try:
        texto = Path(ficha["log"]).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    return "\n".join(texto.splitlines()[-linhas:])


def situacao(ficha: dict) -> str:
    """Diz em que pé está: "rodando", "concluido", "erro" ou "desconhecido".
    Primeiro pergunta ao processo (se este aplicativo o abriu); se não
    der, deduz pelo log e pela planilha no disco."""
    processo = _PROCESSOS.get(ficha.get("id"))
    log = ler_fim_do_log(ficha, linhas=40)
    planilha_existe = Path(ficha.get("saida", "")).is_file()
    if processo is not None:
        codigo = processo.poll()  # None = ainda rodando; número = terminou
        if codigo is None:
            return "rodando"
        return "concluido" if codigo == 0 and planilha_existe else "erro"
    if FRASE_SUCESSO in log and planilha_existe:
        return "concluido"
    if any(frase in log for frase in FRASES_ERRO):
        return "erro"
    return "desconhecido"
