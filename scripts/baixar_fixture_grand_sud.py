# -*- coding: utf-8 -*-
"""Script descartavel: baixa paginas reais do forum Grand Sud Medieval e
salva como fixture de teste (tests/fixtures/grand_sud/), pra nao depender
de internet nos testes automatizados. Roda so quando uma fixture precisa
ser criada ou renovada (ex.: o forum mudou de layout) -- nao faz parte do
motor. Usa o ClienteEducado (mesmo intervalo/User-Agent do adaptador).
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "src"))

from buscador.core.http_educado import ClienteEducado

USER_AGENT = (
    "BuscadorBaixador-InstitutoSaoBento/0.1 "
    "(uso não comercial, preservação de obras; contato: artesacra.quotidianus@gmail.com)"
)

RAIZ_FIXTURES = pathlib.Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "grand_sud"

# (url, nome do arquivo) -- topico t=9264 tem 1 pagina so (caso "sem paginacao");
# topico t=10425 tem 2 paginas (caso "com paginacao").
FIXTURES = [
    ("https://grand-sud-medieval.fr/forum/viewtopic.php?f=14&t=9264", "viewtopic_f14_t9264_p1.html"),
    ("https://grand-sud-medieval.fr/forum/viewtopic.php?f=14&t=10425", "viewtopic_f14_t10425_p1.html"),
    ("https://grand-sud-medieval.fr/forum/viewtopic.php?f=14&t=10425&start=15", "viewtopic_f14_t10425_p2.html"),
]


def main():
    cliente = ClienteEducado(USER_AGENT)
    RAIZ_FIXTURES.mkdir(parents=True, exist_ok=True)
    for url, nome_arquivo in FIXTURES:
        destino = RAIZ_FIXTURES / nome_arquivo
        resposta = cliente.get(url)
        resposta.encoding = resposta.apparent_encoding or "utf-8"
        destino.write_text(resposta.text, encoding="utf-8")
        print(f"Salvo: {destino} ({len(resposta.text)} caracteres)")


if __name__ == "__main__":
    main()
