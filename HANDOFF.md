# Buscador e Baixador — estado atual

## O que é e para quem

Aplicativo local (Windows) para o Instituto São Bento achar, baixar e
catalogar obras digitalizadas (livros esgotados, artigos) espalhadas em
sites e fóruns. Usuários: Samuel e o Kaique (leigo, sem formação técnica —
interface precisa ser simples, em português). Regras completas do projeto,
arquitetura e protocolo de decisões estão em `CLAUDE.md` — leia lá primeiro.

## Estado atual

**Fase 1 ("mapear um site → planilha") concluída.** Dado uma URL (tópico do
fórum Grand Sud) ou uma consulta (autor/título na DDB), o programa varre,
verifica cada link (vivo/quebrado/precisa login), traduz o título, e gera
uma planilha `.xlsx` em `saidas/` — com linha colorida por status e dropdown
de avaliação, no mesmo estilo do `Garimpo_GSM_MESTRE_VERIFICADO.xlsx`.

Rodado de verdade contra o fórum Grand Sud (tópico "Les jongleurs"): 7 itens
encontrados, links verificados corretamente (2 quebrados de verdade, 1
repositório reconhecido, PDFs diretos), planilha gerada em `saidas/`.

- Repositório: https://github.com/Samuel-Bottini-BR/BuscadorBaixador
  (branch de trabalho: `feat/fase1-mapeador`, 9 commits, tudo com `pytest`
  passando a cada um — 61 testes no total).
- Pacote Python instalável (`pyproject.toml`, `src/buscador/`), `.venv` com
  Python 3.12 (instalado à parte do 3.14 global, por causa do `argostranslate`).
- `PhpbbAdapter` (fórum, com paginação) e `DdbAdapter` (API da DDB, com
  paginação por offset) prontos e testados.
- zvdd.de foi descartado como caso de teste (ver seção 12 do CLAUDE.md) e
  fica só como adaptador futuro opcional, por lista de PPN manual.

## Pendências conhecidas (não bloqueiam, mas valem nota)

- **Chave da API da DDB:** Samuel ainda não se cadastrou em "Meine DDB"
  (https://www.deutsche-digitale-bibliothek.de/user/register). O `DdbAdapter`
  está pronto e testado com fixture sintética, mas nunca rodou contra a API
  de verdade. Guardar a chave em `DDB_API_KEY` (variável de ambiente) ou
  `buscador.local.cfg` (nunca no código).
- **Schema da resposta da DDB não confirmado:** os nomes de campo
  (`title`, `creator`, `provider`, `time`, `language`) em
  `src/buscador/adapters/ddb.py` vieram de documentação pública (a API não
  responde nada sem chave, nem pra conferir o formato) — ajustar essas
  constantes no topo do arquivo assim que houver uma resposta real.
- **Tradução online instável:** o `deep-translator` (busca gratuita do
  Google) falhou consistentemente para várias frases reais nesta sessão
  (mesma frase falha e funciona em chamadas diferentes). O fallback offline
  (`argostranslate`, via pivô por inglês: fr→en→pt) funciona e já foi
  testado de verdade — mas vale ficar de olho se isso for um padrão.
- **`_extrair_titulo_topico` do PhpbbAdapter** usa `h2 a` — confirmado contra
  duas fixtures reais, mas só foi testado no layout atual do fórum.

## Decisões fechadas

- `requests` para raspagem educada (Grand Sud, via `ClienteEducado`); `httpx`
  para a API (DDB, sem a mesma exigência de ir devagar).
- Tradução híbrida: `deep-translator` (online) com fallback automático pra
  `argostranslate` (offline, pivô por inglês quando não há par direto).
- Empacotamento: pacote instalável de verdade (`pip install -e .`), não
  hack de `sys.path`.
- Ver seções 3 e 7 do CLAUDE.md para o protocolo de decisões e a árvore de
  acesso a sites (nunca burlar robots.txt/paywall/login).
- Regra de check-in: nesta Fase 1, Samuel pediu execução mais autônoma (só
  interromper por erro real ou decisão genuína) — combinado verbalmente,
  **não** alterado no CLAUDE.md ainda. Perguntar se vale formalizar isso lá
  antes da próxima fase.

## O que falta (próximas fases, ver CLAUDE.md seção 10)

- **Fase 2** — baixar os PDFs marcados (inclusive atrás de login já feito
  pelo Samuel).
- **Fase 3** — baixar já organizando por categoria/seção.
- **Fase 4** — catalogar (OCR, bases online, IA opcional).
- **Fase 5** — buscar por nome em todos os sites cadastrados.
- Antes de começar a Fase 2: seguir a seção 4 do CLAUDE.md (plan mode por
  fase) de novo.

## Como rodar

```
D:\programas\BuscadorBaixador\.venv\Scripts\python.exe -m pytest -q
D:\programas\BuscadorBaixador\.venv\Scripts\python.exe -m buscador.cli "https://grand-sud-medieval.fr/forum/viewtopic.php?f=14&t=<ID>"
D:\programas\BuscadorBaixador\.venv\Scripts\python.exe -m buscador.cli "Christophori Clavii" --adapter ddb   # precisa da chave
```
Ou clique duas vezes em `mapear.bat` (usa o `.venv` do projeto direto, não
depende do que estiver no PATH). O `.venv` já está criado com Python 3.12 e
o pacote instalado em modo editável — `pip install -e ".[dev]"` se precisar
reinstalar.
