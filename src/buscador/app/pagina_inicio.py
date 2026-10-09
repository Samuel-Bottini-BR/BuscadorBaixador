# -*- coding: utf-8 -*-
"""
Tela "Início" do aplicativo: um resumo com números de verdade, tirados do
que já existe no computador (lista de sites, planilhas em saidas/,
arquivos baixados do Telegram, tarefas do motor de jobs).

Nada aqui muda arquivo nenhum -- a tela só olha.
"""
from pathlib import Path

import pandas as pd  # pandas: biblioteca de tabelas; o Streamlit desenha um DataFrame (tabela do pandas) com st.dataframe
import streamlit as st

from buscador.core import config_sites, jobs_registro, resumo_saidas, sites_cadastrados


# st.cache_data guarda o resultado da função por 60 segundos: se a tela for
# redesenhada nesse meio-tempo (cada clique redesenha), o app NÃO conta de
# novo os milhares de arquivos do Telegram -- reaproveita a conta anterior.
# O caminho entra como argumento para o cache saber "de qual pasta" é a conta.
@st.cache_data(ttl=60, show_spinner="Contando os arquivos baixados...")
def _contar_telegram(pasta: str) -> tuple[int, int]:
    return resumo_saidas.contar_arquivos_telegram(Path(pasta))


@st.cache_data(ttl=60)
def _planilhas(pasta: str) -> list[resumo_saidas.Planilha]:
    return resumo_saidas.listar_planilhas(Path(pasta))


def _jobs():
    """Lê o registro do motor de jobs. Devolve (lista, mensagem_de_erro)."""
    try:
        return jobs_registro.carregar_registro(jobs_registro.CAMINHO_PADRAO), None
    except Exception as erro:  # registro com defeito não pode derrubar a tela inteira
        return [], str(erro)


def mostrar() -> None:
    st.title("Início")
    st.caption("Resumo do que o aplicativo já encontrou e baixou. Use o menu ao lado para cada etapa.")

    saidas = resumo_saidas.pasta_saidas()
    try:
        sites = sites_cadastrados.carregar_sites()
        erro_sites = None
    except ValueError as erro:
        sites, erro_sites = [], str(erro)
    planilhas = _planilhas(str(saidas))
    qtd_telegram, bytes_telegram = _contar_telegram(str(saidas / "telegram"))
    jobs, erro_jobs = _jobs()
    rodando = [j for j in jobs if j.estado == "rodando"]

    # --- Os 4 números do topo ---------------------------------------------
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Sites cadastrados", len(sites),
                help="Os sites da tela Sites (o motor só trabalha em sites cadastrados).")
    col1.caption(" · ".join(s.get("nome", "?") for s in sites[:3]) or "nenhum")
    col2.metric("Planilhas geradas", len(planilhas), help="Arquivos .xlsx dentro da pasta saidas/.")
    col2.caption(f"a mais nova: {planilhas[0].modificada_em:%d/%m %H:%M}" if planilhas else "nenhuma ainda")
    col3.metric("Arquivos baixados", f"{qtd_telegram:,}".replace(",", "."),
                help="Arquivos já baixados do Telegram (pastas saidas/telegram/.../arquivos).")
    col3.caption(f"{resumo_saidas.formatar_tamanho(bytes_telegram)} (Telegram)")
    col4.metric("Tarefas rodando agora", len(rodando),
                help="Tarefas longas do motor de jobs (jobs.bat) que estão rodando.")
    col4.caption(f"{len(jobs)} no registro" if jobs else "nenhuma no registro")

    # --- Últimas atividades ----------------------------------------------
    st.subheader("Últimas atividades")
    if planilhas:
        tabela = pd.DataFrame([
            {
                "Quando": p.modificada_em.strftime("%d/%m/%Y %H:%M"),
                "Planilha": p.caminho.name,
                "Pasta": str(p.caminho.parent.relative_to(saidas)) if p.caminho.is_relative_to(saidas) else str(p.caminho.parent),
                "Tamanho": resumo_saidas.formatar_tamanho(p.tamanho_bytes),
            }
            for p in planilhas[:8]
        ])
        st.dataframe(tabela, hide_index=True, width="stretch")
    else:
        st.caption("Nenhuma planilha em saidas/ ainda. Comece pela tela Mapear.")

    # --- Precisa de você --------------------------------------------------
    st.subheader("Precisa de você")
    avisos = 0
    if erro_sites:
        st.error(f"Lista de sites com defeito: {erro_sites}")
        avisos += 1
    if erro_jobs:
        st.warning(f"Não deu para ler o registro de tarefas (jobs): {erro_jobs}")
        avisos += 1
    if not config_sites.CAMINHO_PADRAO.exists():
        st.info(
            "Ainda não existe o arquivo **buscador.local.cfg** (na pasta do projeto). Ele só é "
            "necessário para o Telegram e para sites com chave de API. Para criar: copie "
            "`buscador.local.cfg.exemplo` para `buscador.local.cfg` e preencha."
        )
        avisos += 1
    for site in sites:
        if site.get("url_login"):
            st.info(
                f"**{site.get('nome')}** pode pedir login para baixar alguns itens. "
                "Quando for preciso, abra **Sites** e clique em \"Fazer login\"."
            )
            avisos += 1
    com_erro = [j for j in jobs if j.estado == "erro"]
    for job in com_erro[-3:]:  # só as 3 últimas, para a tela não virar uma lista enorme
        st.warning(f"A tarefa **{job.id}** ({job.modulo}) terminou com erro. Veja o registro: `{job.log_path}`")
        avisos += 1
    if avisos == 0:
        st.success("Nada pendente por enquanto.")
