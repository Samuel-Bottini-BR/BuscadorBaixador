# Projeto "Buscador e Baixador" — Documento-mestre

## 1. Quem você é nesta tarefa
Você é meu parceiro de programação. **Eu estou aprendendo a programar** — então
explique suas decisões de forma **didática, em português**, e prefira **soluções
simples** às espertas. Trabalhe **um passo de cada vez**.

## 2. Regras de trabalho (valem para todo o projeto)
1. **Antes de criar/alterar qualquer arquivo, me mostre o que vai mudar e espere
   minha confirmação.** Nunca escreva vários arquivos de uma vez sem eu ver.
2. Vá em **fatias pequenas**; nada de "refatorar tudo de uma vez".
3. A cada passo, explique **o porquê** e **como testar** que deu certo.
4. Se algo estiver ambíguo, **pergunte** em vez de adivinhar.
5. Commits pequenos e frequentes, mensagens claras em português.

## 3. Protocolo de decisões (ESSENCIAL)
Sempre que houver uma **escolha ou trade-off** (varrer HTML vs API, qual
biblioteca, onde salvar, formato de dado, etc.), **NÃO decida sozinho:**
1. **Sinalize** que ali existe uma decisão.
2. **Explique em termos simples** o que está em jogo (eu quase nunca vou saber que
   a escolha existe se você não avisar).
3. **Ofereça 2–3 opções** com prós e contras curtos.
4. **Recomende uma** e diga por quê.
5. **Espere eu escolher.**
Exceção: **regras rígidas** (não burlar robots.txt / paywall / CAPTCHA / login) —
aí você não me dá a opção de burlar, mas **explica o porquê** e me mostra os
caminhos legítimos (usar API, pular o site, ou eu pedir permissão).

## 4. Como cada fase deve começar (plan mode)
No **início de cada fase (1, 2, 3, ...)**:
1. Peça para eu **ativar o plan mode** do Claude Code.
2. Dentro do plan mode, **apresente o plano da fase** (objetivo, fatias pequenas,
   como testar) — sem escrever código.
3. Eu reviso e aprovo.
4. Só então você **sai do plan mode e executa**, sempre respeitando as regras 2 e 3.

---

## 5. O que é o projeto (visão geral)
Um **aplicativo local** (Windows, roda no meu PC), usado por **mim e pelo Kaique**,
para o **Instituto São Bento** achar, baixar e catalogar obras (livros esgotados,
digitalizações, artigos) espalhadas por vários sites e fóruns. A missão do
Instituto é **preservar obras** e reviver métodos tradicionais de produção de livros.

**Restrições (valem para tudo):**
- **Sem IA local** (os PCs não aguentam). IA só por um **botão opcional** que manda
  dados para o meu **Claude Pro**. Catalogação automática usa **bases on-line
  gratuitas** (Open Library, Google Books, Calibre), não modelo local.
- **Custo zero** por padrão: só **open-source**.
- **Dashboard/frontend fica para o FINAL.** Primeiro o "motor" em Python, testável
  por linha de comando.
- **Ética/legal:** não burlar paywall/CAPTCHA/login; só operar em sites que **eu
  cadastrar**; login feito **por mim, no dashboard** (fase futura), nunca senha no
  código. Acesso a cada site segue a árvore de decisão (seção 7).

## 6. Bases que atravessam todas as fases
- **Dashboard à prova de leigo:** simples, bonito, tudo bem separado (frontend por último).
- **Gestão de sites + login:** eu adiciono um site e faço o login ali no dashboard
  quando ele pede (a maioria é Google); troco de conta sem mexer no código.
- **Botão "mandar pro Claude Pro":** IA só quando eu aperto.
- **Aviso "não confiável":** toda categorização automática vem marcada como palpite;
  o humano confirma.

**Detalhado em 16/09/2026 (ainda não construído, é requisito pro dashboard):**
- **Trocar/escolher o perfil de navegador de dentro do dashboard** — em vez de
  mexer em pasta/configuração na mão. Relacionado: hoje (`core/navegador.py`)
  cada site usa um perfil de Chrome isolado numa pasta própria
  (`sessoes_navegador/<site>/`); o Samuel pediu que desse pra usar um perfil de
  Chrome de verdade (dos que aparecem no seletor de perfis do próprio Chrome),
  não uma pasta escondida — reavaliar esse desenho quando o dashboard existir.
- **Guardar login (email/senha) de um site no backend do app**, só para sites
  que **não impedem login automatizado** (o próprio Samuel definiu essa
  condição), pra reaproveitar depois sem precisar de janela visível toda vez.
  O armazenamento já existe hoje (`core/config_sites.py` + `buscador.local.cfg`,
  já usado pra chave de API — mesmo mecanismo serve pra `email`/`senha` por
  site, sem mudar nada). **O que falta**: o código que pega essa credencial
  guardada e preenche/envia o formulário de login sozinho — isso é
  específico de cada site (nomes de campo, botão, 2FA variam), não dá pra
  fazer genérico; construir por adapter, quando algum precisar disso.

## 7. Regra de acesso a cada site (árvore de decisão)
Para cada site, decida **como** acessar, nesta ordem, **me avisando da escolha**:
1. **Leia o `robots.txt`.**
2. Se a varredura é **permitida** → **varra o HTML normalmente** (adaptador
   genérico/fórum, como no Grand Sud), sendo educado: 1 requisição por vez, atraso
   ~2 s, User-Agent honesto, parar se recusarem. **Este é o caso padrão.**
3. Se o site tem **API oficial** (OAI-PMH, SRU, METS/MODS) → me diga que existe essa
   opção e **deixe eu escolher** entre API e HTML (a API costuma ser mais leve/estável).
4. Se o robots **proíbe** e **não há API** → **me explique e me ofereça as opções
   legítimas** (pular o site, pedir permissão, etc.). Nunca burle.

## 8. Arquitetura
- **Adaptadores de site** (para reuso): uma interface base `SiteAdapter`
  (`iter_itens()`, `descrever(item)`), um adaptador **genérico** (varre páginas e
  acha links/PDFs), e adaptadores **específicos** quando o site tem estrutura própria
  (ex.: fórum phpBB como o Grand Sud) ou API (ex.: `GallicaAdapter`). Adicionar um
  site novo = escrever um adaptador novo, sem mexer no resto.
- **Reaproveitar o `verificar_links.py`** que já existe na pasta (testa
  vivo/quebrado/login/PDF): vire um módulo do motor.
- **Estrutura de pastas sugerida** (proponha e ajuste comigo):
  ```
  BuscadorBaixador/
    src/buscador/
      adapters/        # SiteAdapter + adaptadores por site
      core/            # verificação de links, planilha, tradução, etc.
      cli.py           # ponto de entrada de linha de comando
    tests/             # pytest (rodando sobre HTML/registros de exemplo salvos)
    saidas/            # planilhas geradas (fica no .gitignore)
    CLAUDE.md
    README.md
    requirements.txt
    .gitignore
  ```
- **Git:** inicializar o repo (ainda não existe `.git`), branch por funcionalidade
  (ex.: `feat/fase1-mapeador`), `.gitignore` cobrindo `.venv/`, `__pycache__/`,
  `*.xlsx`, `saidas/`.
- **Testes:** simples desde o começo — o parser rodando sobre um **HTML de exemplo
  salvo** (sem internet), verificando que extrai os links certos.

### 8.1. Repertório de métodos de coleta

Cada site pode precisar de um método de acesso diferente. O motor tenta vários em
cascata (`core/metodo_coleta.py`), em ordem, e só interrompe o Samuel quando **nenhum**
resolver — ver `core/acao_humana.py` para o sinal disso. Métodos conhecidos:

| Método | Estado | Onde mora |
|---|---|---|
| API oficial sem chave | Pronto | `GallicaAdapter` |
| API oficial com chave | Primitivas prontas (`acao_humana.py`, `config_sites.py`) | — |
| Raspagem HTML educada (requisição crua, sem JS) | Pronto (específico); genérico ainda não existe | `PhpbbAdapter` |
| Login lendo cookie do Chrome normal (`browser_cookie3`) | Pronto, mas **confirmado que não funciona no Chrome atual do Samuel** (ver nota abaixo) | `cookies_navegador.py` |
| Navegador automatizado (SeleniumBase, headless ou visível) — resolve JavaScript, login e CAPTCHA | Ainda não construído (próximo passo) | `navegador.py` |
| Sem via automatizável (lista manual de códigos) | Reconhecido (caso zvdd.de, seção 12), ainda não formalizado como método da cascata | — |

**Sobre `cookies_navegador.py` (ler login do Chrome):** testado ao vivo em 15/09/2026
contra o Chrome 152 do Samuel — **não funciona**, e não é bug nosso: desde o Chrome 127
(meados de 2024), o Google cifra os cookies com "app-bound encryption", uma proteção de
segurança deles especificamente contra programas de fora lendo cookie sem passar pelo
próprio Chrome (a mesma técnica que ladrão de sessão/malware tentaria usar). A biblioteca
`browser_cookie3` não consegue descriptografar nesse caso — e devolve vazio de forma
limpa (sem quebrar o programa), como já estava desenhado. **Não vamos tentar contornar
essa proteção** — é a mesma categoria de regra do UC Mode/CDP Mode abaixo: existe técnica
pra isso, mas é contornar uma barreira de segurança colocada de propósito, não construímos
isso. Na prática, isso quer dizer que quem resolve login de verdade, hoje, é a camada
seguinte (sessão salva via `logar.py`), não esta.

**Sobre o navegador automatizado:** usamos o SeleniumBase pelas conveniências dele em
cima do Selenium (espera automática de elemento, API mais simples) — **nunca** os
recursos de disfarce contra detecção de robô que ele também tem (UC Mode/CDP Mode). Essa
proibição é a mesma regra de não burlar detecção da seção 12 (caso zvdd.de) e não é
negociável, mesmo que o pacote instalado deixe esses modos a uma linha de distância — a
barreira aqui é a regra, não uma trava técnica.

**Métodos conhecidos no mundo, sem adaptador ainda** (documentar, não construir até
aparecer um caso real): **OAI-PMH** (biblioteca pronta `Sickle`/`oaipmh-scythe` — é o que
zvdd.de e a DDB usam), **sitemap.xml**, **manifests IIIF**, **dumps públicos** para
baixar o catálogo inteiro de uma vez.

## 9. Stack sugerida (confirmar comigo)
Python 3.11+ com `.venv`. Rede: `httpx` (ou `requests`). HTML: `BeautifulSoup`.
Planilha: `openpyxl`. Tradução grátis: `argostranslate` (offline) ou `deep-translator`.
Testes: `pytest`. **Fases futuras (não instalar agora):** `ocrmypdf`+Tesseract,
`pypdf`, Calibre CLI, FastAPI/Streamlit para o dashboard.

---

## 10. As fases (construir em ordem, uma de cada vez)

### Fase 1 — Mapear um site → planilha  ⟵ COMEÇAR AQUI
**Objetivo:** dado um site, listar todos os links/PDFs numa planilha `.xlsx`.
**Detalhes:**
- varre todas as páginas (respeitando a seção 7); extrai links e PDFs;
- verifica **vivo / quebrado / precisa-login** e pinta a linha: 🟢 baixa direto,
  🔵 login, 🔴 quebrado; "só vivo" fica branco;
- **categoria leve** (de que seção/página do site veio);
- **título original + tradução PT automática**;
- **quadrinho de explicação** (descrição da própria página; em **fóruns**, o texto
  da conversa em volta do link) + botão opcional "Claude lê a conversa" → assunto
  provável (marcado como palpite);
- coluna `avaliacao_humana` (vazia, com **dropdown**).
**Pronto quando:** `pytest` passa; rodar o CLI com uma URL gera o `.xlsx` em
`saidas/` com títulos traduzidos, status colorido e links que levam ao PDF/registro
certo. Testes automáticos **sem internet**.

### Fase 2 — Baixar
**Objetivo:** baixar os PDFs marcados, inclusive atrás de login que **eu** já fiz.
**Detalhes:** baixar 1 ou vários (em lote); usar a sessão logada do dashboard;
guardar o **sha256** de cada arquivo (chave para a ponte com o catálogo).
**Pronto quando:** baixa corretamente um conjunto de itens da planilha da Fase 1,
inclusive um caso que exige login.

### Fase 3 — Baixar já organizando por categoria do site
**Objetivo:** ao baixar, separar em **pastas** pela categoria que a Fase 1 achou
(seção do fórum, tema da página). **Sem OCR ainda.**
**Pronto quando:** os arquivos caem em pastas coerentes, com nomes organizados.

### Fase 4 — Catalogar fundo (OCR + bases + IA opcional)
**Objetivo:** olhar dentro do PDF para chutar **autor, título e tema** e separar por
isso — **sempre marcando "palpite, confirme".**
**Detalhes:** ler texto/metadados embutidos (grátis); **OCR** (OCRmyPDF + Tesseract)
nos escaneados; conferir em **catálogo on-line** (Open Library / Google Books /
Calibre); em fóruns, usar o contexto da conversa; **botão Claude Pro** para mais
precisão.
**Pronto quando:** para uma amostra baixada, gera um palpite de autor/título/tema
com o aviso de confiabilidade, e organiza em pastas por isso.

### Fase 5 — Buscar por nome ("buscador de insights")
**Objetivo:** eu digito o nome de um livro e o app procura na **base de sites
cadastrados**, devolvendo links para conferir.
**Detalhes:** busca de cada site + consultas `site:` no Google; lista de links;
reusa as Fases 1–4 no que achar.
**Pronto quando:** digitar um título conhecido retorna links úteis para conferência.

### Módulo extra (por último) — Telegram
Procurar/baixar obras em grupos de Telegram (tecnologia diferente dos sites);
entra depois que o núcleo estiver pronto.

---

## 11. Contexto e histórico (o que já foi feito — importante)
- **Caso de origem (Grand Sud Médiéval):** um fórum phpBB francês que garimpamos.
  Aprendizados que valem para o motor:
  - o **funil de valor**: o que interessa é a **OBRA para preservar** (PDF de
    livro/tratado/fonte), **não** o estudo acadêmico sobre o tema; artigos entram,
    mas não dominam;
  - classificação de link: **ALTA** (obra baixável: PDF direto, Academia.edu — que
    **baixa com login grátis**, repositório com texto integral), **MÉDIA** (página/
    portal sobre o tema), **BAIXA** (imagem/vídeo/sem contexto);
  - em fóruns, o "onde encaixar" muitas vezes está **na conversa**, não no PDF.
- **Já existe e já rodou:** o `verificar_links.py` (nesta pasta) — testa cada link e
  pinta a linha: 🟢 vivo+PDF, 🔵 login, 🔴 quebrado, branco = só vivo; cria abas
  "Quebrados" e "Prontos p/ baixar" (renomeada para "Prontos para baixar" — `/` não
  é permitido em nome de aba do Excel). Ele usa uma **regra de repositórios
  conhecidos** (Persée, HAL, raco.cat, revues.org, Gallica...) para marcar 🟢 mesmo
  sem "ver" o `.pdf`. **Limitação honesta:** PDFs carregados só por JavaScript não
  são detectados no HTML cru — nesses casos o item fica branco (nunca vira 🔴 por
  engano).
- **Tradução:** no Grand Sud eu traduzi os títulos **à mão**; no app isso vira
  **automático** (Argos/deep-translator).
- **Planilha:** usa **dropdowns** (`avaliacao_humana`: Aprovar/Rejeitar/Talvez/Já no
  acervo/Duplicado; `status_link`). O motor deve gerar planilhas assim.
- **Ponte com o acervo (futuro):** cada obra aprovada recebe um código único
  (`SB-xxxx`) e entra no catálogo do Instituto (BiblioteQ/Biblivre para físico,
  **Calibre** para digital); o **sha256** do PDF é a chave dessa ponte.

## 11.1. Planilhas já produzidas (exemplos do formato-alvo — CONSULTAR)
Já existem duas planilhas prontas do garimpo do Grand Sud. Use-as como **referência
visual do que a Fase 1 deve gerar** (o app novo terá colunas parecidas, adaptadas a
cada site). Ficam em:
`C:\Users\fotog\Desktop\Projeto São Bento\SITE GRAND SUL MEDIEVAL\GARIMPO\`
- **`Garimpo_GSM_MESTRE.xlsx`** — a planilha-mestre do garimpo. Abas: **LEIA-ME**,
  **Links** (a principal), **Texto útil**, **Resumo por seção**. Colunas da aba
  Links: `grupo`, `secao_f`, `secao`, `prioridade` (ALTA/MÉDIA/BAIXA, colorida),
  `obra_baixavel`, `tipo`, `titulo_pt`, `topico_titulo`, `link`, `destino`, `autor`,
  `status_link`, `topico_url`, `avaliacao_humana`. Tem **dropdowns** em
  `avaliacao_humana` e `status_link`, e cores por prioridade/grupo.
- **`Garimpo_GSM_MESTRE_VERIFICADO.xlsx`** — a mesma, depois de rodar o
  `verificar_links.py`: **linha inteira colorida** por status (🟢 vivo+PDF, 🔵 login,
  🔴 quebrado, branco = só vivo) e abas extras **"Quebrados"** e **"Prontos para
  baixar"**.
Antes de programar a Fase 1, **abra essas duas** para ver o formato, as cores e os
dropdowns que já validamos — é o alvo a reproduzir (de forma automática e por site).

## 12. Caso de teste inicial (Fase 1)

**Decisão (atualizada em relação ao rascunho original):** o alvo original era o
**zvdd.de**, mas foi descartado como caso de teste depois de investigar: o
`robots.txt` dele bloqueia **tanto** a busca por HTML (`/dms/search/`, `/dms/esuche/`)
**quanto** a própria API oficial OAI-PMH (`/oai2/`) — não sobra nenhuma via de
busca/descoberta automatizada permitida, só a consulta de metadados de um item **já
conhecido** (`/dms/load/met/?PPN=<código>`, que não descobre nada novo sozinha).
Além disso, o próprio projeto zvdd está sendo desativado desde 2024 por decisão da
DFG (a agência alemã que o financiava), que recomenda migrar para a **Deutsche
Digitale Bibliothek (DDB)** como sucessora oficial.

**Segundo caso de teste (API): Deutsche Digitale Bibliothek (DDB)** — tentamos
primeiro. Tem API REST pública e documentada, mas **exige cadastro** ("Meine DDB")
para gerar uma chave, e o formulário de cadastro (`/user/apikey/request`) deu erro
400 persistente ("Request-Parameter nicht wie erwartet") em várias tentativas
(navegador normal, anônimo, contas diferentes) — parece bug do lado deles. Depois
de muito tempo tentando contornar isso, **trocamos para a Gallica** (abaixo). O
código da DDB (`adapters/ddb.py`, `core/config.py`) foi **removido** do projeto — se
um dia a chave da DDB funcionar, pode valer reconstruir o adaptador (o padrão de
`GallicaAdapter` serve de modelo), mas não é prioridade agora.

**Caso de teste atual (API): Gallica (BnF)** — `https://gallica.bnf.fr/SRU`, API
SRU oficial e documentada em `api.bnf.fr`, **sem chave**. Confirmado por teste real
do Samuel (não só documentação): funciona com
`operation=searchRetrieve&version=1.2&query=<CQL>&maximumRecords=<0-50>&startRecord=<N>`,
resposta em XML Dublin Core (`dc:title`, `dc:creator`/`dc:contributor`, `dc:date`,
`dc:language`, `dc:publisher`, `dc:description`, `dc:rights` → coluna
`dominio_publico`, `dc:identifier`/`<link>` → coluna `link`, `<typedoc>` → tipo).
**Atenção de robots.txt:** o `robots.txt` da Gallica tem uma regra ampla
(`Disallow: /*?`) que, lida ao pé da letra, bloquearia qualquer URL com "?" —
inclusive a do SRU. Concluímos que essa regra mira as páginas de busca do site
comum, não a API oficial (confirmado por `api.bnf.fr` documentar exatamente essa
URL para uso por terceiros) — mas fica registrado que é uma leitura, não uma
certeza absoluta. **Rate limit descoberto na prática:** a Gallica devolve 429 (Too
Many Requests) entre páginas com intervalo menor que ~6s — `GallicaAdapter` usa um
intervalo maior que o padrão do `ClienteEducado`, e o `ClienteEducado` agora tenta
de novo automaticamente em 429 (espera dobrando: 5s/10s/20s) antes de desistir.
Autor de teste: **"Clavius"**. zvdd.de continua descartado (ver abaixo).

**zvdd.de fica anotado como adaptador futuro, opcional, só por PPN manual:** como o
zvdd não permite nenhuma forma de descoberta automatizada, um eventual adaptador para
ele só pode funcionar recebendo uma **lista de PPNs fornecida manualmente** (você
navega no site, anota os códigos dos itens que interessam, e o programa automatiza
metadados/verificação de link/tradução/planilha a partir daí) — nunca uma busca
autônoma. Pode virar uma fatia pequena em qualquer fase futura, sem pressa; não faz
parte do caminho crítico da Fase 1.

---

## 13. Como começar (agora)
**Não escreva código ainda.** Faça, em ordem:
1. Me mostre este documento salvo como `CLAUDE.md` + a **estrutura de pastas** e a
   **lista de dependências** — para eu aprovar.
2. Proponha o **git** (init + branch + revisão do `.gitignore`) e o primeiro **teste**
   de exemplo.
3. Quando eu aprovar a organização, **entre no fluxo de plan mode da Fase 1**
   (seção 4): me peça para ativar o plan mode e apresente o plano da Fase 1 usando o
   zvdd como caso de teste — incluindo **como acessar o zvdd de forma permitida**
   (opções da seção 7). Espere meu "ok" antes de codar.

## Checkpoint de contexto (`/checkpoint`)
Existe um comando pessoal, `/checkpoint` (fora deste repositório — vale pra
todos os projetos), que atualiza o `HANDOFF.md`, comita/envia, e avisa que é
seguro limpar o contexto ou começar uma conversa nova. **Sugira rodá-lo**
(não precisa esperar o Samuel pedir) quando: uma fase inteira for concluída,
uma investigação longa for resolvida (ex.: uma sessão de debug ou pesquisa
que consumiu muitas mensagens), ou a conversa estiver visivelmente longa e
prestes a mudar de assunto. Nunca rode o comando sozinho sem avisar — só
sugira, o Samuel decide quando.

## Commit e push regulares

Quando este repositório tiver GitHub remoto configurado, faça commit do progresso
relevante regularmente e dê `git push` — não é preciso perguntar cada vez, mas
sempre revise o que está sendo commitado antes (nunca commitar segredo, nunca
desfazer o `.gitignore` sem avisar, nunca commitar planilha de dados do garimpo).
