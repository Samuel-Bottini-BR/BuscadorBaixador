# Buscador e Baixador — estado atual

## O que é e para quem

Aplicativo local (Windows) para o Instituto São Bento achar, baixar e
catalogar obras digitalizadas (livros esgotados, artigos) espalhadas em
sites e fóruns. Usuários: Samuel e o Kaique (leigo, sem formação técnica —
interface precisa ser simples, em português). Regras completas do projeto,
arquitetura e protocolo de decisões estão em `CLAUDE.md` — leia lá primeiro.

## Estado atual

**Fase 1 ("mapear um site → planilha") concluída**, e com uma peça grande
que não estava documentada aqui até este checkpoint (ver seção logo abaixo,
"Achado: a coleta em massa da Gallica já existe"). Dado uma URL (tópico do
fórum Grand Sud) ou uma consulta CQL (autor/título na Gallica), o programa
varre, verifica cada link (vivo/quebrado/precisa login), traduz o título, e
gera uma planilha `.xlsx` em `saidas/` — com linha colorida por status e
dropdown de avaliação, no mesmo estilo do `Garimpo_GSM_MESTRE_VERIFICADO.xlsx`.

**Rodado de verdade contra os dois adaptadores:**
- Grand Sud (tópico "Les jongleurs"): 7 itens, links verificados certos
  (2 quebrados de verdade, 1 repositório reconhecido, PDFs diretos).
- Gallica (busca "Clavius"): 50 itens reais, títulos em latim/francês
  traduzidos (online quando funciona, offline via pivô fr→en→pt quando não),
  links de `gallica.bnf.fr` reconhecidos como repositório.

- Repositório: https://github.com/Samuel-Bottini-BR/BuscadorBaixador
  (branch de trabalho: `feat/fase1-mapeador`, commit mais recente conferido
  em 13/09/2026: `d3bc03d`, `pytest` passando — **103 testes** hoje, não 64
  como este arquivo dizia antes; o número cresceu em commits que já
  existiam e este handoff não tinha acompanhado).
- Pacote Python instalável (`pyproject.toml`, `src/buscador/`), `.venv` com
  Python 3.12 (instalado à parte do 3.14 global, por causa do `argostranslate`).
- `PhpbbAdapter` (fórum, com paginação) e `GallicaAdapter` (API SRU da BnF,
  sem chave) prontos, testados e **validados ao vivo**.
- **A DDB foi tentada primeiro e depois abandonada** (ver seção 12 do
  CLAUDE.md): o cadastro pra gerar a chave de API deu erro 400 persistente
  no site deles, em várias tentativas. O código (`adapters/ddb.py`,
  `core/config.py`) foi removido do projeto — não ficou pela metade.
- zvdd.de continua descartado como caso de teste, só como adaptador futuro
  opcional por lista de PPN manual.

## Achado neste checkpoint: a coleta em massa da Gallica já existe, e este handoff não sabia

Ao revisar o repositório em 13/09/2026 achei um pipeline inteiro, já
codificado e já rodado parcialmente, que **este arquivo nunca mencionou**:

- **`src/buscador/gallica_crawl.py`** (Etapa 1) — CLI retomável que coleta
  uma consulta CQL **inteira** da Gallica, com checkpoint em disco
  (`core/checkpoint.py`), tratando 429 com um "cooldown" configurável.
  Uso: `python -m buscador.gallica_crawl 'dc.type all "monographie"'`
  (aceita `--job`, `--max-resultados`, `--tamanho-pagina`,
  `--cooldown-429-minutos`, `--reiniciar`).
- **`src/buscador/gallica_enriquecer.py`** (Etapa 2) — pega o que a Etapa 1
  coletou e verifica link + traduz, em lotes, também retomável
  (`core/enriquecimento_lote.py`).
- **Já tem uma coleta real, incompleta, parada:**
  `saidas/gallica_crawl/dc-type-all-monographie-4d1e657b14/checkpoint.json`
  mostra a consulta `dc.type all "monographie"` — **todos os "livros"
  (monografias) do catálogo inteiro da Gallica, via a categoria oficial da
  API, não a curadoria editorial** — com **311.750 de 934.080 registros
  já coletados** (33%), parada em `2026-09-09T07:35:59Z`, `concluido: false`.
  Não sei por que parou (rate limit, sessão que acabou, ou pausa
  intencional) — não tem registro do motivo em lugar nenhum que eu achei.
  **Rodar o mesmo comando (`python -m buscador.gallica_crawl 'dc.type all
  "monographie"'`) deve retomar sozinho de onde parou**, pelo mecanismo de
  checkpoint — não testei retomar nesta sessão, só confirmei que o
  checkpoint existe e o código foi desenhado pra isso.

**Isso muda a resposta pra "mapear o site inteiro":** essa consulta
(`dc.type all "monographie"`) já é, tecnicamente, "todos os livros da
Gallica" — 934 mil registros, com metadado de verdade (autor, ano, idioma,
domínio público), pela API oficial. É bem mais completo e mais limpo do que
o mapeamento por curadoria editorial que fiz nesta sessão (ver próxima
seção) — que pega só o que a Gallica decidiu destacar manualmente em
"sélections", e vem com um problema de categorização (ver abaixo). As duas
coisas capturam universos diferentes e não se substituem uma pela outra
sem mais conversa com o Samuel sobre qual é o objetivo real.

## O que aconteceu com o mapeamento da Gallica em 12-13/09/2026

Samuel pediu pra mapear "o site inteiro" e, depois de eu mostrar a escala
(uma única letra de uma categoria já tinha 220 itens), ele confirmou: **"eu
quero tudo, pode mandar."** Isso foi feito via as páginas de curadoria
editorial da Gallica (`gallica.bnf.fr/selections/fr/html/...`), não pela
API SRU (ver achado acima — só descobri o pipeline SRU depois de já ter
percorrido esse caminho).

**Resultado:** rastreei a árvore inteira a partir de
`selections/fr/html/livres` — **46.222 itens em 3.165 páginas visitadas**,
script em `scripts/mapear_gallica_selecoes_prototipo.py` (protótipo, não é
parte do pacote, não tem teste — ver docstring do próprio arquivo pros
detalhes técnicos). Saídas em `saidas/` (ambas ignoradas pelo git):
`gallica_mapa_livros.json` (bruto), `gallica_mapa_livros_completo.xlsx`
(planilha, 46.222 linhas), `relevante_religiao_amostra.txt` (181 itens
filtrados por palavra-chave de teologia/religião/bíblia/liturgia).

**Achado importante, ainda sem conserto:** a coluna "categoria" desse
mapeamento é a **trilha de navegação** (a ordem em que o rastreador visitou
as páginas), não uma classificação confiável — a Gallica cruza links entre
assuntos completamente diferentes (ex.: "Manuscritos" aparece como link
relacionado dentro da página de quadrinhos). Isso fez conteúdo de teologia
genuíno ficar registrado com uma trilha tipo "Livros > Quadrinhos > Autores
de quadrinhos > ... > Manuscritos > ... > Teologia", o que é sem sentido.
Título e link de cada item continuam corretos; só a "categoria" engana. Quem
for reaproveitar isso como adapter de verdade precisa ou (a) tratar cada
categoria de primeiro nível como árvore isolada, sem compartilhar o
conjunto de páginas já visitadas entre elas, ou (b) não tentar rotular por
categoria, só guardar título+link+URL de origem.

**Confirmado ao vivo, nesta sessão, sobre a Gallica (além do que já se
sabia):**
- **O rate limit é do site inteiro, não só da API SRU.** As páginas de
  curadoria (`/selections/...`), a página do visualizador de documento
  (`/ark:/.../fNNN.item`) e um endpoint interno de AJAX
  (`/services/ajax/action/download/...`) levaram **429** depois de só
  4-5 requisições em rajada. Um intervalo de 4s entre páginas deu conta de
  rodar 3.165 páginas seguidas sem travar de novo.
- **`WebFetch` (a ferramenta genérica) é bloqueada pela Gallica com 403 em
  qualquer caminho** (`/SRU`, `/selections/...`, o visualizador) —
  provavelmente um WAF que rejeita o user-agent/perfil da ferramenta. Só o
  `ClienteEducado` do próprio projeto (com User-Agent honesto identificando
  o instituto) funciona. Não adianta tentar `WebFetch` na Gallica de novo.
- **O botão "baixar PDF" do site é um endpoint interno, não uma API
  documentada:** `GET /services/ajax/action/download/ark:/12148/{id}/f{n}.item`
  devolve um JSON com um campo `downoaldurl` (erro de digitação deles
  mesmo) apontando pra base `https://gallica.bnf.fr/ark:/12148/{id}` — o
  mesmo padrão já conhecido publicamente de baixar acrescentando `.pdf` no
  fim. **Não confirmei um download completo de verdade** (fim a fim) —
  cheguei a tentar uma vez e tomei 429 antes de confirmar; não tentei de
  novo por cautela com o rate limit. Isso é diferente em espírito de usar a
  API SRU (documentada pra automação): é replicar o que o navegador de
  qualquer visitante faz — público, sem login, mas não é uma API dedicada.
- Achados soltos: a página de categoria `religions` (dentro de "Livros")
  devolveu **403 especificamente essa**, diferente do 429 genérico — não
  investigado o motivo. Alguns links quebrados são do próprio site deles
  (`administration-interieure-de-la-bastille`, `the-new-york-herald`,
  `fondamentaux-des-sciences-et-des-techniques`, todos 404) — não são bug
  nosso.

**Bibliotecas usadas que já estavam instaladas no `.venv`, sem precisar
instalar nada** (confirmado nesta sessão, não são novidade mas o handoff
não citava): `beautifulsoup4` 4.15.0, `openpyxl` 3.1.5.

## Padrão de planilha aprovado em 15/09/2026 (retomar exatamente aqui)

Samuel pediu 3 versões de teste de como organizar a planilha de 46.222 itens
(ele reclamou que a versão de uma aba só, sem tradução, "fica muito
bagunçado"). Fiz uma amostra pequena (24 itens, 4 categorias) traduzida de
verdade, e gerei 3 layouts:

1. Uma aba por categoria, tabela simples.
2. Aba "Índice" (categoria + quantidade + link clicável pra cada aba) + uma
   aba por categoria.
3. Uma aba só, com linha de cabeçalho colorida antes de cada bloco de
   categoria, linhas agrupadas (outline do Excel, recolhe/expande).

**Samuel aprovou a versão 2 — "índice + abas por categoria". Esse é o
padrão de planilha do projeto a partir de agora**, pelo menos para
coleções grandes tipo esta.

**Scripts salvos no repositório** (`scripts/`, fora do pacote `buscador`,
ainda sem teste):
- `categorizar_amostra_gallica.py` — recategoriza por palavra-chave (os
  "baldes" no topo do arquivo) e traduz uma amostra. **Ainda é rascunho**:
  na rodada de teste só 4 dos 8 baldes pegaram itens (Quadrinhos,
  Manuscritos Medievais, Religião e Teologia, Referência) — os outros 4
  (Ciências, Paris, Literatura Clássica, Traduções) ficaram vazios, porque
  a trilha "categoria" de `gallica_mapa_livros.json` é contaminada (ver
  achado logo acima) e a ordem dos baldes decide qual palavra-chave vence
  quando várias aparecem na mesma trilha. Precisa de ajuste fino antes de
  rodar nos 46.222 itens de verdade.
- `gerar_planilha_padrao_gallica.py` — monta a planilha no formato
  aprovado (índice + abas) a partir da saída do script acima. Roda hoje só
  em cima da amostra pequena.
- Saídas de teste em `saidas/` (gitignored): `TESTE_versao1_...xlsx`,
  `TESTE_versao2_...xlsx` (o padrão aprovado, em miniatura),
  `TESTE_versao3_...xlsx`, `amostra_categorizada_traduzida.json`.

**Próximo passo recomendado:** para gerar a planilha final com os 46.222
itens de verdade, faltam duas coisas, nesta ordem:
1. Refinar os baldes de `categorizar_amostra_gallica.py` até a distribuição
   fazer sentido (hoje 2 baldes sozinhos comeriam quase tudo).
2. Traduzir os 46.222 títulos **em lotes retomáveis**, não numa chamada só
   — o Google Translate já se mostrou sensível a rate limit nesta própria
   sessão (recusou toda vez, caiu pro MyMemory) mesmo com só 24 chamadas.
   Vale reaproveitar o padrão de `core/enriquecimento_lote.py` (já existe
   no projeto, feito pra isso) em vez de escrever um laço novo do zero.

## Pendências conhecidas (não bloqueiam, mas valem nota)

- **Rate limit da Gallica:** a API devolve 429 (Too Many Requests) entre
  páginas com bastante facilidade — parece ser por cota acumulada, não só
  por intervalo entre chamadas. `GallicaAdapter` busca tudo numa página só
  por padrão (até 50 itens, o máximo documentado pela BnF) pra evitar isso;
  o `ClienteEducado` agora tenta de novo automaticamente em 429 (espera
  dobrando: 5s/10s/20s) antes de desistir. Buscas com mais de 50 resultados
  reais ainda podem esbarrar nisso se pedir várias páginas seguidas.
- **Sem tradução offline para latim** (o `argostranslate` não tem nenhum
  pacote de latim, nem via pivô) **— mas agora há uma segunda tentativa
  online (`MyMemoryTranslator`) antes de desistir**, que cobre latim (grego
  também tem pacote offline, já baixado e testado: `el→en→pt`). Testado ao
  vivo: 3/3 traduções de latim funcionaram com o MyMemory como reserva do
  Google. Só falha de verdade se as duas APIs online estiverem fora do ar
  ao mesmo tempo — nesse caso o título fica no original, nunca quebra o
  programa.
- **`dominio_publico` da Gallica confirmado correto, não é bug:** duas obras
  do Clavius (1586, 1593) vieram marcadas "Não" — investiguei o XML cru e a
  Gallica realmente marca essas digitalizações específicas como
  `"conditions spécifiques d'utilisation"` (vieram de acordos com outras
  instituições, ex. Observatoire de Paris, com restrição na imagem
  digitalizada — mesmo a obra original de 400+ anos sendo de domínio
  público). A coluna está lendo certo; a checagem de texto em `dc:rights`
  (procura "domaine public"/"public domain") é confiável.
- **Schema da resposta da Gallica confirmado ao vivo** (não é mais suposição
  como era com a DDB) — mas só testado com uma busca (`Clavius`); outras
  buscas podem revelar campos ausentes que os testes ainda não cobrem.
- **`_extrair_titulo_topico` do PhpbbAdapter** usa `h2 a` — confirmado contra
  duas fixtures reais, mas só foi testado no layout atual do fórum.

## Pergunta antiga, já resolvida em 12-13/09/2026

Samuel pediu "vamos mapear o site inteiro, primeiro" — depois de idas e vindas
(pensei que fosse o fórum Grand Sud; era sobre a **Gallica**), chegamos a:
a busca `"gallica all Clavius"` que rodamos tem **9739 resultados no total**
(`<srw:numberOfRecords>9739</srw:numberOfRecords>`, confirmado no XML cru),
não só os 50 da primeira página que processamos. A pergunta exata que tinha
ficado sem resposta:

> A busca 'gallica all Clavius' tem 9739 resultados no total. Você quer dizer:
> mapear TODOS os 9739 resultados dessa busca específica sobre Clavius? (Se
> sim, são ~195 páginas de 50, respeitando o intervalo educado — e a busca
> "all" da Gallica é frouxa, traz bastante ruído tipo jornais franceses do
> séc. XIX que só citam Clavius de passagem.) Ou "o site inteiro" era outra
> ideia — nesse caso, perguntar o que ele quer buscar/mapear de verdade.

**Resolvida:** não era sobre o Clavius nem sobre uma busca específica —
"o site inteiro" era literal, sobre a categoria "Livros" da curadoria da
Gallica por completo. Depois de eu mostrar a escala (uma letra de uma
subcategoria já tinha 220 itens), Samuel confirmou: **"eu quero tudo, pode
mandar."** Ver a seção "O que aconteceu com o mapeamento da Gallica em
12-13/09/2026", mais acima, para o resultado e a pergunta nova que ficou em
aberto no lugar desta.

## Decisões fechadas

- `requests` para raspagem educada (Grand Sud e Gallica, via `ClienteEducado`,
  ambos sem API "oficial feita pra automação sem restrição").
- Tradução em 3 camadas: Google Translate (3 tentativas, instável na prática)
  → MyMemoryTranslator (3 tentativas, cobre idiomas sem pacote offline tipo
  latim) → `argostranslate` offline (pivô por inglês quando não há par
  direto, ex.: fr→en→pt, el→en→pt) → mantém o original se tudo falhar.
- Empacotamento: pacote instalável de verdade (`pip install -e .`), não
  hack de `sys.path`.
- Ver seções 3 e 7 do CLAUDE.md para o protocolo de decisões e a árvore de
  acesso a sites (nunca burlar robots.txt/paywall/login) — inclusive um caso
  reforçado nesta sessão: recusei repetidamente ajudar a burlar o bloqueio
  do zvdd mesmo com técnicas de evasão de detecção sugeridas pelo Samuel
  (headless browser, rotação de proxy/User-Agent, etc.) — não é negociável.
- Regra de check-in: nesta Fase 1, Samuel pediu execução mais autônoma (só
  interromper por erro real ou decisão genuína) — combinado verbalmente,
  **não** alterado no CLAUDE.md ainda. Perguntar se vale formalizar isso lá
  antes da próxima fase.
- **Comando `/checkpoint` criado** (`C:\Users\fotog\.claude\commands\checkpoint.md`,
  fora deste repo — vale pra todos os projetos do Samuel). Atualiza o handoff,
  roda testes, comita/envia, e avisa quando é seguro `/clear`. Regra de quando
  eu devo sugerir isso sozinho está na seção "Checkpoint de contexto" do
  `CLAUDE.md`. **Nota:** `/clear` é uma ação do terminal, não algo que eu
  consigo acionar sozinho de dentro do comando — só aviso, o Samuel roda.
  Os outros 3 projetos (EditorImpressao, BREVIARIO, transcritor-bilingue)
  ainda não têm essa nota nos respectivos CLAUDE.md/handoff — perguntei se
  valia adicionar lá também, sem resposta ainda.

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
D:\programas\BuscadorBaixador\.venv\Scripts\python.exe -m buscador.cli "gallica all Clavius" --adapter gallica
```

**Coleta em massa da Gallica (achado neste checkpoint, ver seção acima) —
retomar a que já está 33% feita:**
```
D:\programas\BuscadorBaixador\.venv\Scripts\python.exe -m buscador.gallica_crawl "dc.type all \"monographie\""
D:\programas\BuscadorBaixador\.venv\Scripts\python.exe -m buscador.gallica_enriquecer
```
(não usar `--reiniciar` — isso apaga os 311.750 já coletados, pede
confirmação explícita antes de apagar mesmo assim)

**Protótipo do mapeamento por curadoria editorial (46.222 itens, ver seção
acima) — não é um comando definitivo, é um script solto:**
```
D:\programas\BuscadorBaixador\.venv\Scripts\python.exe scripts\mapear_gallica_selecoes_prototipo.py
```

Ou clique duas vezes em `mapear.bat` (usa o `.venv` do projeto direto, não
depende do que estiver no PATH). O `.venv` já está criado com Python 3.12 e
o pacote instalado em modo editável — `pip install -e ".[dev]"` se precisar
reinstalar.
