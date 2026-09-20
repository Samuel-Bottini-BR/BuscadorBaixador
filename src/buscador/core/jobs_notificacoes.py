# -*- coding: utf-8 -*-
"""
Dispara uma notificacao nativa do Windows (o balao que aparece no canto da
tela) quando um job precisa da atencao do Samuel. Usa win11toast, que nao
precisa de nenhuma configuracao especial nem permissao de administrador.
"""
import threading

try:
    from win11toast import notify
except Exception:
    # biblioteca ausente ou incompativel com este Windows: o aviso vira um "nao
    # faz nada" e o resto do programa (cli, gallica_crawl...) continua funcionando
    # -- o aviso e so uma cortesia
    notify = None

ESPERA_MAXIMA_SEGUNDOS = 3.0


def _mostrar(titulo: str, mensagem: str) -> None:
    if notify is None:
        return
    try:
        notify(titulo, mensagem)
    except Exception:
        # o aviso e so uma cortesia: se o Windows nao conseguir mostrar
        # (sem suporte, erro interno), o job nao pode quebrar por causa disso
        pass


def avisar_windows(titulo: str, mensagem: str) -> None:
    """Mostra uma notificacao do Windows com o titulo e a mensagem dados.
    Chamado sempre que um job entra num estado que precisa da atencao do
    Samuel (hoje: login/CAPTCHA/chave de API -- ver core/acao_humana.py).
    Roda numa thread com tempo maximo de espera: dependendo da versao, o
    notify() da biblioteca pode ficar esperando o usuario fechar o balao, e
    um job nao pode ficar pendurado indefinidamente por causa disso."""
    thread = threading.Thread(target=_mostrar, args=(titulo, mensagem), daemon=True)
    thread.start()
    thread.join(timeout=ESPERA_MAXIMA_SEGUNDOS)
