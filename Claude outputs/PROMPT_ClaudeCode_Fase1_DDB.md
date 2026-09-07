# Prompt para o Claude Code — Projeto "Buscador e Baixador" (Fase 1, via DDB)

> Cole este documento inteiro no Claude Code, com a pasta do projeto aberta em
> `D:\programas\BuscadorBaixador`.
> **Antes de mandar isto, entre no modo _plan mode_** (no Claude Code, aperte
> `Shift+Tab` até aparecer "plan mode") — assim ele planeja tudo comigo antes de
> escrever qualquer arquivo.

## Quem você é nesta tarefa
Você é meu parceiro de programação. **Eu estou aprendendo a programar** — então
explique suas decisões de forma didática, em **português**, e prefira **soluções
simples** às espertas. Trabalhe **um passo de cada vez**.

## Regras que valem para toda a nossa conversa (obrigatórias)
1. **Antes de criar ou alterar qualquer arquivo, me mostre o que vai mudar e
   espere minha confirmação.** Nada de escrever vários arquivos de uma vez sem eu ver.
2. Vá em **fatias pequenas**. Nada de "refatorar tudo de uma vez".
3. A cada passo, explique **o porquê** da escolha e **como testar** que deu certo.
4. Se algo estiver ambíguo, **pergunte** em vez de adivinhar.
5. Commits pequenos e frequentes, com mensagens claras em português.

## Protocolo de decisões (ESSENCIAL — vale para o projeto todo; coloque no CLAUDE.md)
Sempre que aparecer uma **escolha ou um trade-off** (ex.: varrer o HTML vs usar a
API; qual biblioteca usar; onde salvar; que formato de dado), **NÃO decida sozinho.**
Em vez disso:
1. **Sinalize** claramente que ali existe uma decisão.
2. **Explique em termos simples** o que está em jogo — eu quase nunca vou saber que
   a escolha existe se você não me avisar.
3. **Ofereça 2–3 opções**, cada uma com prós e contras curtos.
4. **Recomende uma** e diga por quê.
5. **Espere eu escolher** antes de seguir.
A única exceção são **regras rígidas** (não burlar robots.txt / paywall / CAPTCHA /
login): aí você não me oferece a opção de burlar, mas mesmo assim **explica o porquê**
e me apresenta os caminhos legítimos.

## Cada fase começa no plan mode (coloque isto no CLAUDE.md)
Este projeto tem várias fases. **No começo de cada fase (1, 2, 3, 4, 5…), a primeira
coisa que você faz é me pedir para entrar no _plan mode_** e planejar a fase inteira
comigo antes de escrever código. Só depois de eu aprovar o plano é que a gente
programa.

## O que é o projeto (visão geral)
Um **aplicativo local** (roda no meu PC, Windows), usado por mim e pelo Kaique,
para o Instituto São Bento **achar, baixar e catalogar obras** (livros esgotados,
artigos, digitalizações) espalhadas por vários sites, bibliotecas digitais e fóruns.

Restrições importantes:
- **Sem IA local** (os PCs não aguentam). A IA entra só por um **botão opcional**
  que manda dados para o meu **Claude Pro**. Catalogação automática usa **bases
  on-line gratuitas** (Open Library, Google Books, Calibre), não modelo local.
- **Custo zero** por padrão: tudo com ferramentas **open-source**.
- **Ética/legal:** **não burlar** paywalls, CAPTCHAs ou logins. Só operar em sites
  que **eu cadastrar**. Login é feito **por mim** (fase futura) — nunca senha escrita
  no código. Chaves de API ficam num arquivo de configuração fora do Git, nunca no código.
- **Frontend/dashboard fica para o final.** Agora construímos o "motor" em Python,
  testável por linha de comando.

## Regra de acesso a cada site (árvore de decisão — importante)
Para cada site, o programa decide **como** acessar, nesta ordem:
1. **Ler o `robots.txt` do site primeiro.**
2. Se o site oferece **API oficial** (OAI-PMH, SRU, ou uma API REST como a da DDB) →
   **prefira a API**: é mais leve, estável e educada. **Mas me avise que essa escolha
   existe** e me deixe optar.
3. Se **não há API** e a varredura é **permitida** pelo robots → **varrer o HTML**
   (adaptador genérico ou de fórum, como fizemos no Grand Sud), sendo **educado**:
   1 requisição por vez, atraso de ~2 s, User-Agent honesto, e parar se o servidor recusar.
4. Se o robots **proíbe** a varredura **e não há API** permitida → **me explique e me
   ofereça as opções legítimas** (pular o site, pedir permissão) — nunca burle.

> **Nota sobre o zvdd (o site que eu tinha pedido primeiro):** descobrimos que o
> `robots.txt` do zvdd **proíbe** tanto a busca por HTML (`/dms/search/`) quanto o
> endpoint OAI (`/oai2/`), e além disso o zvdd está sendo **descontinuado**. Por isso
> **não vamos pelo zvdd.** Vamos pela **DDB (Deutsche Digitale Bibliothek)**, que é a
> sucessora oficial, tem **API aberta e liberada**, e **contém o acervo que estava no
> zvdd** (o zvdd era um agregador que alimentava a DDB). Guarde o zvdd só como um
> adaptador futuro de "buscar um item específico pelo código PPN".

## Roteiro completo (documente no CLAUDE.md; construiremos por fases)
- **Fase 1 — Mapear uma fonte → planilha** (ESTA tarefa). Dada uma busca/acervo,
  listar todas as obras/PDFs numa planilha, com: verificação vivo/quebrado/precisa-login
  (cores 🔵🔴🟢), categoria de origem, **título original + tradução PT automática**,
  e um quadrinho de **explicação**.
- **Fase 2 — Baixar** os arquivos marcados.
- **Fase 3 — Baixar já organizando** em pastas pela categoria da Fase 1.
- **Fase 4 — Catalogar fundo:** ler metadados/texto do PDF; **OCR** (OCRmyPDF +
  Tesseract) nos escaneados; conferir em catálogo on-line; botão Claude Pro; separar
  por autor/título/tema, **sempre marcando "palpite, confirme"**.
- **Fase 5 — Buscar por nome:** digitar o nome de um livro e procurar na base de
  fontes cadastradas.
- **Bases (valem para tudo):** dashboard à prova de leigo; gestão de sites + login;
  botão Claude Pro; aviso de "não confiável".
- **Módulo extra (por último):** Telegram.

## Stack sugerida (confirme comigo antes de fixar)
- **Python 3.11+**, ambiente virtual (`.venv`). *(No meu PC hoje só tem o Python 3.14 —
  me avise se isso for um problema e como resolver.)*
- Rede: `httpx` (ou `requests`). HTML (fases futuras): `BeautifulSoup`. Planilha: `openpyxl`.
- Tradução automática (grátis): `argostranslate` (offline) **ou** `deep-translator`
  (me deixe escolher — offline sem internet vs online mais simples).
- Testes: `pytest`.
- (Fases futuras, não instalar agora: `ocrmypdf`+Tesseract, `pypdf`, Calibre CLI, FastAPI/Streamlit.)

## Arquitetura que eu quero (importante para reuso)
O mapeador tem que servir para **vários tipos de fonte**. Use o padrão de
**"adaptadores de site"**:
- uma interface base `SiteAdapter` com métodos como `iter_itens()` e `descrever(item)`;
- um adaptador **específico da DDB** (`DdbAdapter`) que usa a API oficial;
- mais adiante, um adaptador **genérico** (varre HTML) e um de **fórum** (phpBB, como o Grand Sud).
Assim, adicionar uma fonte nova = escrever um adaptador novo, sem mexer no resto.

Aproveite o **`verificar_links.py` que já existe nesta pasta** (ele testa
vivo/quebrado/login/PDF): transforme a lógica dele num módulo reutilizável do motor.

## Contexto que já temos (do garimpo do Grand Sud Médiéval)
Na pasta `...\Projeto São Bento\SITE GRAND SUL MEDIEVAL\GARIMPO` existem **duas
planilhas** que já fizemos à mão/semi-automático e servem de **referência de formato**:
- `Garimpo_GSM_MESTRE.xlsx` — a planilha mestre (abas LEIA-ME, Links, Texto útil,
  Resumo por seção; colunas de grupo, seção, prioridade, obra baixável, tipo, título
  PT, link, destino, autor, status, avaliação humana, com **dropdowns**).
- `..._VERIFICADO.xlsx` — a mesma, já passada pelo verificador de links, com **linhas
  coloridas** e abas "Quebrados" e "Prontos p/ baixar".
A planilha da Fase 1 deve seguir **esse mesmo espírito** (mesmas cores, dropdown de
avaliação humana).

## A API da DDB — o que já levantei (confira e me explique antes de usar)
A DDB tem API REST oficial em `https://api.deutsche-digitale-bibliothek.de`.
Documentação: `https://api.deutsche-digitale-bibliothek.de/OpenAPI` e
`https://github.com/mbuechner/ddbapi`.

- **Chave de API obrigatória.** Eu (humano) vou criar conta gratuita na "Meine DDB"
  e gerar a chave. **Você me guia nesse passo**, mas quem cria a conta sou eu. A chave
  vai num arquivo de config (ex.: `config.local.toml` ou variável de ambiente), **fora
  do Git**.
- Endpoints que interessam:
  - `/search` — a busca. Aceita `query`, `offset`, `rows`, `sort` e **facetas** de filtro.
  - `/items/{id}` — dados de uma obra.
  - `/items/{id}/binaries` e `/binary/{uuid}` — os arquivos em si (fases 2+).
  - `/items/{id}/source` — metadados originais da biblioteca.
- **Faceta importante:** `provider_fct` (filtrar por provedor/fornecedor) e
  `aggregator_id`. É com ela que dá para isolar as obras que vieram do **zvdd**.

## O que construir NESTA fatia (Fase 1), com o caso de teste
**Caso de teste (real):** buscar o autor **"Christophori Clavii"** na DDB via `/search`.

**Entrada da Fase 1:** um termo de busca (ou uma URL/consulta) da fonte.
**Saída da Fase 1:** um arquivo `.xlsx` na pasta `saidas/`, com uma linha por obra e,
no mínimo, as colunas:
`titulo_original`, `titulo_pt`, `autor`, `ano`, `link` (o visualizador da DDB),
`tipo` (pdf direto / página / precisa login), `status_link` (🟢🔵🔴), `explicacao`,
`fonte/biblioteca` (a instituição que digitalizou), `provedor` (ex.: zvdd),
`avaliacao_humana` (vazia, com dropdown). Pinte a linha conforme o status.

**Pronto quando (como testar):**
1. `pytest` passa (testes do parser sobre uma **resposta JSON de exemplo salva** da
   DDB — sem depender da internet nos testes).
2. Rodar o CLI com a busca "Christophori Clavii" gera um `.xlsx` em `saidas/` com as
   obras, títulos traduzidos, status colorido e links que levam ao registro/visualizador.
3. **Teste do zvdd:** rodar a busca **filtrando pela faceta `provider_fct`/`aggregator_id`
   do zvdd** e me mostrar **quantas obras** aparecem — confirmando na prática que o
   acervo do zvdd está mesmo na DDB.
4. Nada de rede nos testes automatizados; a rede só no comando real.

## Boas práticas para montar ANTES de programar (Etapa de organização)
Me proponha (e só execute após eu aprovar):
1. **Estrutura de pastas**, algo como:
   ```
   BuscadorBaixador/
     src/buscador/
       adapters/          # SiteAdapter, DdbAdapter
       core/              # verificação de links, planilha, tradução
       cli.py             # ponto de entrada de linha de comando
     tests/               # testes com pytest (sobre JSON de exemplo salvo)
     saidas/              # planilhas geradas (.gitignore)
     config.local.toml    # a chave da DDB (.gitignore)
     CLAUDE.md
     README.md
     requirements.txt
     .gitignore
   ```
2. **CLAUDE.md** documentando: o que é o projeto, a stack, como rodar/testar, a
   estrutura, as convenções, o **protocolo de decisões**, a **regra de plan mode por
   fase**, o roteiro das fases, e o que NÃO mexer.
3. **Git:** inicializar o repositório (ainda não é um repo), branch por funcionalidade
   (ex.: `feat/fase1-ddb`), e revisar o `.gitignore` (cobrir `.venv/`, `__pycache__/`,
   `*.xlsx`, `saidas/`, `config.local.toml`).
4. **Testes:** começar simples — um teste que roda o parser sobre uma **resposta JSON
   de exemplo salva** da DDB, verificando que ele extrai as obras certas.

## Primeiro passo, agora
**Não escreva código ainda.** No plan mode, comece me apresentando, para eu aprovar:
(a) a estrutura de pastas e o conteúdo do CLAUDE.md;
(b) a lista de dependências;
(c) como você vai acessar a DDB (endpoints, a chave de API, e como testar sem gastar
   rede nos testes automatizados) — incluindo o que você precisa que EU faça (criar a
   conta e gerar a chave) e o passo a passo desse cadastro.
Espere meu "ok" antes de criar qualquer arquivo.
