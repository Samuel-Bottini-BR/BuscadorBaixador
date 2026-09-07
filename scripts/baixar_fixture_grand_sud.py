# -*- coding: utf-8 -*-
"""Script descartavel: baixa UMA pagina real do forum Grand Sud Medieval e
salva como fixture de teste (tests/fixtures/grand_sud/), pra nao depender
de internet nos testes automatizados. Roda so quando a fixture precisa ser
criada ou renovada (ex.: o forum mudou de layout) -- nao faz parte do motor.
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "src"))

from buscador.core.http_educado import ClienteEducado

USER_AGENT = (
    "BuscadorBaixador-InstitutoSaoBento/0.1 "
    "(uso não comercial, preservação de obras; contato: artesacra.quotidianus@gmail.com)"
)

URL = "https://grand-sud-medieval.fr/forum/viewtopic.php?f=14&t=9264"
DESTINO = pathlib.Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "grand_sud" / "viewtopic_f14_t9264_p1.html"


def main():
    cliente = ClienteEducado(USER_AGENT)
    resposta = cliente.get(URL)
    resposta.encoding = resposta.apparent_encoding or "utf-8"
    DESTINO.parent.mkdir(parents=True, exist_ok=True)
    DESTINO.write_text(resposta.text, encoding="utf-8")
    print(f"Salvo: {DESTINO} ({len(resposta.text)} caracteres)")


if __name__ == "__main__":
    main()
