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
import streamlit as st

from buscador.app import (
    pagina_baixar,
    pagina_catalogar,
    pagina_inicio,
    pagina_mapear,
    pagina_sites,
    pagina_telegram,
)

st.set_page_config(page_title="Buscador e Baixador", page_icon="📚", layout="wide")

with st.sidebar:
    st.markdown("### Buscador e Baixador")
    st.caption("Instituto São Bento · acervo digital")

menu = st.navigation([
    st.Page(pagina_inicio.mostrar, title="Início", icon="🏠", url_path="inicio", default=True),
    st.Page(pagina_sites.mostrar, title="Sites", icon="🌐", url_path="sites"),
    st.Page(pagina_mapear.mostrar, title="Mapear", icon="🗺️", url_path="mapear"),
    st.Page(pagina_baixar.mostrar, title="Baixar", icon="⬇️", url_path="baixar"),
    st.Page(pagina_telegram.mostrar, title="Telegram", icon="✈️", url_path="telegram"),
    st.Page(pagina_catalogar.mostrar, title="Catalogar (em breve)", icon="🏷️", url_path="catalogar"),
])
menu.run()
