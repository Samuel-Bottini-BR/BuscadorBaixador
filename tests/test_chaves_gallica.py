# -*- coding: utf-8 -*-
from buscador.core.chaves_gallica import extrair_ark_id


def test_extrai_ark_id_com_http_e_sufixo_f21_item():
    """Link com http:// e sufixo /f21.item."""
    url = "http://gallica.bnf.fr/ark:/12148/btv1b8595063v/f21.item"
    assert extrair_ark_id(url) == "btv1b8595063v"


def test_extrai_ark_id_com_https_e_sufixo_f1_item():
    """Link com https:// e sufixo /f1.item."""
    url = "https://gallica.bnf.fr/ark:/12148/bpt6k9112480c/f1.item"
    assert extrair_ark_id(url) == "bpt6k9112480c"


def test_extrai_ark_id_sem_sufixo():
    """Link sem sufixo após o ark id."""
    url = "http://gallica.bnf.fr/ark:/12148/btv1b8595063v"
    assert extrair_ark_id(url) == "btv1b8595063v"


def test_extrai_ark_id_com_sufixo_f1_image():
    """Link com sufixo /f1.image."""
    url = "https://gallica.bnf.fr/ark:/12148/bpt6k9112480c/f1.image"
    assert extrair_ark_id(url) == "bpt6k9112480c"


def test_devolve_none_para_string_vazia():
    """String vazia deve devolver None."""
    assert extrair_ark_id("") is None


def test_devolve_none_para_none():
    """None como entrada deve devolver None."""
    assert extrair_ark_id(None) is None


def test_devolve_none_quando_nao_tem_padrao():
    """Link sem o padrão ark:/12148/ deve devolver None."""
    url = "http://gallica.bnf.fr/pagina-qualquer"
    assert extrair_ark_id(url) is None


# --- Achado real (sessão da Tarefa C4): links do mapeamento
# (saidas/gallica_mapa_livros.json) que não têm uma "/" logo depois do ark
# id -- a regra antiga só sabia parar na barra, então grudava lixo no
# final do ark id (4.193 dos 26.876 ark ids únicos do mapeamento, ~15%,
# vinham assim). Cada teste abaixo usa um exemplo REAL tirado desse
# arquivo, não inventado. ---------------------------------------------


def test_extrai_ark_id_com_sufixo_item_sem_barra_antes():
    """Achado real: ".item" colado direto no ark id, sem "/" antes (em vez
    do padrão comum "/f21.item")."""
    url = "https://gallica.bnf.fr/ark:/12148/bpt6k6708678d.item"
    assert extrair_ark_id(url) == "bpt6k6708678d"


def test_extrai_ark_id_ignora_parametros_de_busca_apos_interrogacao():
    """Achado real: link com "?rk=..." (parâmetro interno de posição na
    busca da Gallica) colado direto no ark id, sem "/" antes."""
    url = "https://gallica.bnf.fr/ark:/12148/bpt6k6572724s?rk=21459;2"
    assert extrair_ark_id(url) == "bpt6k6572724s"


def test_extrai_ark_id_ignora_fragmento_apos_cerquilha():
    """Achado real: link terminando em "#" (fragmento de URL vazio)."""
    url = "https://gallica.bnf.fr/ark:/12148/bpt6k205338r#"
    assert extrair_ark_id(url) == "bpt6k205338r"


def test_extrai_ark_id_ignora_pontuacao_e_espacos_colados_no_final():
    """Achado real: lixo de raspagem colado no final do link (parêntese de
    fechamento, espaço, espaço não separável \\xa0)."""
    assert extrair_ark_id("http://gallica.bnf.fr/ark:/12148/bpt6k202956q)") == "bpt6k202956q"
    assert extrair_ark_id("https://gallica.bnf.fr/ark:/12148/cb327927542\xa0") == "cb327927542"
    assert extrair_ark_id("https://catalogue.bnf.fr/ark:/12148/cb303132053 ") == "cb303132053"
