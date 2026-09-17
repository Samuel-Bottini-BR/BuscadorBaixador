# Buscador e Baixador — estado atual

## Checkpoint 17/09/2026 (sessão 2) — desenho do motor de jobs, leia aqui primeiro

Sessão de brainstorming (skill `superpowers:brainstorming`, caminho
arquitetural) sobre um **motor de jobs** — a peça que deixa o programa
rodar várias tarefas ao mesmo tempo, sem terminal manual, pensando já num
uso futuro pelo Kaique (dashboard, projeto separado, vem depois). Ao mesmo
tempo, retomamos as duas frentes que tinham ficado paradas da Gallica
(pergunta em aberto do checkpoint anterior — ver resolução logo abaixo).

**Spec escrita, revisada e commitada:**
`docs/superpowers/specs/2026-09-17-motor-de-jobs-design.md` (commit
`24c6deb`, enviado ao GitHub). Leia o arquivo pra o desenho completo —
resumo das decisões principais:

- **Arquitetura escolhida: subprocessos + registro em JSON** (não um
  processo supervisor único, não fila de arquivos) — cada job roda como
  processo isolado do Windows, reaproveitando o padrão de escrita atômica
  de `core/checkpoint.py`. Motivo: nenhum ponto único de falha, nada
  precisa ficar ligado o tempo todo, e um job travando não derruba os
  outros.
- **Job = alvo + lista de estágios configurável.** Estágios: Mapear
  (obrigatório, primeiro, deve capturar o máximo de metadado disponível
  na fonte) → Verificar links e Traduzir (independentes entre si) → Baixar
  (depende de Verificar; ainda não implementado, é Fase 2). Dá pra
  ligar/desligar estágio por job, inclusive depois que outros já rodaram
  (ex.: mapear sem traduzir agora, adicionar traduzir depois sobre o que
  já foi mapeado).
- **Categorização no estágio Mapear, em 3 níveis de custo crescente:**
  (1) categoria formal de API/metadado do site, se existir — usa direto;
  (2) se não, tenta a trilha de navegação (`secao`/breadcrumb, já coletada
  hoje) e sugere pra Samuel aprovar; (3) se nenhuma resolver, a IA entra —
  primeiro propondo a lista de categorias em rodadas "por exclusão"
  (Samuel aprova/rejeita/pede mais, sem repetir o que já foi decidido),
  depois classificando cada item pelos metadados disponíveis.
- **Decisão importante, com pedido explícito do Samuel: nenhuma API paga
  da Anthropic em lugar nenhum do projeto.** Motivo: sem orçamento
  disponível agora. As duas frentes de IA (propor categorias, classificar
  item) usam só: **(a) modelo local via Ollama** (grátis, mais lento — ver
  estimativa de hardware abaixo) ou **(b) handoff manual via Claude Code**
  (o job exporta um arquivo, Samuel traz numa sessão como esta, recebe o
  resultado de volta, importa — grátis dentro da assinatura Max, mais
  rápido, mas exige Samuel presente).
- **Descartado explicitamente: usar o Claude Agent SDK autenticado pela
  assinatura Max pra automação não-supervisionada.** Tecnicamente possível,
  mas descartado por incerteza real sobre se está dentro dos termos de uso
  do plano Max (pensado pra assistente interativo, não motor de
  classificação em lote rodando sozinho) e por competir pelo mesmo limite
  semanal do uso interativo do Samuel com sobrecarga maior por chamada. O
  handoff manual (uma sessão real, iniciada pelo Samuel) evita esse risco.
- **Hardware do Samuel confirmado nesta sessão** (relevante pra dimensionar
  o modelo local): Ryzen 7 5800H (8 núcleos/16 threads), 16GB RAM, GPU
  dedicada NVIDIA GTX 1650 com **4GB de VRAM** (só isso comporta bem
  folgado; a GPU integrada AMD Radeon do mesmo chip não é relevante pra
  isso). Estimativa não confirmada por teste real: um modelo pequeno
  (~3B parâmetros, ex. Llama 3.2 3B/Qwen2.5 3B) classificaria os 46.222
  itens da Gallica em ~3-5h rodando em lote, como job de segundo plano.
  **Próxima sessão que for validar isso deve rodar um teste real com
  200-300 itens antes de confiar nesse número.**
- **Nota de visão pra mais pra frente** (Fase 4/5 do roadmap, não desenhar
  ainda): o passo de "IA classifica pelos metadados disponíveis" foi
  desenhado pra não precisar mudar de forma quando o OCR existir — o mesmo
  passo passaria a receber também o texto extraído do livro. A ideia do
  Samuel de organizar por categoria/tema/autor com ajuda do OCR e integrar
  com o outro app de biblioteca que ele está construindo fica registrada
  aqui como visão, não como plano.

**Próximo passo recomendado:** ainda não existe plano de implementação —
só o desenho. Quando o Samuel quiser seguir, invocar a skill
`superpowers:writing-plans` a partir do spec acima (o próprio spec já
está commitado e revisado; a skill `brainstorming` normalmente pede pra
confirmar a leitura do spec antes de virar plano — perguntar ao Samuel se
já pode seguir direto ou se ele quer reler o arquivo primeiro).

### Resolução da pergunta em aberto do checkpoint 17/09 anterior

A pergunta "retomar pelos baldes de categorização ou pela coleta SRU?"
(ver seção mais abaixo, "Pergunta em aberto (17/09/2026)") foi respondida:
**os dois em paralelo.** Ambos foram disparados nesta sessão e continuam
**rodando em segundo plano, não concluídos** no momento deste checkpoint:

- **Coleta SRU da Gallica** (`gallica_crawl`, retomada de onde parou):
  em **378.750 / 934.427 registros (~40,5%)**, checkpoint em
  `saidas/gallica_crawl/dc-type-all-monographie-4d1e657b14/checkpoint.json`,
  atualizado pela última vez às 19:19:54 UTC de 17/09. **Ainda rodando**
  quando este handoff foi escrito — uma sessão futura deve checar esse
  arquivo de novo pra saber se terminou, e se não, pode simplesmente rodar
  o mesmo comando de novo (retoma sozinho pelo checkpoint).
- **Conserto da categorização do mapeamento por curadoria** (46.222 itens):
  delegado a um agente em segundo plano. **Categorização já finalizada e
  verificada** contra os 46.222 itens reais (distribuição final abaixo).
  **Tradução dos títulos ainda em andamento**: **22.879 / 46.222 (~49,5%)**
  no arquivo `saidas/amostra_categorizada_traduzida.json` (43MB, é o
  arquivo completo sendo preenchido incrementalmente, não uma amostra
  pequena apesar do nome — script novo, ainda sem teste, ver abaixo).
  Planilha final (índice + abas, padrão aprovado em 15/09) **ainda não foi
  gerada** — só depois que a tradução terminar.

**Distribuição final da categorização** (46.222 itens, baldes ajustados
pelo agente nesta sessão — números batem com o total, nenhum item
duplicado ou perdido):
- Literatura Clássica Francesa: 19.325 (41,8%)
- Outros (não coberto pelos baldes): 9.086 (19,7%)
- Paris e História Local: 7.663 (16,6%)
- Quadrinhos: 5.253 (11,4%)
- Ciências e Natureza: 2.611 (5,6%)
- Manuscritos Medievais: 1.193 (2,6%)
- Referência e Enciclopédias: 619 (1,3%)
- Traduções e Literaturas Estrangeiras: 280 (0,6%)
- Religião e Teologia: 192 (0,4%)

**Arquivos criados/alterados por esse agente, ainda NÃO commitados —
aguardando revisão do Samuel antes de virar commit** (instrução explícita
dada ao agente, pra não commitar lógica que o Samuel ainda não olhou):
- `scripts/categorizar_amostra_gallica.py` — modificado (baldes de
  palavra-chave refinados; 143 inserções/57 remoções no diff).
- `scripts/traduzir_titulos_lote_gallica.py` — novo, reaproveita o padrão
  de `core/enriquecimento_lote.py` pra traduzir em lotes retomáveis.
  **Está em uso agora mesmo pelo processo em segundo plano** — não editar
  nem apagar até o job atual terminar ou ser parado de propósito.

**Testes:** `pytest` rodado nesta sessão, **143 passando** (mesmo número
do checkpoint anterior — os scripts novos ficam fora do pacote testado,
mesmo padrão dos outros scripts em `scripts/`).

## Checkpoint 16/09/2026 — Coleta em cascata (motor multi-método), leia aqui primeiro

Sessão grande, focada numa peça nova de arquitetura pedida pelo Samuel: o
motor agora tenta **vários métodos de coleta em cascata** por site (API →
HTML → navegador automatizado), só avisando o Samuel quando nenhum
resolver. Plano completo (desenhado em plan mode, aprovado, depois
executado em "modo automático" combinado só pra esse plano) está salvo em
`C:\Users\fotog\.claude\plans\eu-quero-escrever-um-mighty-octopus.md`
(fora deste repositório — é um arquivo do Claude Code, não do projeto,
pode não existir mais numa máquina diferente). Resumo do que importa:

**Arquitetura nova, construída e testada (`pytest` passando — 143 testes,
antes eram 103):**
- `core/acao_humana.py` — sinal `AcaoHumanaNecessaria` (tipos: chave de
  API, login, CAPTCHA) pra um método dizer "preciso do Samuel" em vez de
  travar feio ou tentar burlar. Nunca deve ser capturado dentro de laço de
  retentativa de infraestrutura.
- `core/config_sites.py` — lê chave de API por site de `buscador.local.cfg`
  (`.ini`, nunca vai pro git). `buscador.local.cfg.exemplo` documenta o formato.
- `core/metodo_coleta.py` — a cascata (`MetodoColeta` + `coletar_em_cascata`):
  tenta métodos em ordem, um indisponível/que falha no meio só gera log
  discreto (o próximo método ainda pode resolver); só quando o **último**
  falha é que levanta `AcaoHumanaNecessaria` de verdade, juntando os motivos.
- `core/cookies_navegador.py` + `core/navegador.py` — primeira e segunda
  camada de resolver login: ler cookie do Chrome normal do Samuel
  (`browser_cookie3`), e se isso não bastar, navegador automatizado
  (`seleniumbase`, headless ou visível) com sessão persistente por site
  (perfil de Chrome isolado em `sessoes_navegador/<site>/`, gitignored).
  Quando o modo headless trava em login/CAPTCHA, abre uma janela visível
  **na hora** (`resolver_na_mao`), sem precisar de outro comando — o
  Samuel resolve olhando a tela, aperta Enter, a sessão fica salva e a
  coleta continua sozinha em segundo plano.
- `adapters/internet_archive.py` — primeira aplicação real da cascata
  (mais abaixo, seção própria).
- **Todo o código do pacote (`src/buscador/`, 22 arquivos) ganhou
  comentário explicativo linha a linha**, a pedido do Samuel (está
  aprendendo a programar) — nível "explica pra quem não sabe programar,
  mas não esconde o termo técnico". Convenção `# !` (extensão Better
  Comments do VS Code, fica vermelho) pros avisos críticos de
  segurança/ética, tipo a proibição do UC Mode/CDP Mode.

**Decisões fechadas nesta sessão, com o porquê:**
- **SeleniumBase** (não Selenium puro, não Playwright) pro navegador
  automatizado — mais tutorial em português, menos código de espera/
  localização de elemento pra escrever na mão.
- **UC Mode/CDP Mode do SeleniumBase são proibidos, sem exceção** — são
  recursos de disfarce contra detecção de robô. O Samuel pediu
  explicitamente pra desfazer essa regra e liberar o uso; recusei, e
  expliquei que é uma linha que sigo independente do que o projeto
  mandar. Reforçado de novo mais tarde na mesma sessão quando ele tentou
  a mesma coisa por outros ângulos (ver caso Scribd, abaixo) — a resposta
  não muda com reformulação.
- **`browser_cookie3` não funciona no Chrome do Samuel (versão 152)** —
  testado ao vivo. Motivo: "app-bound encryption", proteção que o Google
  colocou desde o Chrome 127 (meados de 2024) especificamente contra
  programas externos lendo cookie sem passar pelo navegador. Não é bug
  nosso, o código já trata isso direito (devolve `None`). **Não vamos
  tentar contornar essa proteção** — mesma categoria de regra do UC/CDP
  Mode. Na prática, quem resolve login de verdade hoje é a camada 2
  (sessão salva via navegador automatizado), não a camada 1.
- **Não usar o Chrome pessoal do Samuel pro navegador automatizado** —
  perfis isolados por site em vez disso. Motivos: o Chrome dele fica
  aberto o tempo todo (travaria a pasta de perfil), e um perfil isolado
  limita o que a automação consegue acessar só ao que foi explicitamente
  logado ali, sem expor o resto da vida digital dele.

**Caso Scribd — descartado como fonte, com justificativa forte:**
O Samuel queria abrir o Scribd, logar, e o programa "olhar" 5 livros pra
montar planilha. Chequei o `robots.txt` deles (protocolo da seção 7 do
CLAUDE.md) antes de escrever qualquer código: bloqueiam `/read/`,
`/viewer/`, `/full/`, `/doc/protected/` pra **qualquer** robô, e têm uma
regra nomeada bloqueando `Claude-Web`/`ClaudeBot` no site inteiro (junto
com outros bots de IA). Recusei construir isso, e recusei de novo em
várias reformulações que o Samuel tentou: usar o perfil de Chrome dele
("não muda quem está lendo, só onde"), eu abrir o navegador ao vivo sem
salvar código ("ainda é automação, arquivo salvo ou não"), trocar de
biblioteca pra Playwright ("a ferramenta nunca foi a questão"), procurar
ferramenta pronta de terceiros pra isso ("terceirizar não muda nada").
**Scribd fica descartado como fonte automatizável neste projeto**, mesmo
critério do zvdd.de (seção 12 do CLAUDE.md).

**Internet Archive — novo site cadastrado, confirmado viável e já com
adaptador real:**
- `robots.txt` do archive.org só bloqueia `/control/` e `/report/`
  (administrativo) — nenhuma restrição contra automação/IA.
- API oficial de busca (`archive.org/advancedsearch.php`, "Advanced
  Search API"), documentada, sem chave, JSON limpo. Confirmado ao vivo:
  busca por `subject:"theology"` sozinha já tem 234.243 resultados.
- `adapters/internet_archive.py`: `MetodoApiInternetArchive` (o método de
  verdade, usa a API) + `InternetArchiveAdapter` (embrulho fino que pluga
  esse método numa cascata de 1 item, pra funcionar com o `cli.py`
  existente) — é a primeira aplicação real da cascata em produção.
- **Testado ao vivo, ponta a ponta** (não só mock): `python -m
  buscador.cli "identifier:ellesmere-pride-and-prejudice" --adapter
  internet_archive` gerou uma planilha real, com título/autor/ano/link
  corretos e verificação de link real encontrando PDF na página.
- **Bug real encontrado e corrigido nesse teste ao vivo:** quando o IA não
  informa idioma, o adaptador colocava `""` em `extra["idioma_origem"]` —
  isso quebrava o fallback pra "auto" em `core/enriquecimento.py` (o
  `.get(chave, "auto")` só cai no padrão quando a CHAVE não existe, não
  quando o valor é vazio). Corrigido: a chave só é preenchida quando o
  idioma é conhecido de verdade.
- **Parte do acervo é "biblioteca de empréstimo"** (Controlled Digital
  Lending, campo `access-restricted-item` no metadado) — função oficial
  do IA, não precisa de login pra *listar* (Fase 1 só lista, não baixa),
  só fica marcado em `extra["access_restricted"]` pra quem for baixar
  depois saber.
- `archive.org` entrou em `REPO_HOSTS` de `core/verificacao_links.py`
  (mesmo tratamento da Gallica).

**Teste de login end-to-end: CONFIRMADO funcionando** (não ficou pendente —
ver detalhe completo na seção "O que falta", mais abaixo, incluindo as
lições sobre confundir pop-up do Chrome com login do site, e sobre matar o
processo certo pra não deixar janela órfã).

**`git`:** branch `feat/fase1-mapeador`, 13 commits nesta sessão (`7cd0bc6`
até `9b2e3af`), todos com `pytest` passando antes de cada commit, todos já
enviados (`git push`) pro GitHub.

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
  (branch de trabalho: `feat/fase1-mapeador`; commit mais recente em
  17/09/2026: `9b2e3af`, `pytest` passando — **143 testes** hoje, ver
  checkpoint 16/09/2026 no topo deste arquivo pra o que mudou desde então).
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

## O que falta

**CONFIRMADO em 16/09/2026: o mecanismo de login via navegador automatizado
funciona ponta a ponta.** Item de teste: `journeypity0000maye` ("The
journey and the pity", Pawel Mayewski), um `access-restricted-item` real do
Internet Archive (headless sem login mostra "SIGN UP | LOG IN" no topo e
área de leitura em branco). Fluxo confirmado: `abrir_navegador('internet_archive',
headless=False)` → Samuel loga na janela visível pela interface normal do
site → fechar o processo direito (matar a árvore inteira, não só o
`chromedriver` — ver lição abaixo) → reabrir `headless=True` → topo já
mostra "SAMUEL BOTTINI" em vez de "LOG IN", sem fazer nada a mais.

**Caminho até chegar lá (útil pra não repetir os mesmos tropeços):**
1. Levaram 4 tentativas na janela isolada até o login persistir de
   verdade — motivos: confundir o pop-up "Fazer login no Chrome" (do
   navegador) com o login do site; prazo cronometrado curto demais (90-180s)
   criando pressa; um crash esporádico de `chromedriver` (não era a causa
   raiz). A instrução que resolveu: deixar claro que a janela é nova/
   isolada, sem prazo, e avisar explicitamente pra ignorar qualquer pop-up
   do próprio Chrome sobre conta/sincronização.
2. **No meio disso, tentamos trocar pra um perfil de Chrome de verdade**
   (um dos que aparecem no seletor "Quem está usando o Chrome?" do Samuel),
   a pedido dele, achando que resolveria a confusão — **mas esbarrou numa
   trava técnica real do Chrome**: ele usa um "cadeado de instância única"
   na pasta raiz inteira (`User Data`), não por perfil, então com o Chrome
   pessoal do Samuel sempre aberto, um segundo processo independente
   (nosso automatizador) é recusado mesmo pedindo um perfil diferente
   (`SessionNotCreatedException: Unable to set user_data_dir while
   starting Chrome`). Voltamos pro perfil isolado (que tem raiz própria,
   sem esse conflito) — era a decisão tecnicamente certa desde o início.
3. **Lição sobre fechar a janela direito:** matar só o processo do
   `chromedriver` não mata o Chrome que ele abriu — fica um processo órfão
   preso na pasta de perfil (`Device or resource busy` ao tentar apagar a
   pasta depois). Isso pode ter causado confusão em tentativas anteriores
   (Samuel logando numa janela enquanto uma janela órfã mais antiga era a
   que eu conferia depois). **Jeito certo de fechar** (usado com sucesso):
   achar o processo principal via
   `Get-CimInstance Win32_Process -Filter "Name='chrome.exe'" | Where-Object { $_.CommandLine -like '*sessoes_navegador*<nome>*' -and $_.CommandLine -notlike '*--type=*' }`
   (o `-notlike '*--type=*'` exclui os processos-filho: gpu-process,
   renderer, crashpad-handler etc.) e `Stop-Process -Id <esse> -Force` —
   isso mata a árvore inteira de uma vez.

**Dois requisitos anotados pra depois** (seção 6 do `CLAUDE.md`,
16/09/2026): trocar/escolher o nome do perfil isolado de dentro do futuro
dashboard; guardar email/senha de site (só os que permitem login
automatizado) pra reaproveitar sem janela visível toda vez — o
armazenamento (`core/config_sites.py`) já serve pra isso, falta só o
código de preencher/enviar o formulário, que é por site.

**As 11 fatias do plano de coleta em cascata estão todas feitas** (incluindo
o passo 9, `buscador/logar.py` — comando avulso, reaproveita
`resolver_na_mao()`, já confirmado funcionando). Plano completo salvo em
`C:\Users\fotog\.claude\plans\eu-quero-escrever-um-mighty-octopus.md`.
143 testes passando. **Próximo passo em aberto:** não há mais nenhum passo
do plano original pendente — decidir com o Samuel o que vem a seguir (ex.:
um segundo site real usando a cascata de verdade — Internet Archive hoje só
usa o método de API; testar o método do navegador automatizado dentro de um
adapter de verdade ainda não aconteceu, só testado solto/manualmente; ou
começar a Fase 2 do roadmap).

**Fases futuras do projeto (ver CLAUDE.md seção 10), ainda não começadas:**
- **Fase 2** — baixar os PDFs marcados (inclusive atrás de login já feito
  pelo Samuel).
- **Fase 3** — baixar já organizando por categoria/seção.
- **Fase 4** — catalogar (OCR, bases online, IA opcional).
- **Fase 5** — buscar por nome em todos os sites cadastrados.
- Antes de começar a Fase 2: seguir a seção 4 do CLAUDE.md (plan mode por
  fase) de novo.

**Atualizado no checkpoint 17/09/2026 (sessão 2)** — as duas pendências
abaixo não estão mais paradas, estão **rodando em segundo plano** (ver
checkpoint no topo do arquivo pro progresso exato e os arquivos ainda não
commitados):
- Coleta SRU em massa da Gallica: retomada, em ~40,5% (378.750/934.427).
- Baldes de categorização do mapeamento por curadoria: **já ajustados e
  finalizados**; falta só a tradução terminar (~49,5% feito) pra gerar a
  planilha final.

## Pergunta em aberto (17/09/2026) — RESOLVIDA na sessão seguinte

Samuel perguntou "vamos voltar a planilha do Gallica, ela foi terminada?" —
respondi que não, e expliquei os dois caminhos parados (ver seção acima).
A pergunta exata que tinha ficado sem resposta era se retomar pelos baldes
de categorização ou pela coleta SRU — **resposta: os dois, em paralelo**.
Ver o checkpoint 17/09/2026 (sessão 2) no topo deste arquivo pro estado
atual de cada um (nenhum dos dois concluído ainda no momento desse
checkpoint).

## Como rodar

```
D:\programas\BuscadorBaixador\.venv\Scripts\python.exe -m pytest -q
D:\programas\BuscadorBaixador\.venv\Scripts\python.exe -m buscador.cli "https://grand-sud-medieval.fr/forum/viewtopic.php?f=14&t=<ID>"
D:\programas\BuscadorBaixador\.venv\Scripts\python.exe -m buscador.cli "gallica all Clavius" --adapter gallica
D:\programas\BuscadorBaixador\.venv\Scripts\python.exe -m buscador.cli "subject:theology AND mediatype:texts" --adapter internet_archive
```

**Ambiente instalado nesta sessão** (16/09/2026, além do que já existia):
`browser-cookie3` e `seleniumbase` (adicionados a `pyproject.toml` —
`pip install -e ".[dev]"` reinstala tudo). O SeleniumBase baixou sozinho
o `chromedriver` 152.0.7977.82 (compatível com o Chrome 152 instalado) em
`.venv\Lib\site-packages\seleniumbase\drivers\` — automático, não precisa
fazer nada manual.

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
