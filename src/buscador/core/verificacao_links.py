# -*- coding: utf-8 -*-
"""
Verificação de links: testa se uma URL está viva, quebrada, exige login, ou
tem PDF baixável. Extraído de um script mais antigo (verificar_links.py)
pra ser reaproveitado pelos adaptadores do motor (Fase 1) sem duplicar a
lógica -- ou seja, em vez de cada adaptador escrever de novo como checar um
link, todos usam esta função "analisar" daqui.
"""
import re  # "regex"/expressão regular: linguagem pra descrever padrões de texto (usado aqui pra achar ".pdf" no meio de um texto)

import requests
from openpyxl.styles import PatternFill  # cor de fundo de célula, pra pintar a planilha depois

requests.packages.urllib3.disable_warnings()
# Desliga um aviso chato que a biblioteca requests mostra toda vez que a
# gente ignora a checagem de certificado de segurança (ver "verify=False"
# mais abaixo) -- não desliga a checagem em si, só o aviso repetido.

TIMEOUT = 12  # depois de quantos segundos desistir de esperar resposta de um site
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
# "UA" = User-Agent -- aqui, diferente do ClienteEducado, usamos um
# User-Agent de navegador comum, porque essa checagem é só pra ver se o
# link funciona (não é raspagem de conteúdo em massa de um site).

# Sites conhecidos que exigem login pra ver o conteúdo -- se o link for de
# um desses, nem tenta acessar, já marca direto como "requer login".
LOGIN_HOSTS = ("academia.edu", "drive.google.com", "docs.google.com", "jstor.org", "researchgate.net")
# repositórios de texto integral: se estiver vivo, assume-se que há PDF (mesmo sem "ver" no HTML)
REPO_HOSTS = ("persee.fr", "archives-ouvertes.fr", "raco.cat", "revues.org", "openedition",
              "oapen.org", "unesdoc.unesco.org", "collectionscanada.gc.ca", "thesescanada",
              "archipel.uqam.ca", "theses.univ-lyon2.fr", "gallica.bnf.fr", "digidol.llgc.org.uk",
              "gipuzkoakultura.net", "nauticalarch.org", "bibnum.enc.sorbonne.fr")
PDF_RE = re.compile(r'\.pdf(["\'?#)\s]|$)', re.I)
# Esse "regex" (expressão regular) procura ".pdf" seguido de um desses
# caracteres (aspas, interrogação, parêntese, espaço) ou do fim do texto --
# assim acha ".pdf" de verdade num link, sem confundir com uma palavra que
# só por acaso contém essas letras no meio.

# Cores de fundo pra pintar a linha da planilha de acordo com o resultado
# (PatternFill é a forma que a biblioteca openpyxl usa pra descrever "solid"
# = preenchimento sólido, e o código de cor em hexadecimal).
COR = {
    "quebrado":     PatternFill("solid", fgColor="FFC7CE"),  # vermelho
    "requer login": PatternFill("solid", fgColor="BDD7EE"),  # azul
    "verde":        PatternFill("solid", fgColor="C6EFCE"),  # verde
}


def host_de(url):
    """Pega só o domínio de uma URL (ex.: de "https://site.com/pagina"
    devolve "site.com")."""
    try: return url.split("/")[2].lower()
    except Exception: return ""
    # ".split("/")" quebra a URL em pedaços usando "/" como separador; o
    # pedaço [2] é o domínio (o [0] e [1] são "https:" e "" -- o espaço
    # vazio entre as duas barras "//"). Se a URL for esquisita e não tiver
    # esse formato, devolve texto vazio em vez de quebrar o programa.


def tem_login(host):
    return any(h in host for h in LOGIN_HOSTS)
    # "any(...)" devolve True se PELO MENOS UM dos itens da lista bater


def eh_repo(host):
    return any(h in host for h in REPO_HOSTS)


def analisar(url):
    """Retorna (status_texto, categoria) onde categoria in {quebrado,requer login,verde,branco}."""
    host = host_de(url)
    if tem_login(host):
        return "requer login", "requer login"
    try:
        # 1) status + tipo de conteúdo (HEAD; se recusado, GET)
        # "HEAD" é um tipo de pedido HTTP que pergunta só a "ficha técnica"
        # da página (existe? qual o tipo de conteúdo?), sem baixar o
        # conteúdo inteiro -- mais rápido que "GET" quando só queremos checar.
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
            # o HEAD não funcionou -- tenta de novo com GET (pede o conteúdo de verdade)
            try:
                r = requests.get(url, timeout=TIMEOUT, allow_redirects=True,
                                 headers={"User-Agent": UA}, verify=False, stream=True)
                # "stream=True" faz o Python NÃO baixar a resposta inteira de
                # uma vez -- vamos ler só um pedacinho dela mais abaixo, pra
                # não gastar tempo/internet baixando uma página enorme
                # inteira só pra checar se ela tem link de PDF.
            except requests.exceptions.SSLError:
                return "vivo (ssl)", "branco"
            except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
                return "quebrado", "quebrado"

        code = r.status_code  # o código de status HTTP (200 = ok, 404 = não achado, etc.)
        ct = (r.headers.get("Content-Type") or "").lower()  # o tipo do conteúdo (ex.: "application/pdf")
        if code in (401, 403, 429):
            # 401/403 = acesso negado (não autorizado/proibido); 429 = excesso de pedidos.
            # Aqui a gente trata esses três como "provavelmente precisa de login".
            try: r.close()
            except Exception: pass
            return "requer login", "requer login"
        if code == 404 or code == 410 or code >= 500:
            # 404 = não encontrado; 410 = removido de propósito; 5xx = erro do lado do servidor
            try: r.close()
            except Exception: pass
            return "quebrado", "quebrado"
        if not (200 <= code < 400):
            # qualquer outro código fora da faixa "deu certo" (200-399) também conta como quebrado
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
            # lê só os primeiros 600.000 bytes (cerca de 600 KB) do HTML --
            # o suficiente pra achar um link de PDF sem baixar a página inteira
            html = chunk.decode("utf-8", "ignore")
            # transforma os bytes brutos baixados em texto legível;
            # "ignore" descarta qualquer trechinho que não conseguir
            # decodificar direito, em vez de travar o programa por causa disso
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
        # qualquer erro inesperado que não foi previsto acima -- em vez de
        # travar o programa inteiro, marca esse link como quebrado e segue
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
