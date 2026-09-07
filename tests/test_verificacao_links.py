# -*- coding: utf-8 -*-
"""Testes de regressao: a logica de verificar_links.py migrou pra
core/verificacao_links.py sem mudar de comportamento. Nada aqui toca rede
de verdade -- requests.head/get sao substituidos por dublês (mocks)."""
import subprocess
import sys
from unittest.mock import MagicMock, patch

from buscador.core import verificacao_links as vl


def _resposta(status_code=200, content_type="", corpo=b""):
    r = MagicMock()
    r.status_code = status_code
    r.headers = {"Content-Type": content_type}
    r.raw.read.return_value = corpo
    return r


def test_host_de():
    assert vl.host_de("https://exemplo.com/pagina") == "exemplo.com"
    assert vl.host_de("nao-e-url") == ""


def test_login_host_nunca_chama_rede():
    with patch.object(vl.requests, "head") as head, patch.object(vl.requests, "get") as get:
        texto, categoria = vl.analisar("https://www.academia.edu/12345/obra")
    assert categoria == "requer login"
    assert texto == "requer login"
    head.assert_not_called()
    get.assert_not_called()


def test_404_e_quebrado():
    with patch.object(vl.requests, "head", return_value=_resposta(404)):
        texto, categoria = vl.analisar("https://exemplo.com/sumiu.pdf")
    assert categoria == "quebrado"


def test_403_no_head_cai_para_login_via_get():
    # servidor recusa HEAD (403) -> o codigo tenta de novo, agora com GET
    with patch.object(vl.requests, "head", return_value=_resposta(403)), \
         patch.object(vl.requests, "get", return_value=_resposta(403)):
        texto, categoria = vl.analisar("https://exemplo.com/restrito")
    assert categoria == "requer login"


def test_pdf_direto_por_content_type():
    with patch.object(vl.requests, "head", return_value=_resposta(200, "application/pdf")):
        texto, categoria = vl.analisar("https://exemplo.com/obra")
    assert categoria == "verde"
    assert texto == "vivo (pdf direto)"


def test_pdf_encontrado_no_html():
    pagina = _resposta(200, "text/html")
    with patch.object(vl.requests, "head", return_value=pagina), \
         patch.object(vl.requests, "get", return_value=_resposta(200, "text/html", b'<a href="obra.pdf">baixar</a>')):
        texto, categoria = vl.analisar("https://exemplo.com/pagina")
    assert categoria == "verde"
    assert texto == "vivo (pdf na página)"


def test_repositorio_conhecido_e_verde_mesmo_sem_pdf_no_html():
    pagina = _resposta(200, "text/html")
    with patch.object(vl.requests, "head", return_value=pagina), \
         patch.object(vl.requests, "get", return_value=_resposta(200, "text/html", b"<p>sem link nenhum</p>")):
        texto, categoria = vl.analisar("https://gallica.bnf.fr/ark:/obra")
    assert categoria == "verde"
    assert texto == "vivo (repositório)"


def test_vivo_sem_pdf_fica_branco():
    pagina = _resposta(200, "text/html")
    with patch.object(vl.requests, "head", return_value=pagina), \
         patch.object(vl.requests, "get", return_value=_resposta(200, "text/html", b"<p>nada aqui</p>")):
        texto, categoria = vl.analisar("https://exemplo.com/pagina")
    assert categoria == "branco"
    assert texto == "vivo (sem pdf)"


def test_classificar_tipo():
    assert vl.classificar_tipo("requer login", "requer login") == "precisa login"
    assert vl.classificar_tipo("quebrado", "quebrado") == "quebrado"
    assert vl.classificar_tipo("vivo (pdf direto)", "verde") == "pdf direto"
    assert vl.classificar_tipo("vivo (repositório)", "verde") == "página"
    assert vl.classificar_tipo("vivo (sem pdf)", "branco") == "página"


def test_script_raiz_continua_importavel():
    raiz = __import__("pathlib").Path(__file__).resolve().parent.parent
    resultado = subprocess.run(
        [sys.executable, "-c", "import verificar_links"],
        cwd=raiz, capture_output=True, text=True,
    )
    assert resultado.returncode == 0, resultado.stderr
