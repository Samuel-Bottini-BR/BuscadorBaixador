# -*- coding: utf-8 -*-
import time

from buscador.core import jobs_notificacoes


def test_avisar_windows_chama_notify_com_titulo_e_mensagem(monkeypatch):
    chamadas = []
    monkeypatch.setattr(
        jobs_notificacoes, "notify",
        lambda titulo, mensagem: chamadas.append((titulo, mensagem)),
    )

    jobs_notificacoes.avisar_windows("Job travado", "Precisa fazer login no Internet Archive")

    assert chamadas == [("Job travado", "Precisa fazer login no Internet Archive")]


def test_avisar_windows_nao_fica_esperando_se_o_aviso_bloquear(monkeypatch):
    # o notify da biblioteca pode ficar esperando o usuario fechar o balao;
    # um job nao pode ficar pendurado por causa disso
    monkeypatch.setattr(jobs_notificacoes, "notify", lambda titulo, mensagem: time.sleep(5))
    monkeypatch.setattr(jobs_notificacoes, "ESPERA_MAXIMA_SEGUNDOS", 0.2)

    inicio = time.time()
    jobs_notificacoes.avisar_windows("Job travado", "qualquer mensagem")

    assert time.time() - inicio < 2


def test_avisar_windows_nao_propaga_erro_do_windows(monkeypatch):
    def notify_que_falha(titulo, mensagem):
        raise RuntimeError("sem suporte a notificacao")
    monkeypatch.setattr(jobs_notificacoes, "notify", notify_que_falha)

    jobs_notificacoes.avisar_windows("Job travado", "qualquer mensagem")  # nao pode levantar
