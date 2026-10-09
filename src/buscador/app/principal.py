# -*- coding: utf-8 -*-
"""
Porta de entrada do aplicativo com tela (Streamlit).

Streamlit é uma biblioteca que transforma um script Python numa página que
abre no navegador: cada st.algo(...) desenha um pedaço da tela. Quando você
clica num botão, o Streamlit roda o script de novo, de cima para baixo -- por
isso o que precisa ser "lembrado" entre cliques fica em st.session_state.

Cada tela mora no seu próprio arquivo (pagina_*.py) e tem uma função
mostrar(). Este arquivo só monta o menu lateral e chama a tela escolhida.

Para abrir: app.bat (ou: python -m streamlit run src/buscador/app/principal.py)
"""
import functools

import streamlit as st

from buscador.app import (
    pagina_baixar,
    pagina_catalogar,
    pagina_inicio,
    pagina_mapear,
    pagina_sites,
    pagina_telegram,
)

from buscador.core.registro_erros import ARQUIVO_ERROS, registrar_erro

st.set_page_config(page_title="Buscador e Baixador", page_icon="📚", layout="wide")


def com_registro_de_erros(nome_tela, mostrar):
    """Embrulha uma tela: se der qualquer erro inesperado, ele vai para o
    caderno logs/erros.log (o Claude lê de lá e corrige) e a tela mostra um
    aviso amigável em vez de um monte de texto vermelho."""
    @functools.wraps(mostrar)
    def mostrar_protegido():
        try:
            mostrar()
        except Exception as erro:  # noqa: BLE001 -- de propósito: registrar QUALQUER erro
            # st.rerun()/st.stop() funcionam lançando exceções especiais do
            # Streamlit -- essas não são erro, deixamos passar
            if type(erro).__module__.startswith("streamlit"):
                raise
            registrar_erro(f"tela {nome_tela}", erro)
            st.error(
                f"Deu um erro nesta tela. Já ficou anotado em {ARQUIVO_ERROS} -- "
                "é só avisar o Claude que ele lê de lá e corrige."
            )
            with st.expander("Detalhes técnicos"):
                st.exception(erro)
    return mostrar_protegido

with st.sidebar:
    st.markdown("### Buscador e Baixador")
    st.caption("Instituto São Bento · acervo digital")
    st.caption("Se algo der errado, fica anotado em logs\\erros.log.")

menu = st.navigation([
    st.Page(com_registro_de_erros("Início", pagina_inicio.mostrar), title="Início", icon="🏠", default=True),
    st.Page(com_registro_de_erros("Sites", pagina_sites.mostrar), title="Sites", icon="🌐", url_path="sites"),
    st.Page(com_registro_de_erros("Mapear", pagina_mapear.mostrar), title="Mapear", icon="🗺️", url_path="mapear"),
    st.Page(com_registro_de_erros("Baixar", pagina_baixar.mostrar), title="Baixar", icon="⬇️", url_path="baixar"),
    st.Page(com_registro_de_erros("Telegram", pagina_telegram.mostrar), title="Telegram", icon="✈️", url_path="telegram"),
    st.Page(com_registro_de_erros("Catalogar (em breve)", pagina_catalogar.mostrar), title="Catalogar (em breve)", icon="🏷️", url_path="catalogar"),
])
menu.run()
