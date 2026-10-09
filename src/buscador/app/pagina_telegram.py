# -*- coding: utf-8 -*-
"""
Tela "Telegram" do aplicativo: conta -> grupo -> tópico -> Listar, Escolher, Baixar.

Lembrete de como o Streamlit funciona: a cada clique o script inteiro roda
de novo, de cima para baixo. Por isso:
- o que precisa ser lembrado entre cliques fica em st.session_state
  (ex.: a lista de grupos da conta que acabou de ser carregada) ou num
  arquivo em saidas/telegram/ (grupos, listas, downloads);
- NADA conecta ao Telegram só por abrir a tela: só quando um botão é
  clicado. Assim a tela abre rápido e funciona mesmo sem internet.

A parte que não é tela (pastas, listas, download, repetidos) mora em
core/telegram_grupos.py e core/telegram_download.py -- lá tem testes.

Regras: senha nunca é guardada (só usada na hora do login); o arquivo
.session vale como senha e nunca vai pro GitHub; se o Telegram mandar
esperar (FLOOD_WAIT), o Telethon espera sozinho; uma conta por vez.
"""
import asyncio
import io
import os
import subprocess
from collections import Counter
from datetime import datetime
from pathlib import Path

import pandas as pd
import qrcode
import streamlit as st
from telethon.errors import PasswordHashInvalidError, RPCError

from buscador.core import relogio
from buscador.core import telegram_download as dl
from buscador.core.registro_erros import registrar_erro
from buscador.core.acao_humana import TIPO_LOGIN, AcaoHumanaNecessaria, formatar_aviso
from buscador.core.config_sites import CAMINHO_PADRAO
from buscador.core.escrita_atomica import salvar_json_atomico
from buscador.core.telegram_busca import contar_arquivos, listar_arquivos, montar_lista_tdl
from buscador.core.telegram_conta import (
    PASTA_SESSOES, caminho_sessao, criar_cliente, ler_credenciais, login_qr,
)
from buscador.core.telegram_grupos import (
    CAMINHO_GRUPOS, PASTA_TELEGRAM, ler_grupos, listar_contas, listar_dialogos,
    listar_topicos, mascarar_telefone, nome_para_mostrar, resolver_grupo, salvar_grupo,
)

# Os caminhos ficam aqui em cima (e não direto nas funções) para os testes
# poderem trocá-los por uma pasta temporária.
CAMINHO_CFG = CAMINHO_PADRAO
PASTA_CONTAS = PASTA_SESSOES
ARQUIVO_GRUPOS = CAMINHO_GRUPOS
PASTA_SAIDA = PASTA_TELEGRAM

CHAVE_DOCUMENTOS = "documentos (PDF, EPUB, RAR...)"

AVISO_REPETIDOS = (
    "**Repetidos:** só contam como cópia arquivos com conteúdo **idêntico**, "
    "conferido pela impressão digital **SHA-256** (mesmo nome e mesmo tamanho não "
    "bastam). As cópias vão **todas** para a pasta `repetidos/`, lado a lado. "
    "**Nada é apagado:** você decide depois."
)


class SenhaFaltando(Exception):
    """A conta tem senha de duas etapas e o campo da senha está vazio."""


# --- ajudantes ----------------------------------------------------------------

def _rodar(conta: str, trabalho):
    """Abre a conta, roda trabalho(cliente) e fecha a conexão.

    asyncio.run(...) é o jeito de rodar código "async" (o Telethon é todo
    assim) de dentro de um script comum. Qualquer problema vira um aviso
    na tela em vez de quebrar a página. Devolve None se deu errado."""
    async def _tudo():
        cliente = criar_cliente(conta, CAMINHO_CFG, PASTA_CONTAS)
        await cliente.connect()
        try:
            if not await cliente.is_user_authorized():
                raise AcaoHumanaNecessaria(
                    TIPO_LOGIN,
                    f"a conta '{conta}' não está conectada. Use '+ Adicionar conta' "
                    "com esse mesmo nome para escanear o QR de novo.",
                    site="telegram",
                )
            return await trabalho(cliente)
        finally:
            await cliente.disconnect()

    try:
        return asyncio.run(_tudo())
    except AcaoHumanaNecessaria as erro:
        st.warning(formatar_aviso(erro))
    except ValueError as erro:  # ex.: link não reconhecido, grupo não achado
        st.error(str(erro))
    except (RPCError, ConnectionError, OSError) as erro:
        st.error(f"O Telegram não respondeu como esperado: {erro}")
    return None


def _qr_png(link: str) -> bytes:
    """Desenha o QR em memória (bytes de uma imagem PNG) -- nenhum arquivo."""
    memoria = io.BytesIO()
    qrcode.make(link).save(memoria)
    return memoria.getvalue()


def _gb(n_bytes: int) -> str:
    return f"{n_bytes / 1024**3:.2f} GB".replace(".", ",")


def _abrir_pasta(pasta) -> None:
    """Botão "Abrir pasta": só existe no Windows (os.startfile)."""
    if hasattr(os, "startfile") and st.button("Abrir pasta", key=f"abrir_{pasta}"):
        pasta.mkdir(parents=True, exist_ok=True)
        os.startfile(pasta)


# --- 1. contas ------------------------------------------------------------------

def _adicionar_conta(nome: str, senha: str) -> None:
    try:
        caminho_sessao(nome, PASTA_CONTAS)  # só para validar o nome
    except ValueError as erro:
        st.error(str(erro))
        return
    lugar_qr = st.empty()  # um "espaço reservado": cada QR novo substitui o anterior
    qrs = {"n": 0}

    def mostrar_qr(link: str) -> None:
        qrs["n"] += 1
        with lugar_qr.container():
            col_qr, col_texto = st.columns([1, 2])
            col_qr.image(_qr_png(link), width=220)
            col_texto.markdown(
                "**No celular:**\n"
                "1. Abra o Telegram → **Configurações**\n"
                "2. **Dispositivos** → **Conectar dispositivo**\n"
                "3. Aponte a câmera para este código\n\n"
                f"QR nº {qrs['n']} — se vencer, aparece outro sozinho (até ~5 minutos)."
            )

    def pedir_senha() -> str:
        if not senha:
            raise SenhaFaltando()
        return senha  # usada só agora; não é gravada em lugar nenhum

    async def _login():
        cliente = criar_cliente(nome, CAMINHO_CFG, PASTA_CONTAS)
        await cliente.connect()
        try:
            await login_qr(cliente, mostrar_qr, pedir_senha)
            return await cliente.get_me()
        finally:
            await cliente.disconnect()

    try:
        eu = asyncio.run(_login())
    except SenhaFaltando:
        lugar_qr.empty()
        st.warning(
            "Esta conta tem **senha de duas etapas**. Preencha o campo da senha "
            "e clique de novo em 'Gerar QR e conectar' (vai aparecer um QR novo)."
        )
        return
    except PasswordHashInvalidError:
        lugar_qr.empty()
        st.error("A senha de duas etapas está errada. Confira e tente de novo.")
        return
    except AcaoHumanaNecessaria as erro:
        lugar_qr.empty()
        st.warning(formatar_aviso(erro))
        return
    except (RPCError, ConnectionError, OSError) as erro:
        lugar_qr.empty()
        st.error(f"O Telegram não respondeu como esperado: {erro}")
        return
    lugar_qr.empty()
    nome_tg = " ".join(p for p in (eu.first_name, eu.last_name) if p)
    st.session_state["tg_msg_conta"] = f"Pronto! Conta '{nome}' conectada como {nome_tg}."
    # Não dá para mudar o seletor de conta depois que ele já foi desenhado
    # nesta rodada; guardamos o pedido e ele é aplicado na próxima.
    st.session_state["tg_conta_pendente"] = nome
    st.rerun()  # desenha a tela de novo, já com a conta nova na lista


def _secao_contas() -> str | None:
    """Mostra as contas e devolve o nome da escolhida (ou None)."""
    st.subheader("Contas")
    if mensagem := st.session_state.pop("tg_msg_conta", None):
        st.success(mensagem)
    contas = listar_contas(PASTA_CONTAS)
    conta = None
    if st.session_state.get("tg_conta_pendente") in contas:
        st.session_state["tg_conta"] = st.session_state.pop("tg_conta_pendente")
    if contas:
        if st.session_state.get("tg_conta") not in contas:
            st.session_state.pop("tg_conta", None)
        conta = st.selectbox("Usar a conta", contas, key="tg_conta")
        if st.button("Verificar conexão"):
            async def _quem(cliente):
                return await cliente.get_me()
            eu = _rodar(conta, _quem)
            if eu:
                nome = " ".join(p for p in (eu.first_name, eu.last_name) if p)
                st.success(f"Conectada como {nome} ({mascarar_telefone(eu.phone)}).")
    else:
        st.info("Nenhuma conta conectada ainda. Use '+ Adicionar conta' abaixo.")

    with st.expander("+ Adicionar conta", expanded=not contas):
        nome = st.text_input("Nome da conta (ex.: samuel, kaique)", key="tg_nova_conta")
        senha = st.text_input(
            "Senha de duas etapas (só se a conta tiver)", type="password", key="tg_senha",
            help="Usada só para entrar. Não fica guardada em lugar nenhum.",
        )
        st.caption("Cada pessoa usa a própria conta. Não use várias contas para "
                   "\"somar velocidade\" -- o Telegram pode bloquear.")
        if st.button("Gerar QR e conectar", type="primary"):
            _adicionar_conta(nome.strip(), senha)
    return conta


# --- 2. grupos --------------------------------------------------------------------

def _secao_grupos(conta: str) -> dict | None:
    st.subheader("Grupo")
    grupos = ler_grupos(ARQUIVO_GRUPOS)
    grupo = None
    if grupos:
        indice = st.selectbox("Grupo", range(len(grupos)), key="tg_grupo",
                              format_func=lambda i: nome_para_mostrar(grupos[i]))
        grupo = grupos[indice]

    with st.expander("+ Adicionar grupo ou conversa", expanded=not grupos):
        link = st.text_input("Colar o link do grupo ou canal",
                             placeholder="https://t.me/nomedogrupo, @nome ou link de uma mensagem")
        if st.button("Adicionar pelo link"):
            async def _resolver(cliente):
                return await resolver_grupo(cliente, link)
            novo = _rodar(conta, _resolver)
            if novo:
                salvar_grupo(novo, ARQUIVO_GRUPOS)
                st.success(f"Adicionado: {nome_para_mostrar(novo)}")
                st.rerun()

        st.caption(f"ou escolha um grupo em que a conta '{conta}' já está")
        if st.button("Carregar meus grupos"):
            st.session_state["tg_dialogos"] = _rodar(conta, listar_dialogos)
        dialogos = st.session_state.get("tg_dialogos") or []
        if dialogos:
            i = st.selectbox("Meus grupos e canais", range(len(dialogos)),
                             format_func=lambda i: nome_para_mostrar(dialogos[i]))
            if st.button("Adicionar"):
                salvar_grupo(dialogos[i], ARQUIVO_GRUPOS)
                st.rerun()
        st.caption("O programa não entra em grupo nenhum sozinho: a conta precisa já participar.")
    return grupo


# --- 3. tópicos -------------------------------------------------------------------

def _situacao(chat_id: int, topico_id) -> str:
    pasta = dl.pasta_alvo(PASTA_SAIDA, chat_id, topico_id)
    return dl.situacao(pasta, rodando=bool(dl.download_rodando(pasta)))


def _secao_topicos(conta: str, grupo: dict):
    """Devolve (topico_id, nome) do alvo escolhido -- topico_id None para
    conversa sem tópicos -- ou None se ainda não dá para escolher."""
    chat_id = grupo["chat_id"]
    if not grupo.get("forum"):
        st.caption("Esta conversa não tem tópicos: a lista e o download são da conversa "
                   f"inteira (pasta `{dl.nome_alvo(chat_id, None)}`).")
        return None, grupo["nome"]

    st.subheader("Tópicos")
    topicos = grupo.get("topicos") or []
    col1, col2 = st.columns(2)
    if col1.button("Atualizar tópicos" if topicos else "Carregar tópicos"):
        async def _carregar(cliente):
            return await listar_topicos(cliente, chat_id)
        novos = _rodar(conta, _carregar)
        if novos is not None:
            salvar_grupo({**grupo, "topicos": novos}, ARQUIVO_GRUPOS)
            st.rerun()
    if not topicos:
        st.info("Clique em 'Carregar tópicos' para ver os tópicos deste grupo.")
        return None

    contagens = st.session_state.setdefault("tg_contagens", {})
    if col2.button("Contar arquivos de todos (rápido)"):
        barra = st.progress(0.0, text="Contando...")

        async def _contar_todos(cliente):
            for n, t in enumerate(topicos, 1):
                contagem = await contar_arquivos(cliente, chat_id, t["id"])
                contagens[(chat_id, t["id"])] = contagem.get(CHAVE_DOCUMENTOS, 0)
                barra.progress(n / len(topicos), text=f"{n} de {len(topicos)} tópicos")
            return True
        _rodar(conta, _contar_todos)
        barra.empty()

    situacoes = {t["id"]: _situacao(chat_id, t["id"]) for t in topicos}
    tabela = pd.DataFrame([{
        "Tópico": t["titulo"],
        "Nº": t["id"],
        "Documentos": contagens.get((chat_id, t["id"])),
        "Situação": situacoes[t["id"]],
    } for t in topicos])
    # "Int64" (com I maiúsculo) é o tipo de número do pandas que aceita
    # "vazio": tópico ainda não contado aparece em branco, não "None".
    tabela["Documentos"] = tabela["Documentos"].astype("Int64")
    st.dataframe(tabela, hide_index=True, width="stretch",
                 column_config={"Nº": st.column_config.NumberColumn(format="%d"),
                                "Documentos": st.column_config.NumberColumn(
                                    help="Contagem rápida pela busca do Telegram")})
    i = st.selectbox("Trabalhar no tópico", range(len(topicos)), key=f"tg_topico_{chat_id}",
                     format_func=lambda i: f"{topicos[i]['titulo']} — {situacoes[topicos[i]['id']]}")
    return topicos[i]["id"], topicos[i]["titulo"]


# --- 4. etapas: listar, escolher, baixar ------------------------------------------

def _etapas_no_topo(lista_existe: bool, marcados_existe: bool, rodando, prog) -> None:
    """As 3 caixinhas lado a lado mostrando em que etapa estamos."""
    if prog and prog["total"] and prog["baixados"] >= prog["total"]:
        baixar = ("feita", "tudo o que foi marcado está na pasta")
    elif rodando:
        baixar = ("agora", "baixando em segundo plano")
    elif marcados_existe:
        baixar = ("agora", "pode baixar (ou continuar)")
    else:
        baixar = ("depois", "vai para a pasta do tópico")
    etapas = [
        ("Listar", ("feita", "lista pronta") if lista_existe else ("agora", "buscar os documentos")),
        ("Escolher", ("feita", "marcados gravados") if marcados_existe
         else (("agora", "marque o que baixar") if lista_existe else ("depois", "marque o que baixar"))),
        ("Baixar", baixar),
    ]
    for n, (coluna, (titulo, (estado, texto))) in enumerate(zip(st.columns(3), etapas), 1):
        with coluna.container(border=True):
            st.markdown(f"**Etapa {n} · {estado}**  \n{titulo}")
            st.caption(texto)


def _etapa_listar(conta, grupo, topico_id, pasta) -> None:
    chat_id, tipo = grupo["chat_id"], grupo.get("tipo", "canal")
    st.markdown("#### 1. Listar")
    chave_contagem = f"tg_contagem_{pasta.name}"
    col1, col2 = st.columns(2)
    if col1.button("Contar (rápido)", help="Uma pergunta só ao Telegram: quantos arquivos de cada tipo"):
        async def _contar(cliente):
            return await contar_arquivos(cliente, chat_id, topico_id, tipo)
        st.session_state[chave_contagem] = _rodar(conta, _contar)
    if col2.button("Listar documentos", type="primary",
                   help="Busca só as mensagens com documento (PDF, EPUB, RAR...), de 100 em 100"):
        barra = st.progress(0.0, text="Começando...")

        async def _listar(cliente):
            total = (await contar_arquivos(cliente, chat_id, topico_id, tipo)).get(CHAVE_DOCUMENTOS, 0)

            def ao_receber(pagina, n):
                fracao = min(n / total, 1.0) if total else 0.0
                barra.progress(fracao, text=f"página {pagina}: {n} de ~{total} documentos")
            return await listar_arquivos(cliente, chat_id, topico_id,
                                         ao_receber_pagina=ao_receber, tipo=tipo)
        mensagens = _rodar(conta, _listar)
        barra.empty()
        if mensagens is not None:
            lista = montar_lista_tdl(chat_id, mensagens)
            pasta.mkdir(parents=True, exist_ok=True)
            salvar_json_atomico(lista, dl.caminho_lista(pasta))
            tamanho = sum(dl.tamanhos_por_id(lista).values())
            st.success(f"{len(lista['messages'])} documentos ({_gb(tamanho)}), sem figurinhas.")

    contagem = st.session_state.get(chave_contagem)
    if contagem:
        colunas = st.columns(len(contagem))
        for coluna, (nome, numero) in zip(colunas, contagem.items()):
            coluna.metric(nome, numero)
    caminho = dl.caminho_lista(pasta)
    if caminho.exists():
        quando = datetime.fromtimestamp(caminho.stat().st_mtime)
        st.caption(f"Lista gravada em {quando:%d/%m/%Y %H:%M}: `{caminho}`")


def _etapa_escolher(pasta) -> tuple[dict, list[int]]:
    """Mostra a tabela com caixinhas. Devolve (lista, ids marcados)."""
    st.markdown("#### 2. Escolher")
    lista = dl.ler_lista(dl.caminho_lista(pasta))
    linhas = dl.linhas_da_lista(lista, dl.ids_baixados(dl.pasta_arquivos(pasta)))
    if not linhas:
        st.info("A lista está vazia: não há documentos aqui.")
        return lista, []
    por_tipo = Counter(l["tipo"] for l in linhas)
    tipos = sorted(por_tipo, key=lambda t: -por_tipo[t])
    escolhidos = st.multiselect("Tipos", tipos, default=tipos, key=f"tg_tipos_{pasta.name}",
                                format_func=lambda t: f"{t} ({por_tipo[t]})")
    esconder = st.toggle("Esconder os que já estão na pasta", key=f"tg_esconder_{pasta.name}")
    visiveis = [l for l in linhas
                if l["tipo"] in escolhidos and not (esconder and l["ja_baixado"])]
    if not visiveis:
        st.info("Nenhum arquivo neste filtro.")
        return lista, []
    # A "chave" da tabela muda junto com o filtro -- assim as marcações de um
    # filtro não vão parar, por engano, em linhas de outro.
    chave = f"tg_editor_{pasta.name}_{'-'.join(sorted(escolhidos))}_{esconder}"
    editado = st.data_editor(
        pd.DataFrame(visiveis), key=chave, hide_index=True, width="stretch",
        disabled=["id", "arquivo", "tipo", "tamanho_mb", "data", "ja_baixado"],
        column_config={
            "baixar": st.column_config.CheckboxColumn("Baixar"),
            "id": st.column_config.NumberColumn("Nº msg", format="%d"),
            "arquivo": "Arquivo",
            "tipo": "Tipo",
            "tamanho_mb": st.column_config.NumberColumn("Tamanho (MB)", format="%.1f"),
            "data": "Data",
            "ja_baixado": st.column_config.CheckboxColumn("Já na pasta"),
        },
    )
    marcados = [int(i) for i in editado.loc[editado["baixar"], "id"]]
    tamanhos = dl.tamanhos_por_id(lista)
    st.caption(f"**{len(marcados)} marcados** (≈ {_gb(sum(tamanhos[i] for i in marcados))}) · "
               f"mostrando {len(visiveis)} de {len(linhas)}. Só entram no download as "
               "linhas marcadas que aparecem na tabela.")
    return lista, marcados


def _relogio_pronto() -> bool:
    """Antes de baixar: confere o relógio do PC. O tdl trava sem avisar se o
    relógio estiver mais de ~30 s errado (aconteceu em 09/10/2026). Se estiver
    errado, acerta sozinho (o Windows pede um "Sim" de administrador) e
    confere de novo."""
    with st.spinner("Conferindo o relógio do PC..."):
        dif = relogio.diferenca_do_relogio()
    if relogio.relogio_ok(dif):
        return True
    st.warning(relogio.descrever(dif) + " Vou acertar agora -- clique **Sim** na janela do Windows.")
    if not relogio.acertar_relogio_windows():
        st.error("Não consegui acertar o relógio automaticamente (isto não é Windows?).")
        return False
    dif = relogio.diferenca_do_relogio()
    if relogio.relogio_ok(dif):
        st.success("Relógio acertado. " + relogio.descrever(dif))
        return True
    registrar_erro("tela Telegram: acertar relógio",
                   detalhe=f"Depois de tentar acertar: {relogio.descrever(dif)}")
    st.error(relogio.descrever(dif) + " Não consegui acertar sozinho; ficou anotado em "
             "logs\\erros.log. Tente: Configurações > Hora e idioma > Sincronizar agora.")
    return False


def _anotar_falha_do_download(pasta, log, rodando) -> None:
    """Se o download parou com problema (SEM PROGRESSO / LIMITE), anota no
    caderno de erros -- uma vez por ocorrência -- com o fim do rodadas.log e do
    registro interno do tdl, para o Claude ler e corrigir."""
    if rodando or not log or not any("SEM PROGRESSO" in l or "LIMITE" in l for l in log):
        return
    caminho = dl.caminho_log(pasta)
    marca = f"falha_anotada:{caminho}:{caminho.stat().st_mtime if caminho.exists() else 0}"
    if st.session_state.get(marca):
        return
    st.session_state[marca] = True
    tdl_log = Path.home() / ".tdl" / "log" / "latest.log"
    detalhe = "rodadas.log:\n" + "\n".join(log)
    if tdl_log.exists():
        detalhe += "\n\ntdl latest.log (fim):\n" + "\n".join(dl.ultimas_linhas(tdl_log, 25))
    registrar_erro(f"download Telegram {pasta.name}", detalhe=detalhe)
    st.error("O download parou sem conseguir baixar. Já anotei os detalhes em logs\\erros.log "
             "-- é só avisar o Claude.")


def _etapa_baixar(grupo, topico_id, nome, pasta, lista, marcados, rodando) -> None:
    st.markdown("#### 3. Baixar")
    st.info(AVISO_REPETIDOS)
    st.caption("Quem baixa é o tdl, que tem login próprio (scripts/telegram/tdl_login_qr.bat). "
               "Arquivos já na pasta não são baixados de novo.")
    if rodando is None:
        st.warning("Não consegui saber se o download anterior deste tópico ainda está rodando. "
                   f"Se tiver certeza de que acabou, apague `{dl.caminho_pid(pasta)}`.")

    col1, col2, col3 = st.columns(3)
    if col1.button(f"Baixar {len(marcados)} marcados", type="primary",
                   disabled=not marcados or bool(rodando)):
        bash = dl.achar_bash()
        if bash is None:
            st.error("Não achei o Git Bash (precisa dele para rodar o baixar_topico.sh). "
                     f"Lugar esperado: `{dl.BASH_WINDOWS[0]}`. Instale o Git for Windows.")
        elif not _relogio_pronto():
            pass  # _relogio_pronto já mostrou o aviso
        else:
            dl.gravar_marcados(lista, marcados, pasta)
            try:
                pid = dl.iniciar_download(pasta, bash)
                st.success(f"Download iniciado em segundo plano (processo {pid}). "
                           "Pode fechar a tela e voltar depois.")
                rodando = True
            except RuntimeError as erro:
                st.error(str(erro))
    col2.button("Atualizar", help="Lê de novo a pasta e o log")
    with col3:
        _abrir_pasta(dl.pasta_arquivos(pasta))

    prog = dl.progresso(pasta)
    if prog and prog["total"]:
        st.progress(prog["baixados"] / prog["total"],
                    text=f"{prog['baixados']} de {prog['total']} · "
                         f"{_gb(prog['bytes_baixados'])} de {_gb(prog['bytes_total'])}"
                         + (" · baixando" if rodando else ""))
    log = dl.ultimas_linhas(dl.caminho_log(pasta))
    _anotar_falha_do_download(pasta, log, rodando)
    if log:
        st.caption("Últimas linhas do rodadas.log")
        st.code("\n".join(log), language=None)

    if st.button("Gerar planilha", help="Planilha .xlsx (Resumo + Arquivos) com toda a lista"):
        saida = pasta / f"{pasta.name}_lista.xlsx"
        comando = dl.comando_planilha(dl.caminho_lista(pasta), saida, grupo["chat_id"],
                                      topico_id, nome, grupo["nome"])
        resultado = subprocess.run(comando, capture_output=True, text=True, encoding="utf-8",
                                   errors="replace")
        if resultado.returncode == 0:
            st.success(f"Planilha gerada: `{saida}`")
        else:
            st.error("A planilha não foi gerada.")
        st.code((resultado.stdout + resultado.stderr).strip() or "(sem mensagens)", language=None)

    with st.expander("Conferir repetidos (SHA-256)"):
        st.caption("Faça isso só depois que o download terminar: o script usa os arquivos "
                   "da pasta para saber o que falta.")
        chave = f"tg_repetidos_{pasta.name}"
        if st.button("Procurar repetidos", disabled=bool(rodando)):
            with st.spinner("Calculando as impressões digitais (pode demorar em arquivos grandes)..."):
                st.session_state[chave] = dl.achar_repetidos(dl.pasta_arquivos(pasta))
        grupos = st.session_state.get(chave)
        if grupos is not None:
            if not grupos:
                st.success("Nenhum arquivo com conteúdo idêntico.")
            for g in grupos:
                st.markdown("- " + " = ".join(f"`{p.name}`" for p in g))
            if grupos and st.button("Mover estes para repetidos/", disabled=bool(rodando)):
                movidos = dl.mover_repetidos(grupos, dl.pasta_arquivos(pasta))
                st.session_state.pop(chave)
                st.success(f"{len(movidos)} arquivos movidos para repetidos/. Nada foi apagado.")


def _secao_etapas(conta, grupo, topico_id, nome) -> None:
    pasta = dl.pasta_alvo(PASTA_SAIDA, grupo["chat_id"], topico_id)
    rodando = dl.download_rodando(pasta)
    st.subheader(nome)
    st.caption(f"Pasta: `{pasta}`")
    _etapas_no_topo(dl.caminho_lista(pasta).exists(), dl.caminho_marcados(pasta).exists(),
                    rodando, dl.progresso(pasta))
    _etapa_listar(conta, grupo, topico_id, pasta)
    if not dl.caminho_lista(pasta).exists():
        return
    lista, marcados = _etapa_escolher(pasta)
    _etapa_baixar(grupo, topico_id, nome, pasta, lista, marcados, rodando)


# --- a tela ----------------------------------------------------------------------

def mostrar() -> None:
    st.title("Telegram")
    st.caption("Baixar arquivos de um tópico de grupo. Cada tópico vai para uma pasta "
               "própria, sem misturar.")
    try:
        ler_credenciais(CAMINHO_CFG)
    except AcaoHumanaNecessaria as erro:
        st.warning(formatar_aviso(erro))
        return

    conta = _secao_contas()
    if not conta:
        return
    st.divider()
    grupo = _secao_grupos(conta)
    if not grupo:
        return
    alvo = _secao_topicos(conta, grupo)
    if alvo is None:
        return
    st.divider()
    _secao_etapas(conta, grupo, *alvo)
