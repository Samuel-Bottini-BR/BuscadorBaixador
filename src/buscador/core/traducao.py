# -*- coding: utf-8 -*-
"""
Tradução automática híbrida (mistura de mais de um jeito): tenta um serviço
online primeiro (melhor qualidade) e cai pra um tradutor offline se não
houver internet ou o serviço online falhar. Essa ideia de "tentar um jeito,
cair pro próximo se falhar" é chamada de cascata (cascade) -- é o mesmo
padrão que inspirou core/metodo_coleta.py, só que aqui é bem mais simples
(hardcoded/escrito direto no código, sem uma lista configurável de opções).

Regra importante: esta função NUNCA lança erro pra quem chamou ela -- se as
duas vias (online e offline) falharem, ela devolve o texto original em vez
de travar o resto do programa por causa de uma tradução que não deu certo.
"""
import logging
import time

logger = logging.getLogger(__name__)
# "logger" é o jeito padrão do Python de registrar mensagens internas
# (avisos, erros) sem usar "print" -- dá pra configurar depois pra
# aparecer ou não, e pra onde (tela, arquivo), sem mudar o código.

_MODELOS_ARGOS_INSTALADOS = set()
# Um "set" (conjunto) guarda itens sem repetir e sem ordem -- aqui, guarda
# quais pares de idioma (ex.: francês->português) já foram confirmados como
# instalados, pra não checar de novo toda vez (mais rápido).

# O deep-translator (biblioteca usada aqui) raspa a busca gratuita
# (não-oficial) do Google Translate: a mesma frase pode falhar e funcionar
# em chamadas seguidas (visto na prática). Vale tentar de novo antes de
# cair pro offline por causa de uma falha passageira.
TENTATIVAS_ONLINE = 3
ESPERA_ENTRE_TENTATIVAS = 1.0

# O MyMemoryTranslator (outro serviço online) quer o nome do idioma por
# extenso ("french"), não o código de 2 letras ("fr") que o resto do
# programa usa -- esse dicionário faz essa "tradução" de nome, só pros
# idiomas que os adaptadores realmente produzem (seção 7 do CLAUDE.md: cada
# adaptador novo grava idioma_origem em Item.extra ao encontrar um).
_MAPA_MYMEMORY = {
    "fr": "french", "de": "german", "en": "english",
    "la": "latin", "el": "greek", "pt": "portuguese",
}


class ErroTraducao(Exception):
    # Tipo de erro próprio pra esse arquivo -- ver adapters/gallica.py
    # (RespostaVaziaInesperadaError) pra uma explicação de por que criar um
    # tipo de erro próprio, em vez de usar um erro genérico do Python.
    pass


def traduzir(texto, idioma_origem="auto", idioma_destino="pt"):
    """Função principal deste arquivo -- é ela que o resto do programa
    chama. "idioma_origem='auto'" quer dizer que, se ninguém disser qual é
    o idioma original, o serviço online tenta adivinhar sozinho."""
    if not texto or not texto.strip():
        return ""  # nada pra traduzir (texto vazio ou só espaços)
    try:
        return _traduzir_online(texto, idioma_origem, idioma_destino)
    except Exception as erro_online:
        logger.warning("Tradução online falhou (%s); tentando offline...", erro_online)
        try:
            return _traduzir_offline(texto, idioma_origem, idioma_destino)
        except Exception as erro_offline:
            logger.error("Tradução offline falhou também (%s); mantendo original.", erro_offline)
            return texto  # nenhum dos dois jeitos funcionou -- devolve o texto original, sem travar o programa


def _traduzir_online(texto, origem, destino):
    """Tenta o Google primeiro (melhor qualidade quando funciona) e, se
    falhar, tenta o MyMemory antes de desistir do caminho online -- o
    MyMemory cobre idiomas (como latim) que o argostranslate offline nem
    tem pacote pra baixar."""
    try:
        return _traduzir_google(texto, origem, destino)
    except Exception as erro_google:
        logger.warning("Google Translate falhou (%s); tentando MyMemory...", erro_google)
        return _traduzir_mymemory(texto, origem, destino)


def _com_retentativas(nome_servico, funcao):
    """Chama funcao() ate TENTATIVAS_ONLINE vezes -- os dois servicos gratuitos
    (Google e MyMemory) tem o mesmo comportamento na pratica: a mesma frase
    falha e funciona em chamadas diferentes."""
    # "funcao" aqui é um parâmetro que É UMA FUNÇÃO (não um valor comum) --
    # em Python, dá pra passar uma função como argumento de outra função,
    # e essa aqui embrulha a chamada com a lógica de "tenta de novo se falhar".
    ultimo_erro = None
    for tentativa in range(1, TENTATIVAS_ONLINE + 1):
        try:
            return funcao()
        except Exception as erro:
            ultimo_erro = erro
            if tentativa < TENTATIVAS_ONLINE:
                logger.warning("Tentativa %d/%d de tradução online (%s) falhou (%s); tentando de novo...",
                                tentativa, TENTATIVAS_ONLINE, nome_servico, erro)
                time.sleep(ESPERA_ENTRE_TENTATIVAS)
    raise ultimo_erro  # todas as tentativas falharam -- repassa o último erro pra quem chamou decidir o que fazer


def _traduzir_google(texto, origem, destino):
    from deep_translator import GoogleTranslator
    # O "import" está aqui DENTRO da função (não no topo do arquivo) de
    # propósito -- só carrega essa biblioteca se essa função for realmente
    # chamada, economizando tempo de inicialização do programa quando ela
    # não é necessária.
    tradutor = GoogleTranslator(source=origem, target=destino)
    return _com_retentativas("Google", lambda: tradutor.translate(texto))
    # "lambda: tradutor.translate(texto)" cria uma função anônima
    # (sem nome, de uma linha só) que _com_retentativas vai chamar; é um
    # jeito curto de "empacotar" essa chamada pra passar como argumento.


def _traduzir_mymemory(texto, origem, destino):
    if origem not in _MAPA_MYMEMORY:
        raise ErroTraducao(f"MyMemory precisa de um idioma de origem conhecido, recebi '{origem}'")
    from deep_translator import MyMemoryTranslator
    nome_origem = _MAPA_MYMEMORY[origem]
    nome_destino = _MAPA_MYMEMORY.get(destino, destino)
    tradutor = MyMemoryTranslator(source=nome_origem, target=nome_destino)
    return _com_retentativas("MyMemory", lambda: tradutor.translate(texto))


def _traduzir_offline(texto, origem, destino):
    if origem == "auto":
        raise ErroTraducao("argostranslate exige o idioma de origem explícito, não 'auto'")
    _garantir_modelo_argos(origem, destino)
    import argostranslate.translate
    return argostranslate.translate.translate(texto, origem, destino)


def _garantir_modelo_argos(origem, destino):
    """Garante que exista um caminho origem->destino instalado no argostranslate.
    A maioria dos pares só existe via inglês (ex.: não há fr->pt direto, só
    fr->en e en->pt) — o próprio argostranslate junta os dois sozinho (monta
    uma "tradução composta") uma vez que ambos os pacotes estejam instalados,
    então só precisamos garantir que os pacotes certos existam."""
    chave = (origem, destino)  # uma "tupla" (par de valores agrupados) usada como identificador único desse par de idiomas
    if chave in _MODELOS_ARGOS_INSTALADOS:
        return  # já confirmamos antes que esse par está pronto -- não precisa checar de novo

    import argostranslate.package
    import argostranslate.translate

    instalados = {(p.from_code, p.to_code) for p in argostranslate.package.get_installed_packages()}
    # isso é uma "set comprehension" -- monta um conjunto (set) de tuplas
    # (origem, destino) a partir de cada pacote que já está instalado
    if chave in instalados:
        _MODELOS_ARGOS_INSTALADOS.add(chave)
        return

    if origem != "en" and destino != "en":
        # nenhum dos dois é inglês -- precisa instalar em duas etapas,
        # passando pelo inglês como "ponte" (origem->inglês, inglês->destino)
        _instalar_pacote_argos(origem, "en")
        _instalar_pacote_argos("en", destino)
    else:
        _instalar_pacote_argos(origem, destino)

    argostranslate.translate.get_installed_languages.cache_clear()
    # limpa uma "memória guardada" (cache) interna do argostranslate, pra
    # ele perceber o pacote novo que acabamos de instalar
    _MODELOS_ARGOS_INSTALADOS.add(chave)


def _instalar_pacote_argos(origem, destino):
    """Instala o pacote direto origem->destino, se ainda nao estiver instalado."""
    import argostranslate.package

    if any(p.from_code == origem and p.to_code == destino
           for p in argostranslate.package.get_installed_packages()):
        return  # já está instalado, não precisa baixar de novo
    argostranslate.package.update_package_index()  # atualiza a lista de pacotes disponíveis pra download
    candidatos = [
        p for p in argostranslate.package.get_available_packages()
        if p.from_code == origem and p.to_code == destino
    ]
    if not candidatos:
        raise ErroTraducao(f"Nenhum pacote de tradução {origem}->{destino} disponível no argostranslate")
    argostranslate.package.install_from_path(candidatos[0].download())
