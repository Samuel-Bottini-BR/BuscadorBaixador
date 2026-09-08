# -*- coding: utf-8 -*-
"""Traducao automatica hibrida: tenta um servico online (melhor qualidade)
e cai para um tradutor offline se nao houver internet ou o servico falhar.
Nunca lanca para quem chama -- se as duas vias falharem, devolve o texto
original em vez de travar o resto do pipeline."""
import logging
import time

logger = logging.getLogger(__name__)

_MODELOS_ARGOS_INSTALADOS = set()

# O deep-translator raspa a busca gratuita (nao-oficial) do Google Translate:
# a mesma frase pode falhar e funcionar em chamadas seguidas (visto na pratica).
# Vale tentar de novo antes de cair pro offline por causa de uma falha passageira.
TENTATIVAS_ONLINE = 3
ESPERA_ENTRE_TENTATIVAS = 1.0

# O MyMemoryTranslator quer o nome do idioma por extenso, nao o codigo ISO.
# So os idiomas que os adaptadores realmente produzem (secao 7 do CLAUDE.md:
# cada adaptador novo grava idioma_origem em Item.extra ao encontrar um).
_MAPA_MYMEMORY = {
    "fr": "french", "de": "german", "en": "english",
    "la": "latin", "el": "greek", "pt": "portuguese",
}


class ErroTraducao(Exception):
    pass


def traduzir(texto, idioma_origem="auto", idioma_destino="pt"):
    if not texto or not texto.strip():
        return ""
    try:
        return _traduzir_online(texto, idioma_origem, idioma_destino)
    except Exception as erro_online:
        logger.warning("Tradução online falhou (%s); tentando offline...", erro_online)
        try:
            return _traduzir_offline(texto, idioma_origem, idioma_destino)
        except Exception as erro_offline:
            logger.error("Tradução offline falhou também (%s); mantendo original.", erro_offline)
            return texto


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
    raise ultimo_erro


def _traduzir_google(texto, origem, destino):
    from deep_translator import GoogleTranslator
    tradutor = GoogleTranslator(source=origem, target=destino)
    return _com_retentativas("Google", lambda: tradutor.translate(texto))


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
    chave = (origem, destino)
    if chave in _MODELOS_ARGOS_INSTALADOS:
        return

    import argostranslate.package
    import argostranslate.translate

    instalados = {(p.from_code, p.to_code) for p in argostranslate.package.get_installed_packages()}
    if chave in instalados:
        _MODELOS_ARGOS_INSTALADOS.add(chave)
        return

    if origem != "en" and destino != "en":
        _instalar_pacote_argos(origem, "en")
        _instalar_pacote_argos("en", destino)
    else:
        _instalar_pacote_argos(origem, destino)

    argostranslate.translate.get_installed_languages.cache_clear()
    _MODELOS_ARGOS_INSTALADOS.add(chave)


def _instalar_pacote_argos(origem, destino):
    """Instala o pacote direto origem->destino, se ainda nao estiver instalado."""
    import argostranslate.package

    if any(p.from_code == origem and p.to_code == destino
           for p in argostranslate.package.get_installed_packages()):
        return
    argostranslate.package.update_package_index()
    candidatos = [
        p for p in argostranslate.package.get_available_packages()
        if p.from_code == origem and p.to_code == destino
    ]
    if not candidatos:
        raise ErroTraducao(f"Nenhum pacote de tradução {origem}->{destino} disponível no argostranslate")
    argostranslate.package.install_from_path(candidatos[0].download())
