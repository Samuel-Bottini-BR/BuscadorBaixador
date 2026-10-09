# -*- coding: utf-8 -*-
"""
Tela "Sites": a lista dos sites onde o aplicativo pode procurar, e o
formulário para cadastrar um site novo.

Regra do projeto (seção 7 do CLAUDE.md): antes de cadastrar, o aplicativo
lê o robots.txt do site. Se o site proíbe robôs, a tela NÃO deixa mapear --
só mostra os caminhos legítimos (pular o site ou pedir permissão).

Lembrete sobre o Streamlit: cada clique roda esta função de novo, de cima
para baixo. O que precisa sobreviver entre cliques (ex.: o resultado da
verificação) fica guardado em st.session_state.
"""
import streamlit as st

from buscador.app import pagina_mapear
from buscador.cli import escolher_adapter
from buscador.core import sites_cadastrados, verificar_site
from buscador.core.sites_cadastrados import METODOS_TEXTO

# Chave em st.session_state que a tela Mapear lê para já vir com o site escolhido.
CHAVE_SITE_ESCOLHIDO = "mapear_site_id"


def mostrar() -> None:
    st.title("Sites")
    st.caption(
        "Os sites onde o aplicativo pode procurar. Ele só trabalha em sites cadastrados aqui, "
        "e o jeito de acessar segue as regras do próprio site (robots.txt)."
    )

    try:
        sites = sites_cadastrados.carregar_sites()
    except ValueError as erro:
        st.error(str(erro))
        return

    _formulario_adicionar(sites)

    for site in sites:
        _cartao_do_site(site, sites)


# ---------------------------------------------------------------------------
# Cartão de cada site
# ---------------------------------------------------------------------------
def _cartao_do_site(site: dict, sites: list[dict]) -> None:
    with st.container(border=True):
        info, botoes = st.columns([3, 1])
        with info:
            st.markdown(f"#### {site.get('nome', '?')}")
            st.markdown(f"**Endereço:** {site.get('endereco', '')}")
            metodo = METODOS_TEXTO.get(site.get("metodo"), site.get("metodo") or "?")
            if site.get("adapter"):
                st.markdown(f"**Como acessa:** {metodo} · adaptador do motor: `{site['adapter']}`")
            else:
                st.markdown(f"**Como acessa:** {metodo} · ainda **sem adaptador** no motor")
            if site.get("observacao"):
                st.caption(site["observacao"])
        with botoes:
            pode_mapear = bool(site.get("adapter")) and site.get("metodo") != "proibido"
            if st.button("Mapear agora", key=f"mapear_{site['id']}", type="primary",
                         disabled=not pode_mapear, width="stretch",
                         help=None if pode_mapear else "Este site ainda não pode ser mapeado (ver o texto do cartão)."):
                st.session_state[CHAVE_SITE_ESCOLHIDO] = site["id"]
                # Para trocar de tela, o Streamlit precisa de uma "página"
                # igual à cadastrada no menu (principal.py): mesma função e
                # mesmo url_path.
                st.switch_page(st.Page(pagina_mapear.mostrar, title="Mapear", icon="🗺️", url_path="mapear"))
            if st.button("Fazer login", key=f"login_{site['id']}", width="stretch"):
                st.session_state[f"ver_login_{site['id']}"] = not st.session_state.get(f"ver_login_{site['id']}", False)
            if site["id"] not in {s["id"] for s in sites_cadastrados.SITES_PADRAO}:
                if st.button("Remover", key=f"remover_{site['id']}", width="stretch"):
                    sites_cadastrados.salvar_sites(sites_cadastrados.remover_site(sites, site["id"]))
                    st.rerun()
        if not pode_mapear and site.get("metodo") != "proibido":
            st.caption(
                "Ainda não existe um adaptador para este site. O adaptador genérico (que lê qualquer "
                "site) é um passo futuro da Fase 1; por enquanto, peça ao Claude para escrever um."
            )
        if st.session_state.get(f"ver_login_{site['id']}"):
            _explicar_login(site)


def _explicar_login(site: dict) -> None:
    """Login é sempre feito por VOCÊ, numa janela do Chrome separada (perfil
    próprio do aplicativo). O aplicativo nunca guarda senha no código."""
    url_login = site.get("url_login") or site.get("endereco", "")
    if site.get("metodo") == "api" and not site.get("url_login"):
        st.success("Este site não precisa de login: o aplicativo usa a API oficial dele.")
        return
    st.info(
        "\"Fazer login\" abre uma janela do Chrome separada, com um perfil só do aplicativo. "
        "Você entra com a sua conta ali, aperta Enter no terminal, e a sessão fica salva para "
        "as próximas coletas. Por enquanto isso é feito por um comando no terminal "
        "(na pasta do projeto), porque a janela precisa de você do lado:"
    )
    st.code(f".venv\\Scripts\\python.exe -m buscador.logar {site['id']} {url_login}", language="bat")
    st.caption(
        "Login automático (o aplicativo digitar a senha sozinho) ainda não existe -- e só será feito "
        "para sites que permitem isso."
    )


# ---------------------------------------------------------------------------
# Formulário "+ Adicionar site"
# ---------------------------------------------------------------------------
def _formulario_adicionar(sites: list[dict]) -> None:
    with st.expander("➕ Adicionar site", expanded=bool(st.session_state.get("site_verificado"))):
        # st.form junta os campos: nada acontece enquanto você digita; só
        # quando aperta "Verificar".
        with st.form("adicionar_site"):
            nome = st.text_input("Nome", placeholder="Ex.: Biblioteca Digital Hispânica")
            endereco = st.text_input("Endereço (URL)", placeholder="Ex.: https://bdh.bne.es")
            verificar = st.form_submit_button("Verificar", type="primary")

        if verificar:
            try:
                with st.spinner("Lendo o robots.txt e procurando API oficial (até 3 pedidos, com calma)..."):
                    resultado = verificar_site.verificar_site(endereco)
            except ValueError as erro:
                st.warning(str(erro))
                st.session_state.pop("site_verificado", None)
            else:
                st.session_state["site_verificado"] = {"nome": nome.strip(), "resultado": resultado}

        dados = st.session_state.get("site_verificado")
        if dados:
            _mostrar_resultado(dados["nome"], dados["resultado"], sites)


def _mostrar_resultado(nome: str, resultado: verificar_site.ResultadoVerificacao, sites: list[dict]) -> None:
    st.markdown(f"**Resultado da verificação** de {resultado.endereco}")
    if resultado.robots_permite is True:
        robots = "permite a leitura ✔" if resultado.robots_encontrado else "não existe (sem restrições) ✔"
    elif resultado.robots_permite is False:
        robots = "**proíbe** a leitura ✘"
    else:
        robots = "não deu para ler"
    st.markdown(f"- **robots.txt:** {robots}")
    st.markdown(f"- **API oficial encontrada:** {resultado.api_encontrada or 'não'}"
                + (f" ({resultado.url_api})" if resultado.url_api else ""))
    st.markdown(f"- **Método sugerido:** {verificar_site.explicar_metodo(resultado)}")
    adapter = _adapter_conhecido(resultado.endereco)
    if adapter:
        st.markdown(f"- **O motor já tem adaptador próprio para este site:** `{adapter}`")
    if resultado.sitemaps:
        st.markdown(f"- **Sitemap(s) citados no robots.txt:** {', '.join(resultado.sitemaps[:3])}")
    for aviso in resultado.avisos:
        st.caption(f"⚠ {aviso}")
    if resultado.robots_texto:
        with st.expander("Ver o robots.txt"):
            st.code(resultado.robots_texto[:5000], language=None)

    if resultado.metodo_sugerido == "proibido":
        st.error(
            "O robots.txt deste site não permite que robôs leiam este endereço. O aplicativo não burla "
            "essa regra (nem com disfarce, nem com outro navegador). Caminhos legítimos:"
        )
        for opcao in verificar_site.OPCOES_SE_PROIBIDO:
            st.markdown(f"- {opcao}")
        st.button("Salvar site", disabled=True, help="Sites proibidos pelo robots.txt não são cadastrados.")
        return
    if resultado.metodo_sugerido == "indefinido":
        st.warning("Não dá para salvar ainda: tente \"Verificar\" de novo mais tarde.")
        return

    col_salvar, col_cancelar, _ = st.columns([1, 1, 4])
    if col_salvar.button("Salvar site", type="primary"):
        novo = {
            "nome": nome, "endereco": resultado.endereco, "metodo": resultado.metodo_sugerido,
            "adapter": adapter, "exemplo": resultado.endereco,
            # Gallica e Internet Archive recebem um texto de busca; os outros, um endereço
            "entrada": "consulta" if adapter in ("gallica", "internet_archive") else "url",
            "observacao": f"Verificado pelo aplicativo. {verificar_site.explicar_metodo(resultado)}",
        }
        try:
            sites_cadastrados.salvar_sites(sites_cadastrados.adicionar_site(sites, novo))
        except ValueError as erro:
            st.warning(str(erro))
        else:
            st.session_state.pop("site_verificado", None)
            st.toast(f"Site \"{nome}\" salvo.")
            st.rerun()
    if col_cancelar.button("Cancelar"):
        st.session_state.pop("site_verificado", None)
        st.rerun()


def _adapter_conhecido(endereco: str) -> str | None:
    """Se o domínio já tem adaptador no motor (cli.ADAPTERS_POR_DOMINIO), diz qual."""
    try:
        return escolher_adapter(endereco)
    except ValueError:
        return None
