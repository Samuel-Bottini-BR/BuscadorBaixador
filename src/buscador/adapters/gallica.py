# -*- coding: utf-8 -*-
"""
Adaptador (ver adapters/base.py) para a Gallica, a biblioteca digital da
BnF (Biblioteca Nacional da França). Diferente do fórum (phpbb.py), a
Gallica tem uma API oficial chamada SRU -- documentada de verdade em
api.bnf.fr, pra qualquer programa usar, sem precisar de chave de acesso.

Mesmo tendo API oficial, ainda seguimos a regra de raspagem educada (seção
7 do CLAUDE.md): 1 requisição de cada vez, com intervalo entre elas,
User-Agent honesto -- por isso usa ClienteEducado, igual o PhpbbAdapter,
e não uma biblioteca mais "rápida" tipo httpx direto (diferente da DDB,
onde não há indicação de que "ir rápido" seja bem-vindo).

Confirmado ao vivo pelo Samuel (não é só documentação lida por mim):
endpoint, parâmetros e formato de resposta abaixo realmente funcionam.
maximumRecords vai de 0 a 50 (limite documentado pela própria BnF).
"""
from urllib.parse import urlencode  # transforma um dicionário de parâmetros em texto de URL (ex.: {"a": "b"} vira "a=b")
import xml.etree.ElementTree as ET  # biblioteca padrão do Python pra ler XML (o formato de resposta que a API da Gallica usa)

from buscador.adapters.base import Item, SiteAdapter
from buscador.core.http_educado import ClienteEducado

USER_AGENT = (
    "BuscadorBaixador-InstitutoSaoBento/0.1 "
    "(uso não comercial, preservação de obras; contato: artesacra.quotidianus@gmail.com)"
)
API_BASE = "https://gallica.bnf.fr/SRU"  # o endereço fixo de toda consulta na API SRU da Gallica
MAXIMO_POR_PAGINA = 50  # limite documentado pela BnF -- pedir mais que isso de uma vez a API recusa

# Palavras que, se aparecerem no campo "direitos" (rights) de um item,
# indicam que a obra já é de domínio público (pode ser usada livremente).
_TERMOS_DOMINIO_PUBLICO = ("domaine public", "domaine publique", "public domain")


def construir_consulta_lote_ark_ids(ark_ids):
    """Monta uma consulta CQL que pede, numa unica chamada, varios itens de
    uma vez pelo identificador ark deles -- em vez de um pedido por item
    (que seria lento e bateria em limite de taxa do site). Confirmado ao
    vivo que a Gallica aceita esse formato com "or" entre varias clausulas
    'dc.identifier all "..."' e devolve todos os registros pedidos numa
    resposta so. O resultado desta funcao vira o "consulta" que o
    GallicaAdapter usa como string opaca (ele nao sabe nem precisa saber
    como o CQL foi montado)."""
    if not ark_ids:
        # Lote vazio nao faz sentido pra consultar -- melhor falhar cedo e
        # claro do que mandar uma consulta vazia pra API.
        raise ValueError("ark_ids nao pode ser uma lista vazia")
    return " or ".join(f'dc.identifier all "ark:/12148/{ark_id}"' for ark_id in ark_ids)


class RespostaVaziaInesperadaError(Exception):
    # "Exception" é a classe base de erros do Python -- criar uma nova
    # classe que herda dela permite ter um TIPO de erro próprio, com nome
    # que já explica o problema, em vez de um erro genérico.
    """Uma pagina no meio da busca voltou sem nenhum registro, mesmo o
    startRecord pedido ainda sendo menor ou igual ao total que a propria
    Gallica declarou -- quase certo que e' uma falha temporaria dela, nao o
    fim real da busca (visto ao vivo: tentar de novo na hora resolveu).
    Quem chama (core/coleta_gallica.py) deve tratar isso como algo pra
    tentar de novo, nunca como 'terminou'."""


class GallicaAdapter(SiteAdapter):  # "herda" (usa como molde) o SiteAdapter -- ver adapters/base.py
    nome = "Gallica (BnF)"

    # Na pratica (testado ao vivo), a Gallica devolve 429 ("Too Many
    # Requests" -- excesso de pedidos) entre paginas com o intervalo padrao
    # de 2s do ClienteEducado -- ela pede mais espaco que o forum do Grand
    # Sud. Mesmo assim, uma segunda pagina pode esbarrar num limite por COTA
    # acumulada (nao so por intervalo) -- por isso os padroes abaixo buscam
    # tudo numa unica pagina sempre que der (ate 50, o maximo documentado
    # pela BnF), evitando paginar sem necessidade.
    INTERVALO_SEGUNDOS = 6.0

    def __init__(self, consulta, cliente=None, max_resultados=MAXIMO_POR_PAGINA,
                 tamanho_pagina=MAXIMO_POR_PAGINA, startrecord_inicial=1):
        # __init__ roda quando a gente CRIA um GallicaAdapter novo.
        self.consulta = consulta  # o texto de busca, no formato CQL que a API SRU entende (ex.: 'gallica all "Clavius"')
        self.cliente = cliente or ClienteEducado(USER_AGENT, intervalo_segundos=self.INTERVALO_SEGUNDOS)
        self.max_resultados = max_resultados
        self.tamanho_pagina = min(tamanho_pagina, MAXIMO_POR_PAGINA)  # nunca deixa passar do limite da BnF, mesmo se alguem pedir mais
        self.startrecord_inicial = startrecord_inicial  # permite retomar de onde parou (coleta longa)
        self.total_ultima_busca = None  # numberOfRecords da ultima chamada -- so informativo

    def iter_itens(self):
        # Achata (transforma em uma sequência única) o resultado de
        # iter_paginas(), que vem página por página, em itens um por um.
        for _inicio_pagina, itens_pagina in self.iter_paginas():
            yield from itens_pagina

    def iter_paginas(self):
        """Gera (inicio_da_pagina, [itens_da_pagina]) -- uma pagina inteira
        de cada vez, em vez de um fluxo achatado de itens. Usado pela coleta
        longa (core/coleta_gallica.py) pra so avancar o checkpoint depois
        que uma pagina inteira foi processada com sucesso."""
        inicio = self.startrecord_inicial  # SRU pagina a partir de 1, nao de 0
        total = None
        while inicio <= self.max_resultados and (total is None or inicio <= total):
            raiz = self._buscar_pagina(inicio, self.tamanho_pagina)
            if total is None:
                total = _texto_como_int(raiz, "numberOfRecords")
                self.total_ultima_busca = total
            registros = _elementos_por_nome_local(raiz, "record")
            if not registros:
                if total == 0 or inicio > total:
                    return  # fim real: ou a busca nao tem nenhum resultado, ou passamos do total
                raise RespostaVaziaInesperadaError(
                    f"Pagina em startRecord={inicio} veio vazia, mas o total declarado e' "
                    f"{total} (ou seja, ainda deveria ter registro aqui)."
                )
            itens_pagina = [self._item_de_registro(registro) for registro in registros]
            yield inicio, itens_pagina
            inicio += len(registros)

    def _buscar_pagina(self, start_record, maximum_records):
        # Monta a URL da API SRU e faz a chamada de verdade.
        params = {
            "operation": "searchRetrieve",  # diz pra API "quero buscar registros"
            "version": "1.2",               # versao do protocolo SRU que estamos usando
            "query": self.consulta,
            "maximumRecords": maximum_records,
            "startRecord": start_record,    # a partir de qual registro comecar (pra paginar)
        }
        url = f"{API_BASE}?{urlencode(params)}"
        resposta = self.cliente.get(url)
        return ET.fromstring(resposta.text)  # transforma o texto XML devolvido numa estrutura navegavel

    def _item_de_registro(self, registro):
        # Extrai cada campo de um <record> do XML e monta um Item (a
        # "caixinha" padrao de achado, definida em adapters/base.py). Os
        # nomes tipo "dc:title", "dc:creator" seguem o padrao Dublin Core,
        # um jeito comum de descrever metadados de obras/documentos.
        titulo = _texto_local(registro, "title")
        autor = _texto_local(registro, "creator") or _texto_local(registro, "contributor")
        ano = _texto_local(registro, "date")
        idioma = _texto_local(registro, "language")
        editora = _texto_local(registro, "publisher")
        descricao = _texto_local(registro, "description")
        direitos = _texto_local(registro, "rights")
        link = _texto_local(registro, "link") or _texto_local(registro, "identifier")
        tipo_doc = _texto_local(registro, "typedoc")

        return Item(
            titulo_original=titulo,
            link=link,
            autor=autor,
            ano=ano,
            explicacao=descricao,
            fonte=editora or self.nome,
            provedor=self.nome,
            dominio_publico=_dominio_publico(direitos),
            url_pagina=link,
            extra={"idioma_origem": _idioma_iso(idioma), "tipo_doc": tipo_doc},
        )


def _elementos_por_nome_local(elemento, nome_local):
    """Acha elementos pelo nome, ignorando o prefixo de namespace (srw:record,
    dc:title, etc.) -- mais simples que declarar todos os namespaces exatos."""
    # Em XML, "namespace" é um prefixo (tipo "dc:") que evita confusão
    # quando duas fontes diferentes usam a mesma palavra pra coisas
    # diferentes. Aqui a gente ignora esse prefixo de propósito, olhando só
    # a parte depois da "}" (é assim que o Python representa o namespace
    # por dentro), pra não ter que escrever o endereço completo de cada um.
    return [e for e in elemento.iter() if e.tag.rsplit("}", 1)[-1] == nome_local]


def _texto_local(elemento, nome_local):
    achados = _elementos_por_nome_local(elemento, nome_local)
    return (achados[0].text or "").strip() if achados and achados[0].text else ""


def _texto_como_int(elemento, nome_local):
    texto = _texto_local(elemento, nome_local)
    return int(texto) if texto.isdigit() else 0


def _dominio_publico(texto_direitos):
    texto = (texto_direitos or "").lower()  # ".lower()" deixa tudo minúsculo, pra comparar sem se importar com maiúscula/minúscula
    return "Sim" if any(t in texto for t in _TERMOS_DOMINIO_PUBLICO) else "Não"


# Mapa de códigos de idioma que a Gallica usa (às vezes em francês, às
# vezes abreviado) para o código de 2 letras que o resto do programa usa
# (padrão ISO 639-1 -- "fr" = francês, "en" = inglês, etc.).
_MAPA_IDIOMA = {
    "fre": "fr", "fra": "fr", "français": "fr", "lat": "la", "latin": "la",
    "eng": "en", "gre": "el", "grc": "el", "greek": "el", "grec": "el",
}


def _idioma_iso(idioma):
    return _MAPA_IDIOMA.get((idioma or "").strip().lower(), "fr")
    # ".get(chave, valor_padrao)": procura a chave no dicionário; se não
    # achar, devolve "fr" (assume francês, já que é o idioma mais comum na
    # Gallica, em vez de quebrar o programa por um idioma desconhecido)
