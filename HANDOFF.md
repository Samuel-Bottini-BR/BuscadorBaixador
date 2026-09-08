# Buscador e Baixador — estado atual

## O que é e para quem

Aplicativo local (Windows) para o Instituto São Bento achar, baixar e
catalogar obras digitalizadas (livros esgotados, artigos) espalhadas em
sites e fóruns. Usuários: Samuel e o Kaique (leigo, sem formação técnica —
interface precisa ser simples, em português). Regras completas do projeto,
arquitetura e protocolo de decisões estão em `CLAUDE.md` — leia lá primeiro.

## Estado atual

**Fase 1 ("mapear um site → planilha") concluída.** Dado uma URL (tópico do
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
  (branch de trabalho: `feat/fase1-mapeador`, commit mais recente `6e3f4d2`,
  `pytest` passando a cada commit — 64 testes no total).
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

## Pergunta em aberto (retomar exatamente aqui)

Samuel pediu "vamos mapear o site inteiro, primeiro" — depois de idas e vindas
(pensei que fosse o fórum Grand Sud; era sobre a **Gallica**), chegamos a:
a busca `"gallica all Clavius"` que rodamos tem **9739 resultados no total**
(`<srw:numberOfRecords>9739</srw:numberOfRecords>`, confirmado no XML cru),
não só os 50 da primeira página que processamos. A pergunta exata que ficou
sem resposta (a última pergunta que fiz, ele interrompeu antes de responder):

> A busca 'gallica all Clavius' tem 9739 resultados no total. Você quer dizer:
> mapear TODOS os 9739 resultados dessa busca específica sobre Clavius? (Se
> sim, são ~195 páginas de 50, respeitando o intervalo educado — e a busca
> "all" da Gallica é frouxa, traz bastante ruído tipo jornais franceses do
> séc. XIX que só citam Clavius de passagem.) Ou "o site inteiro" era outra
> ideia — nesse caso, perguntar o que ele quer buscar/mapear de verdade.

**Antes de implementar isso:** se for mesmo "todos os 9739", pensar em: (a)
como isso interage com o rate limit por cota da Gallica (ver pendência
abaixo) — 195 páginas seguidas provavelmente estoura o limite, precisa de um
intervalo bem maior entre páginas ou rodar em lotes ao longo de várias horas;
(b) vale a pena refinar a consulta CQL antes (`gallica adj "Christophori
Clavii"` ou algo mais estrito) para reduzir o ruído, em vez de aceitar os
9739 brutos — isso é uma decisão de trade-off pra apresentar ao Samuel
(seção 3 do CLAUDE.md), não decidir sozinho.

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
Ou clique duas vezes em `mapear.bat` (usa o `.venv` do projeto direto, não
depende do que estiver no PATH). O `.venv` já está criado com Python 3.12 e
o pacote instalado em modo editável — `pip install -e ".[dev]"` se precisar
reinstalar.
