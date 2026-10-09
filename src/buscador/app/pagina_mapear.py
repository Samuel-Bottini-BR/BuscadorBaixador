# -*- coding: utf-8 -*-
"""
Tela "Mapear": escolher um site, dizer o que procurar, e o motor gera a
planilha (.xlsx) com os links encontrados, o status de cada link e os
títulos traduzidos -- é a Fase 1 do projeto, agora com botão.

O trabalho pesado é o mesmo comando do terminal (python -m buscador.cli),
rodando em segundo plano (ver core/mapear_segundo_plano.py). A tela só
inicia, acompanha e mostra o resultado.
"""
import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

from buscador.cli import escolher_adapter
from buscador.core import mapear_segundo_plano, resumo_saidas, sites_cadastrados

CHAVE_SITE_ESCOLHIDO = "mapear_site_id"  # a tela Sites grava aqui o site do botão "Mapear agora"
OPCAO_OUTRO = "__outro__"

TEXTO_SITUACAO = {
    "rodando": "⏳ rodando",
    "concluido": "✅ concluído",
    "erro": "❌ parou sem gerar a planilha",
    "desconhecido": "❔ situação desconhecida (o aplicativo foi reaberto no meio?)",
}


def mostrar() -> None:
    st.title("Mapear um site")
    st.caption(
        "Escolha o site e o que procurar. O aplicativo lista as obras, testa cada link e traduz os "
        "títulos para o português, e entrega tudo numa planilha."
    )

    try:
        sites = sites_cadastrados.carregar_sites()
    except ValueError as erro:
        st.error(str(erro))
        sites = []
    mapeaveis = [s for s in sites if s.get("adapter") and s.get("metodo") != "proibido"]

    _formulario(mapeaveis)
    _andamento()
    _ultima_planilha()


# ---------------------------------------------------------------------------
# Formulário: site + o que procurar + botão Mapear
# ---------------------------------------------------------------------------
def _formulario(mapeaveis: list[dict]) -> None:
    ids = [s["id"] for s in mapeaveis] + [OPCAO_OUTRO]
    nomes = {s["id"]: s["nome"] for s in mapeaveis}
    nomes[OPCAO_OUTRO] = "Outro (colar um endereço)"
    escolhido = st.session_state.get(CHAVE_SITE_ESCOLHIDO)
    indice = ids.index(escolhido) if escolhido in ids else 0

    with st.container(border=True):
        id_site = st.selectbox("Site", ids, index=indice, format_func=lambda i: nomes[i])
        st.session_state[CHAVE_SITE_ESCOLHIDO] = id_site
        site = sites_cadastrados.achar_site(mapeaveis, id_site)

        if site:
            rotulo = "Procurar (autor, título ou assunto)" if site.get("entrada") == "consulta" else "Endereço da página (URL)"
            texto = st.text_input(rotulo, placeholder=f"Ex.: {site.get('exemplo', '')}", key=f"texto_{id_site}")
            adapter = site["adapter"]
        else:
            texto = st.text_input("Endereço (URL)", placeholder="https://...", key="texto_outro")
            adapter = None
            if texto.strip():
                try:
                    adapter = escolher_adapter(texto.strip())
                except ValueError:
                    st.warning(
                        "O motor ainda não tem adaptador para esse endereço (o adaptador genérico ainda "
                        "não existe). Cadastre o site na tela Sites para verificar o robots.txt dele."
                    )
        if adapter:
            st.caption(f"Adaptador usado pelo motor: `{adapter}`")
            if adapter == "gallica":
                st.caption("Gallica: um nome simples vira a busca `gallica all \"nome\"` (até 50 resultados). "
                           "Quem sabe a linguagem CQL pode digitar a consulta completa.")

        ficha = mapear_segundo_plano.ultimo_mapeamento()
        ocupado = ficha is not None and mapear_segundo_plano.situacao(ficha) == "rodando"
        if st.button("Mapear", type="primary", disabled=not adapter or ocupado,
                     help="Espere o mapeamento atual terminar." if ocupado else None):
            try:
                entrada = mapear_segundo_plano.montar_consulta(adapter, texto)
                mapear_segundo_plano.iniciar_mapeamento(adapter, entrada, nome_site=nomes.get(id_site, ""))
            except (ValueError, OSError) as erro:
                st.warning(f"Não deu para começar: {erro}")
            else:
                st.toast("Mapeamento iniciado em segundo plano.")
                st.rerun()


# ---------------------------------------------------------------------------
# Andamento do mapeamento atual
# ---------------------------------------------------------------------------
def _andamento() -> None:
    ficha = mapear_segundo_plano.ultimo_mapeamento()
    if not ficha:
        return
    situacao = mapear_segundo_plano.situacao(ficha)
    # Enquanto roda, este pedaço da tela se redesenha sozinho a cada 5 s
    # (st.fragment com run_every) -- sem precisar recarregar a tela toda.
    st.fragment(run_every=5 if situacao == "rodando" else None)(_desenhar_andamento)(ficha, situacao)


def _desenhar_andamento(ficha: dict, situacao_antes: str) -> None:
    situacao = mapear_segundo_plano.situacao(ficha)
    if situacao_antes == "rodando" and situacao != "rodando":
        # Acabou de terminar: redesenha a tela INTEIRA (não só este pedaço),
        # para o botão "Mapear" voltar a funcionar e a planilha nova aparecer.
        st.rerun()
    st.subheader("Último mapeamento")
    inicio = datetime.datetime.fromisoformat(ficha["iniciado_em"])
    minutos = int((datetime.datetime.now() - inicio).total_seconds() // 60)
    st.markdown(
        f"**{ficha.get('site') or ficha['adapter']}** · procurando `{ficha['entrada']}` · "
        f"iniciado {inicio:%d/%m %H:%M} · **{TEXTO_SITUACAO.get(situacao, situacao)}**"
    )
    if situacao == "rodando":
        st.caption(f"Rodando há {minutos} min. Cada link é testado com calma (e a Gallica pede 6 s entre "
                   "pedidos), então pode levar vários minutos. Pode trocar de tela; ele continua.")
        st.button("Atualizar agora")
    log = mapear_segundo_plano.ler_fim_do_log(ficha)
    if situacao == "erro" and any(p in log for p in ("ConnectionError", "ProxyError", "Max retries", "Timeout")):
        st.warning("O motor não conseguiu falar com o site (sem internet, site fora do ar ou bloqueado "
                   "no caminho). Tente de novo mais tarde.")
    if log:
        with st.expander("Registro (log) do motor", expanded=situacao == "erro"):
            st.code(log, language=None)
    if situacao == "concluido":
        caminho = Path(ficha["saida"])
        st.success(f"Pronto! Planilha salva em: `{caminho}`")
        _botao_baixar(caminho, chave="baixar_ultimo")


def _botao_baixar(caminho: Path, chave: str) -> None:
    try:
        dados = caminho.read_bytes()
    except OSError:
        return
    st.download_button(
        "Exportar planilha (.xlsx)", data=dados, file_name=caminho.name, key=chave,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


# ---------------------------------------------------------------------------
# Prévia da planilha mais nova
# ---------------------------------------------------------------------------
def _ultima_planilha() -> None:
    saidas = resumo_saidas.pasta_saidas()
    # só as planilhas soltas em saidas/ (é onde o mapeamento grava); as
    # das subpastas são de outros trabalhos (Telegram, coleta da Gallica).
    planilhas = resumo_saidas.listar_planilhas(saidas, profundidade_maxima=0)
    st.subheader("Planilhas geradas")
    if not planilhas:
        st.caption("Nenhuma planilha em saidas/ ainda.")
        return
    escolhida = st.selectbox(
        "Planilha", planilhas, format_func=lambda p: f"{p.caminho.name}  ({p.modificada_em:%d/%m/%Y %H:%M})"
    )
    try:
        colunas, linhas, bolinhas = resumo_saidas.ler_previa_planilha(escolhida.caminho, limite=200)
    except Exception as erro:  # planilha aberta/estragada não pode derrubar a tela
        st.warning(f"Não deu para ler esta planilha: {erro}")
        return

    contagem = {b: bolinhas.count(b) for b in resumo_saidas.LEGENDA_STATUS}
    st.markdown("  ·  ".join(
        f"{b} {texto}: **{contagem[b]}**" for b, texto in resumo_saidas.LEGENDA_STATUS.items()
    ))
    # Tudo vira texto (vazio no lugar de "nada"): uma coluna que mistura
    # número e texto (ex.: "ano" = 1581 e "s.d.") atrapalharia a tabela.
    linhas = [["" if valor is None else str(valor) for valor in linha] for linha in linhas]
    tabela = pd.DataFrame(linhas, columns=_nomes_unicos(colunas))
    tabela.insert(0, "cor", bolinhas)  # a bolinha descoberta pela cor da linha
    config = {}
    if "link" in tabela.columns:
        config["link"] = st.column_config.LinkColumn("link", display_text="abrir")
    st.dataframe(tabela, hide_index=True, width="stretch", column_config=config)
    st.caption(
        f"Mostrando até 200 linhas ({len(linhas)} aqui). A tradução PT é automática e pode ter erros. "
        "A coluna avaliacao_humana (Aprovar / Rejeitar / ...) é preenchida no Excel, por enquanto."
    )
    _botao_baixar(escolhida.caminho, chave="baixar_escolhida")


def _nomes_unicos(colunas: list[str]) -> list[str]:
    """A tabela não aceita duas colunas com o mesmo nome: a segunda "autor"
    vira "autor (2)", e assim por diante."""
    vistos, resultado = {}, []
    for nome in colunas:
        vistos[nome] = vistos.get(nome, 0) + 1
        resultado.append(nome if vistos[nome] == 1 else f"{nome} ({vistos[nome]})")
    return resultado
