# -*- coding: utf-8 -*-
import email.utils

from buscador.core import relogio
from buscador.core.registro_erros import registrar_erro


def test_registra_erro_com_traceback(tmp_path):
    arquivo = tmp_path / "logs" / "erros.log"
    try:
        1 / 0
    except ZeroDivisionError as e:
        registrar_erro("teste", e, detalhe="linha extra", arquivo=arquivo)
    texto = arquivo.read_text(encoding="utf-8")
    assert "| teste |" in texto
    assert "ZeroDivisionError" in texto
    assert "linha extra" in texto


def test_caderno_grande_vira_ponto_1(tmp_path, monkeypatch):
    from buscador.core import registro_erros
    monkeypatch.setattr(registro_erros, "TAMANHO_MAXIMO", 10)
    arquivo = tmp_path / "erros.log"
    arquivo.write_text("x" * 50, encoding="utf-8")
    registrar_erro("novo", detalhe="oi", arquivo=arquivo)
    assert (tmp_path / "erros.log.1").exists()
    assert "novo" in arquivo.read_text(encoding="utf-8")


class ClienteHora:
    def __init__(self, diferenca_servidor):
        self.diferenca = diferenca_servidor

    def head(self, site):
        import time
        hora = time.time() + self.diferenca
        return type("R", (), {"headers": {"date": email.utils.formatdate(hora, usegmt=True)}})()


def test_detecta_relogio_atrasado():
    dif = relogio.diferenca_do_relogio(cliente=ClienteHora(+47))  # servidor 47 s à frente
    assert -49 < dif < -45
    assert not relogio.relogio_ok(dif)
    assert "atrasado" in relogio.descrever(dif)


def test_relogio_certo():
    dif = relogio.diferenca_do_relogio(cliente=ClienteHora(0))
    assert relogio.relogio_ok(dif)


def test_sem_internet_nao_trava():
    import httpx

    class SemRede:
        def head(self, site):
            raise httpx.ConnectError("sem rede")

    assert relogio.diferenca_do_relogio(cliente=SemRede()) is None
    assert relogio.relogio_ok(None)
