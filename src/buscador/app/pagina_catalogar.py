# -*- coding: utf-8 -*-
"""
Tela "Catalogar" -- fase futura (Fase 4 do CLAUDE.md). Por enquanto só
explica o que vai existir; nada aqui funciona ainda, e a tela diz isso.
"""
import streamlit as st


def mostrar() -> None:
    st.title("Catalogar (em breve)")
    st.info("Esta tela é de uma **fase futura (Fase 4)**. Ainda não funciona: abaixo, só a ideia.")

    st.markdown(
        "O aplicativo vai olhar **dentro** de cada PDF baixado para sugerir **autor, título e tema**, "
        "e separar os arquivos em pastas por isso:"
    )
    st.markdown(
        "- ler o texto e as informações que já vêm dentro do PDF (grátis);\n"
        "- nos PDFs escaneados (só imagem), reconhecer o texto com **OCR** (OCRmyPDF + Tesseract);\n"
        "- conferir em **catálogos on-line gratuitos** (Open Library, Google Books, Calibre);\n"
        "- nos fóruns, usar também o texto da conversa em volta do link."
    )
    st.warning(
        "Tudo o que for sugerido automaticamente vai aparecer marcado como **palpite — confirme**. "
        "Uma pessoa sempre confirma ou corrige antes de valer."
    )

    with st.container(border=True):
        st.caption("Como vai ser um item esperando confirmação (exemplo, não funciona):")
        st.markdown("**arquivo_exemplo_0001.pdf** · `palpite — confirme`")
        col1, col2, col3 = st.columns(3)
        col1.text_input("Título sugerido", disabled=True, key="cat_titulo")
        col2.text_input("Autor sugerido", disabled=True, key="cat_autor")
        col3.text_input("Tema sugerido", disabled=True, key="cat_tema")
        b1, b2, b3, _ = st.columns([1, 1, 2, 2])
        b1.button("Confirmar", disabled=True, key="cat_confirmar")
        b2.button("Corrigir", disabled=True, key="cat_corrigir")
        b3.button("Mandar pro Claude Pro", disabled=True, key="cat_claude",
                  help="Opcional: manda o item para o seu Claude Pro dar um palpite melhor. Fase futura.")
