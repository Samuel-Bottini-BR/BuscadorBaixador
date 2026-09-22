# -*- coding: utf-8 -*-
"""
Descoberta da URL real de download de uma página da Gallica.

O botão "baixar PDF" do site da Gallica não é uma API documentada: é um
endpoint interno de AJAX que o próprio visualizador do site usa
internamente. Dado um "ark id" (identificador canônico da obra, ver
chaves_gallica.py) e um índice de página, esse endpoint devolve um JSON
com a URL de verdade de onde baixar o conteúdo daquela página.

O campo com a URL se chama "downoaldurl" -- sim, com o "a" e o "l"
trocados de lugar; é erro de digitação da própria Gallica, não nosso (já
confirmado e documentado no HANDOFF.md do projeto).

Confirmado ao vivo (Tarefa C1): o campo NÃO vem no nível mais alto do
JSON -- ele vem enterrado dentro de uma estrutura de "fragmentos" da
interface do visualizador (algo como
fragment.contenu.SideBarFragment.contenu.DownloadFragment.contenu.libelles.downoaldurl).
Por isso a busca abaixo é recursiva em vez de acessar um caminho fixo: é
mais resistente a mudanças de profundidade que a Gallica venha a fazer
nessa estrutura interna (que não é uma API documentada).
"""

BASE_AJAX_DOWNLOAD = "https://gallica.bnf.fr/services/ajax/action/download/ark:/12148/{ark_id}/f{indice_pagina}.item"


def montar_url_ajax_download(ark_id: str, indice_pagina: int = 1) -> str:
    """Monta a URL do endpoint interno de download da Gallica pra uma página.

    Args:
        ark_id: identificador canônico da obra (ex.: "bpt6k6382082m").
        indice_pagina: número da página dentro da obra (1 = primeira).

    Returns:
        A URL do endpoint de AJAX de download pra essa página.
    """
    return BASE_AJAX_DOWNLOAD.format(ark_id=ark_id, indice_pagina=indice_pagina)


def _procurar_downoaldurl(dados):
    """Procura a chave "downoaldurl" em qualquer nível de um JSON (dict/list
    aninhado à vontade) e devolve o primeiro valor achado, ou None se não
    achar em lugar nenhum."""
    if isinstance(dados, dict):
        if "downoaldurl" in dados:
            return dados["downoaldurl"]
        for valor in dados.values():
            encontrado = _procurar_downoaldurl(valor)
            if encontrado is not None:
                return encontrado
    elif isinstance(dados, list):
        for item in dados:
            encontrado = _procurar_downoaldurl(item)
            if encontrado is not None:
                return encontrado
    return None


def descobrir_url_download(ark_id: str, cliente, indice_pagina: int = 1) -> str:
    """Descobre a URL real de download de uma página da Gallica.

    Faz um GET no endpoint interno de AJAX (via ClienteEducado, respeitando
    o intervalo educado entre pedidos) e devolve o campo "downoaldurl" do
    JSON de resposta -- é a URL de onde baixar o conteúdo de verdade dessa
    página (fora do site principal da Gallica, normalmente).

    Args:
        ark_id: identificador canônico da obra.
        cliente: um ClienteEducado (ou objeto com um método .get(url)
            compatível) pra fazer o pedido HTTP.
        indice_pagina: número da página dentro da obra (1 = primeira).

    Returns:
        A URL real de download dessa página.

    Raises:
        ValueError: se o campo "downoaldurl" não vier na resposta.
    """
    url_ajax = montar_url_ajax_download(ark_id, indice_pagina)
    resposta = cliente.get(url_ajax)
    dados = resposta.json()
    url_download = _procurar_downoaldurl(dados)
    if url_download is None:
        raise ValueError(
            f"Resposta do endpoint de download da Gallica sem o campo "
            f"'downoaldurl' esperado (ark_id={ark_id!r}, indice_pagina={indice_pagina!r}): {dados!r}"
        )
    return url_download
