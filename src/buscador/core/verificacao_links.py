# -*- coding: utf-8 -*-
"""
Verificacao de links: testa se uma URL esta viva, quebrada, exige login, ou
tem PDF baixavel. Extraido de verificar_links.py para ser reaproveitado pelos
adaptadores do motor (Fase 1) sem duplicar a logica.
"""
import re

import requests
from openpyxl.styles import PatternFill

requests.packages.urllib3.disable_warnings()

TIMEOUT = 12
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
LOGIN_HOSTS = ("academia.edu", "drive.google.com", "docs.google.com", "jstor.org", "researchgate.net")
# repositórios de texto integral: se estiver vivo, assume-se que há PDF (mesmo sem "ver" no HTML)
REPO_HOSTS = ("persee.fr", "archives-ouvertes.fr", "raco.cat", "revues.org", "openedition",
              "oapen.org", "unesdoc.unesco.org", "collectionscanada.gc.ca", "thesescanada",
              "archipel.uqam.ca", "theses.univ-lyon2.fr", "gallica.bnf.fr", "digidol.llgc.org.uk",
              "gipuzkoakultura.net", "nauticalarch.org", "bibnum.enc.sorbonne.fr")
PDF_RE = re.compile(r'\.pdf(["\'?#)\s]|$)', re.I)

COR = {
    "quebrado":     PatternFill("solid", fgColor="FFC7CE"),  # vermelho
    "requer login": PatternFill("solid", fgColor="BDD7EE"),  # azul
    "verde":        PatternFill("solid", fgColor="C6EFCE"),  # verde
}


def host_de(url):
    try: return url.split("/")[2].lower()
    except Exception: return ""


def tem_login(host):
    return any(h in host for h in LOGIN_HOSTS)


def eh_repo(host):
    return any(h in host for h in REPO_HOSTS)


def analisar(url):
    """Retorna (status_texto, categoria) onde categoria in {quebrado,requer login,verde,branco}."""
    host = host_de(url)
    if tem_login(host):
        return "requer login", "requer login"
    try:
        # 1) status + tipo de conteúdo (HEAD; se recusado, GET)
        r = None
        try:
            r = requests.head(url, timeout=TIMEOUT, allow_redirects=True,
                              headers={"User-Agent": UA}, verify=False)
            if r.status_code in (405, 501, 403):  # muitos servidores recusam HEAD
                r = None
        except requests.exceptions.SSLError:
            return "vivo (ssl)", "branco"
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
            r = None

        if r is None:
            try:
                r = requests.get(url, timeout=TIMEOUT, allow_redirects=True,
                                 headers={"User-Agent": UA}, verify=False, stream=True)
            except requests.exceptions.SSLError:
                return "vivo (ssl)", "branco"
            except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
                return "quebrado", "quebrado"

        code = r.status_code
        ct = (r.headers.get("Content-Type") or "").lower()
        if code in (401, 403, 429):
            try: r.close()
            except Exception: pass
            return "requer login", "requer login"
        if code == 404 or code == 410 or code >= 500:
            try: r.close()
            except Exception: pass
            return "quebrado", "quebrado"
        if not (200 <= code < 400):
            try: r.close()
            except Exception: pass
            return "quebrado", "quebrado"

        # vivo. É PDF direto?
        if url.lower().split("?")[0].endswith(".pdf") or "application/pdf" in ct:
            try: r.close()
            except Exception: pass
            return "vivo (pdf direto)", "verde"

        # baixa um pedaço do HTML e procura link .pdf
        html = ""
        try:
            g = requests.get(url, timeout=TIMEOUT, allow_redirects=True,
                             headers={"User-Agent": UA}, verify=False, stream=True)
            if "application/pdf" in (g.headers.get("Content-Type") or "").lower():
                g.close(); return "vivo (pdf direto)", "verde"
            chunk = g.raw.read(600000, decode_content=True) or b""
            html = chunk.decode("utf-8", "ignore")
            g.close()
        except Exception:
            html = ""
        if PDF_RE.search(html):
            return "vivo (pdf na página)", "verde"
        # regra extra: repositório conhecido de texto integral
        if eh_repo(host):
            return "vivo (repositório)", "verde"
        return "vivo (sem pdf)", "branco"
    except Exception:
        return "quebrado", "quebrado"


def classificar_tipo(status_texto, categoria):
    """Mapeia o resultado de analisar() para o rotulo da coluna 'tipo' da planilha."""
    if categoria == "requer login":
        return "precisa login"
    if categoria == "quebrado":
        return "quebrado"
    if status_texto == "vivo (pdf direto)":
        return "pdf direto"
    return "página"
