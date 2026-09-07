# Prompt para o Claude Code — Projeto "Buscador e Baixador" (Fase 1)

> Cole este documento inteiro no Claude Code, com a pasta do projeto aberta em
> `D:\programas\BuscadorBaixador`.

## Quem você é nesta tarefa
Você é meu parceiro de programação. **Eu estou aprendendo** — então explique suas
decisões de forma didática, em **português**, e prefira **soluções simples** às
espertas. Trabalhe **um passo de cada vez**.

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
2. **Explique em termos simples** o que está em jogo — eu estou aprendendo e quase
   nunca vou saber que a escolha existe se você não me avisar.
3. **Ofereça 2–3 opções**, cada uma com prós e contras curtos.
4. **Recomende uma** e diga por quê.
5. **Espere eu escolher** antes de seguir.
Essa sinalização é **obrigatória**, não opcional. A única exceção são **regras
rígidas** (não burlar robots.txt / paywall / CAPTCHA / login): aí você não me
oferece a opção de burlar, mas mesmo assim **explica o porquê** e me apresenta os
caminhos legítimos.

## O que é o projeto (visão geral)
Um **aplicativo local** (roda no meu PC, Windows), usado por mim e pelo Kaique,
para o Instituto São Bento **achar, baixar e catalogar obras** (livros esgotados,
artigos, digitalizações) espalhadas por vários sites e fóruns.

Restrições importantes:
- **Sem IA local** (os PCs não aguentam). A IA entra só por um **botão opcional**
  que manda dados para o meu **Claude Pro**. Catalogação automática usa **bases
  on-line gratuitas** (Open Library, Google Books, Calibre), não modelo local.
- **Custo zero** por padrão: tudo com ferramentas **open-source**.
- **Ética/legal:** **não burlar** paywalls, CAPTCHAs ou logins. Só operar em sites
  que **eu cadastrar**. Login é feito **por mim, no dashboard** (fase futura) —
  nunca senha escrita no código. O acesso a cada site segue a **árvore de decisão**
  abaixo.

## Regra de acesso a cada site (árvore de decisão — importante)
Para cada site, o programa decide **como** acessar, nesta ordem:
1. **Ler o `robots.txt` do site primeiro.**
2. Se a varredura é **permitida** → **varrer o HTML normalmente** (adaptador
   genérico ou de fórum, como fizemos no Grand Sud), sendo **educado**: 1 requisição
   por vez, atraso de ~2 s entre elas, User-Agent honesto e identificável, e parar
   se o servidor recusar.
3. Se o site oferece **API oficial** (OAI-PMH, SRU, METS/MODS) → **prefira a API**
   mesmo quando o HTML é permitido: é mais leve, estável e educada. (É escolha de
   qualidade, não obrigação legal.)
4. Se o `robots.txt` **proíbe** a varredura **e não há API** permitida → **me
   explique isso e me ofereça as opções legítimas** (ex.: usar a API caso exista,
   pular o site, ou eu pedir permissão ao site) — não decida sozinho e nunca burle.
   Mesmo no item 3 (existe API), **me avise que essa escolha existe** e me deixe
   optar entre API e HTML, em vez de decidir por mim.
O caso mais comum (item 2) é o **padrão**. O zvdd cai no item 3/4 (tem API e o
robots restringe a busca por HTML), por isso ele exige tratamento especial.
- **Frontend/dashboard fica para o final.** Agora construímos o "motor" em Python,
  testável por linha de comando.

## Roteiro completo (documente isto no CLAUDE.md; construiremos por fases)
- **Fase 1 — Mapear um site → planilha** (ESTA tarefa). Dado um site, listar todos
  os links/PDFs numa planilha, com: verificação vivo/quebrado/precisa-login (cores
  🔵🔴🟢), categoria de origem, **título original + tradução PT automática**,
  quadrinho de **explicação** (descrição da página, ou o texto da conversa no caso
  de fóruns).
- **Fase 2 — Baixar** os PDFs marcados (inclusive atrás de login que EU já fiz).
- **Fase 3 — Baixar já organizando** em pastas pela categoria que a Fase 1 achou.
- **Fase 4 — Catalogar fundo:** ler texto/metadados embutidos do PDF; **OCR**
  (OCRmyPDF + Tesseract) nos escaneados; conferir em **catálogo on-line**; botão
  Claude Pro; separar por autor/título/tema, **sempre marcando "palpite, confirme"**.
- **Fase 5 — Buscar por nome:** digitar o nome de um livro e procurar na base de
  sites cadastrados (busca de cada site + consultas `site:` no Google), devolvendo
  links para conferir.
- **Bases (valem para tudo):** dashboard à prova de leigo; gestão de sites + login
  no dashboard; botão Claude Pro; aviso de "não confiável".
- **Módulo extra (por último):** Telegram.

## Stack sugerida (confirme comigo antes de fixar)
- **Python 3.11+**, ambiente virtual (`.venv`).
- Rede: `httpx` (ou `requests`). HTML: `BeautifulSoup` (`bs4`). Planilha: `openpyxl`.
- Tradução automática (grátis): `argostranslate` (offline) **ou** `deep-translator`.
- Testes: `pytest`.
- (Fases futuras, não instalar agora: `ocrmypdf`+Tesseract, `pypdf`, Calibre CLII, FastAPI/Streamlit.)

## Arquitetura que eu quero (importante para reuso)
O mapeador tem que servir para **vários tipos de site**. Então use o padrão de
**"adaptadores de site"**:
- uma interface base `SiteAdapter` com métodos como `iter_itens()` (gera os
  achados) e `descrever(item)`;
- um adaptador **genérico** (varre páginas e acha links/PDFs);
- adaptadores **específicos** quando o site tiver API (ex.: `ZvddAdapter` usando a
  interface oficial do zvdd), ou estrutura própria (ex.: fórum phpBB, como o Grand Sud).
Assim, adicionar um site novo = escrever um adaptador novo, sem mexer no resto.

Aproveite o **`verificar_links.py` que já existe nesta pasta** (ele testa
vivo/quebrado/login/PDF): transforme a lógica dele num módulo reutilizável do motor.

## Boas práticas para montar ANTES de programar a Fase 1 (Etapa de organização)
Me proponha (e só execute após eu aprovar):
1. **Estrutura de pastas**, algo como:
   ```
   BuscadorBaixador/
     src/buscador/        # o código do motor
       adapters/          # SiteAdapter e os adaptadores
       core/              # verificação de links, planilha, tradução
       cli.py             # ponto de entrada de linha de comando
     tests/               # testes com pytest
     saidas/              # planilhas geradas (fica no .gitignore)
     CLAUDE.md
     README.md
     requirements.txt
     .gitignore
   ```
2. **CLAUDE.md** documentando: o que é o projeto, a stack, como rodar/testar, a
   estrutura de pastas, as convenções, o roteiro das fases e o que NÃO mexer.
3. **Git:** inicializar o repositório (ainda não é um repo), branch por
   funcionalidade (ex.: `feat/fase1-mapeador`), e revisar/atualizar o `.gitignore`
   (já existe um; confira se cobre `.venv/`, `__pycache__/`, `*.xlsx`, `saidas/`).
4. **Testes:** começar simples — um teste que roda o parser sobre um **HTML de
   exemplo salvo** (sem depender da internet), verificando que ele extrai os links
   certos. Assim os testes são rápidos e não dependem do site no ar.

## O que construir NESTA fatia (Fase 1), com o site de teste
**Site de teste (caso real):** zvdd.de — Zentrales Verzeichnis Digitalisierter
Drucke (agregador alemão de impressos digitalizados; obras antigas, domínio público).
Exemplo de busca (autor "Christophori Clavii"):
`https://www.zvdd.de/dms/search/?tx_goobit3_search[default]=metadata&tx_goobit3_search[formquery]=Christophori Clavii`

Observações que descobrimos e que você deve tratar:
- O **robots.txt do zvdd proíbe** raspar a busca via HTML. Então **primeiro
  investigue a interface oficial** (o zvdd oferece **SRU/OAI-PMH**); use-a se
  existir. Se não houver caminho permitido, **pare e me avise** — não burle o robots.
- O zvdd é **agregador**: cada resultado normalmente **aponta para o visualizador
  de outra biblioteca** (onde está o PDF/METS de verdade). O adaptador precisa
  seguir esse "pulo" para achar o PDF real.

**Entrada da Fase 1:** uma URL de busca (ou de acervo) do site.
**Saída da Fase 1:** um arquivo `.xlsx` na pasta `saidas/`, com uma linha por
achado e, no mínimo, as colunas:
`titulo_original`, `titulo_pt`, `autor`, `ano`, `link`, `tipo` (pdf direto /
página / precisa login), `status_link` (🟢🔵🔴), `explicacao`, `fonte/biblioteca`,
`avaliacao_humana` (vazia, com dropdown). Pinte a linha conforme o status, como
combinamos (🟢 baixa direto, 🔵 login, 🔴 quebrado; "só vivo" fica branco).

**Pronto quando (como testar):**
1. `pytest` passa (testes do parser sobre HTML/registro de exemplo salvo).
2. Rodar o CLI com a URL de teste do zvdd gera um `.xlsx` em `saidas/` com as
   obras de "Christophori Clavii", títulos traduzidos, status colorido e links que,
   ao clicar, levam ao PDF/registro certo.
3. Nada de rede nos testes automatizados; a rede só no comando real.

## Primeiro passo, agora
**Não escreva código ainda.** Comece me apresentando, para eu aprovar:
(a) a estrutura de pastas e o conteúdo do CLAUDE.md;
(b) a lista de dependências;
(c) como você pretende acessar o zvdd de forma permitida (API oficial vs HTML) —
   incluindo o que você precisa verificar no site antes.
Espere meu "ok" antes de criar qualquer arquivo.
