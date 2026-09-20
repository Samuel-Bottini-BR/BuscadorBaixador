# -*- coding: utf-8 -*-
import pytest


@pytest.fixture(autouse=True)
def _sem_aviso_real_do_windows(monkeypatch):
    """Nenhum teste deve abrir um aviso de verdade no Windows do Samuel --
    os testes que querem checar o aviso trocam o notify por conta propria
    (como test_jobs_notificacoes.py faz)."""
    monkeypatch.setattr("buscador.core.jobs_notificacoes.notify", lambda titulo, mensagem: None)
