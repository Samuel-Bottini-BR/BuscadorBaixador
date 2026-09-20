# -*- coding: utf-8 -*-
# src/buscador/core/jobs_executor.py
"""
Ponto de entrada do processo "executor" de um job -- lancado por
core/jobs_motor.py::iniciar_job, nunca digitado na mao. Roda o comando de
verdade do job e atualiza o registro quando ele termina:
"python -m buscador.core.jobs_executor <id_do_job> <caminho_do_registro>".
"""
import sys
import traceback
from pathlib import Path

from buscador.core.jobs_motor import executar_job
from buscador.core.jobs_registro import atualizar_job, carregar_registro


def _deixar_rastro_da_falha(id_job: str, caminho_registro: Path, texto_do_erro: str) -> None:
    """Melhor esforco, e NUNCA levanta: tenta (1) gravar o traceback no log do
    job e (2) marcar o job como 'erro' no registro. Cada passo e independente --
    se um falhar (o registro esta ilegivel, o disco cheio...), o outro ainda
    roda. Sem isso o executor morria em silencio absoluto (o stderr dele vai pro
    nada) e o job ficava 'interrompido' sem ninguem saber por que."""
    try:
        job = next((j for j in carregar_registro(caminho_registro) if j.id == id_job), None)
        if job is not None:
            caminho_log = Path(job.log_path)
            caminho_log.parent.mkdir(parents=True, exist_ok=True)
            # recria a pasta do log se ela foi apagada: essa e uma das causas
            # possiveis do erro, e sem a pasta o traceback nao teria onde ficar
            with open(caminho_log, "a", encoding="utf-8") as arquivo_log:
                # "a" (acrescentar), nunca "w": o comando pode ja ter escrito
                # horas de saida no log, e ela nao pode ser apagada
                arquivo_log.write(f"\n[executor] O executor do job falhou antes de terminar:\n{texto_do_erro}")
    except Exception:
        pass
    try:
        atualizar_job(id_job, caminho_registro, estado="erro")
    except Exception:
        pass


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    id_job, caminho_registro = argv[0], Path(argv[1])
    try:
        executar_job(id_job, caminho_registro)
    except Exception:
        # Qualquer falha do proprio executor (pasta de log apagada, o python
        # sumiu, a trava do registro estourou no atualizar_job FINAL depois de
        # uma coleta de horas que terminou bem...) vira rastro no log + estado
        # 'erro', em vez de morte silenciosa.
        _deixar_rastro_da_falha(id_job, caminho_registro, traceback.format_exc())
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
