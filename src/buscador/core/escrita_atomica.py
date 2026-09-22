# -*- coding: utf-8 -*-
"""
Escrita atômica de dados JSON em disco.

Generaliza o padrão de `checkpoint.py::salvar`: escreve em um arquivo
temporário, depois usa `os.replace` para trocar atomicamente pelo arquivo
definitivo. Se o Windows negar a troca (PermissionError enquanto outro
processo tem o arquivo aberto), tenta novamente algumas vezes antes de
desistir.

Este módulo é para reutilização por novos módulos que precisem de escrita
segura e atômica de dados JSON, sem deixar arquivo corrompido se o
programa morrer no meio da gravação.
"""
import json
import os
import time
from pathlib import Path
from typing import Any


def salvar_json_atomico(dados: Any, caminho: Path, tentativas_windows: int = 10,
                         espera_entre_tentativas: float = 0.05) -> None:
    """
    Salva dados serializáveis em JSON de forma atômica.

    Escreve em um arquivo temporário (com sufixo .tmp) e depois usa
    `os.replace` para trocar atomicamente pelo arquivo definitivo. Assim,
    se o programa morrer no meio da gravação, o arquivo anterior (ainda
    válido) nunca fica corrompido.

    No Windows, enquanto outro processo tem o arquivo aberto, `os.replace`
    pode falhar com PermissionError. Esta função tenta novamente várias
    vezes antes de desistir, evitando que uma operação longa falhe por
    um instante de azar.

    Argumentos:
        dados: dados serializáveis (dict, list, etc.) para salvar como JSON.
        caminho: caminho (Path) onde salvar o arquivo definitivo.
        tentativas_windows: quantas vezes tentar fazer o `os.replace` se falhar
                           com PermissionError (padrão: 10).
        espera_entre_tentativas: segundos a esperar entre tentativas
                                (padrão: 0.05).

    Levanta:
        PermissionError: se todas as `tentativas_windows` falharem.
    """
    caminho = Path(caminho)  # garante que é um Path, não uma string
    caminho.parent.mkdir(parents=True, exist_ok=True)

    # arquivo temporário fica ao lado do definitivo
    caminho_tmp = caminho.with_suffix(caminho.suffix + ".tmp")

    # escreve no arquivo temporário primeiro
    caminho_tmp.write_text(
        json.dumps(dados, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    # tenta fazer o replace atômico, retentando em caso de PermissionError
    for tentativa in range(tentativas_windows):
        try:
            os.replace(caminho_tmp, caminho)
            break
        except PermissionError:
            if tentativa == tentativas_windows - 1:
                raise  # todas as tentativas falharam, deixa o erro subir
            time.sleep(espera_entre_tentativas)
