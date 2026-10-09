# -*- coding: utf-8 -*-
"""
Caderno de erros do aplicativo: logs/erros.log, na raiz do projeto.

Qualquer erro inesperado (na tela, num comando de terminal, num download em
segundo plano) é escrito aqui com data, hora, onde aconteceu e o "traceback"
(a lista de onde o Python estava quando deu o erro). Assim o Samuel não
precisa copiar nada: o Claude lê esse arquivo direto do HD e corrige o código.

O arquivo nunca vai pro GitHub (logs/ está no .gitignore) -- pode conter
nomes de arquivos e pastas do PC.
"""
import datetime
import platform
import sys
import traceback
from pathlib import Path

from buscador.core.config_sites import CAMINHO_PADRAO

PASTA_LOGS = CAMINHO_PADRAO.parent / "logs"
ARQUIVO_ERROS = PASTA_LOGS / "erros.log"
TAMANHO_MAXIMO = 5 * 1024 * 1024  # 5 MB: passou disso, o antigo vira erros.log.1


def _girar_se_grande(arquivo: Path) -> None:
    """Se o caderno ficou grande demais, guarda o atual como .1 e começa um novo."""
    try:
        if arquivo.exists() and arquivo.stat().st_size > TAMANHO_MAXIMO:
            antigo = arquivo.with_name(arquivo.name + ".1")
            antigo.unlink(missing_ok=True)
            arquivo.rename(antigo)
    except OSError:
        pass


def registrar_erro(onde: str, erro: BaseException | None = None, detalhe: str = "",
                   arquivo: Path | None = None) -> Path:
    """Escreve um erro no caderno e devolve o caminho do arquivo.

    onde: em que parte do app (ex.: "tela Telegram", "telegram_cli listar").
    erro: a exceção (se houver) -- o traceback completo vai junto.
    detalhe: texto livre extra (ex.: as últimas linhas do log de um download).
    Nunca levanta erro: se nem isso der para gravar, desiste em silêncio."""
    arquivo = arquivo or ARQUIVO_ERROS
    agora = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    partes = [f"===== {agora} | {onde} | Python {platform.python_version()} | {platform.platform()}"]
    if erro is not None:
        partes.append("".join(traceback.format_exception(type(erro), erro, erro.__traceback__)).rstrip())
    if detalhe:
        partes.append(detalhe.rstrip())
    try:
        arquivo.parent.mkdir(parents=True, exist_ok=True)
        _girar_se_grande(arquivo)
        with open(arquivo, "a", encoding="utf-8") as f:
            f.write("\n".join(partes) + "\n\n")
    except OSError:
        pass
    return arquivo


def instalar_em_comandos(onde: str) -> None:
    """Para programas de terminal (telegram_cli etc.): qualquer erro não
    tratado também vai para o caderno, além de aparecer na tela."""
    anterior = sys.excepthook

    def gancho(tipo, valor, tb):
        if not issubclass(tipo, KeyboardInterrupt):
            registrar_erro(onde, valor)
        anterior(tipo, valor, tb)

    sys.excepthook = gancho
