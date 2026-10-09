# -*- coding: utf-8 -*-
"""
Tela "Baixar" (Fase 2 do projeto). Ainda não existe um "baixador" geral,
que pegue os itens aprovados de qualquer planilha e baixe -- então esta
tela é honesta: mostra o que existe de verdade hoje (as tarefas do motor
de jobs, o download do Telegram, que tem tela própria) e explica o que
ainda não funciona, sem botões de enfeite.
"""
from pathlib import Path

import pandas as pd
import streamlit as st

from buscador.core import jobs_registro, resumo_saidas

NOMES_MODULOS = {
    "cli": "Mapear (Fase 1)",
    "gallica_crawl": "Coleta da Gallica (catálogo)",
    "gallica_enriquecer": "Gallica: testar links e traduzir",
}
TEXTO_ESTADO = {
    "rodando": "⏳ rodando",
    "concluido": "✅ concluído",
    "erro": "❌ erro",
    "parado": "⏹ parado",
    "interrompido": "⚠ interrompido",
}


@st.cache_data(ttl=60, show_spinner="Contando os arquivos baixados...")
def _contar_telegram(pasta: str) -> tuple[int, int]:
    return resumo_saidas.contar_arquivos_telegram(Path(pasta))


def mostrar() -> None:
    st.title("Baixar")
    st.caption(
        "Aqui vão ficar os downloads dos itens que vocês aprovarem nas planilhas. Cada arquivo vai "
        "receber uma impressão digital (SHA-256), que liga o arquivo ao catálogo do Instituto."
    )

    st.info(
        "**Ainda não:** o botão \"Baixar aprovados\" (pegar os itens marcados como *Aprovar* numa "
        "planilha e baixar em lote) é a **Fase 2** e ainda não foi construído. Por isso esta tela não "
        "tem esse botão por enquanto."
    )

    # --- O que já baixa de verdade: Telegram ------------------------------
    st.subheader("Telegram")
    quantidade, total = _contar_telegram(str(resumo_saidas.pasta_saidas() / "telegram"))
    col1, col2 = st.columns(2)
    col1.metric("Arquivos baixados do Telegram", f"{quantidade:,}".replace(",", "."))
    col2.metric("Tamanho total", resumo_saidas.formatar_tamanho(total))
    st.caption("O download de tópicos do Telegram tem tela própria: abra **Telegram** no menu ao lado.")

    # --- Gallica: situação real -------------------------------------------
    st.subheader("Gallica")
    st.warning(
        "**Download em lote da Gallica: bloqueado pelo lado deles.** O mecanismo existe e já baixou "
        "um PDF de verdade num teste, mas nas tentativas em lote (23 e 24/09/2026) todos os itens "
        "falharam: o site passou a responder com a verificação anti-robô, com \"serviço indisponível\" "
        "(503) e sem resposta. **Não tentamos contornar** (sem disfarce, sem trocar de identidade) -- "
        "é a regra do projeto. Mapear a Gallica continua funcionando normalmente."
    )

    # --- Tarefas do motor de jobs -----------------------------------------
    st.subheader("Tarefas longas do motor (jobs)")
    try:
        jobs = jobs_registro.carregar_registro(jobs_registro.CAMINHO_PADRAO)
    except Exception as erro:  # registro com defeito não pode derrubar a tela
        st.warning(f"Não deu para ler o registro de tarefas: {erro}")
        return
    if not jobs:
        st.caption("Nenhuma tarefa no registro (jobs/registro.json). Elas são iniciadas pelo jobs.bat.")
        return
    tabela = pd.DataFrame([
        {
            "Tarefa": NOMES_MODULOS.get(j.modulo, j.modulo),
            "Alvo": j.alvo or " ".join(j.argv)[:80],
            "Situação": TEXTO_ESTADO.get(j.estado, j.estado),
            "Iniciada em": j.iniciado_em[:16].replace("T", " "),
            "Atualizada em": j.atualizado_em[:16].replace("T", " "),
            "Registro (log)": j.log_path,
        }
        for j in reversed(jobs)  # as mais novas primeiro
    ])
    st.dataframe(tabela, hide_index=True, width="stretch")
    st.caption(
        "Estas tarefas são coletas e verificações longas (não downloads de PDF). Para ver detalhes, "
        "parar ou retomar: `jobs.bat status`, `jobs.bat parar <id>`, `jobs.bat retomar <id>`."
    )
