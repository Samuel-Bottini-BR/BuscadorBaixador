# Buscador e Baixador — estado atual

## Checkpoint 24/09/2026 (sessão 7) — mapeamento por curadoria FINALIZADO (dedup + categorização + tradução, 26.544/26.544); download em lote ainda bloqueado, com achado novo — leia aqui primeiro

**Retomado pelo comando `/projeto`.** Contexto herdado da sessão 6 (checkpoint
logo abaixo): o mecanismo de download em lote da Gallica (Tarefa C4) tinha
travado num bloqueio não resolvido. Nesta sessão, duas frentes avançaram: (1)
uma nova tentativa do download real, que revelou um achado importante sobre o
bloqueio; (2) o mapeamento por curadoria editorial (46.222 itens, pendência
desde 12-13/09) foi **finalizado de ponta a ponta** — dedup, categorização e
tradução, os três com resultado real confirmado, não só código.

### Download em lote da Gallica: tentativa nova, ainda bloqueado, achado importante

Depois de esperar (a pedido do Samuel, "já esperei o tempo"), rodei um lote
real de 15 itens (amostra nova, seed diferente da sessão 6, pra não repetir os
mesmos 40 que já tinham falhado). **Resultado: 15/15 falhas de novo — mas com
tipos de erro DIFERENTES da sessão 6**, o que muda a interpretação:
- 5 itens: mesmo padrão de antes (desafio anti-robô não passou em 180s).
- 5 itens: **503 Service Unavailable** no endpoint de download — NOVO; antes o
  site respondia 200 com a página do desafio, nunca 503.
- 5 itens: **timeout de conexão puro** (site nem respondeu em 15s) — também
  NOVO.

**Interpretação (não confirmada com certeza):** a mistura de 503 + timeout de
conexão puro enfraquece a teoria de "só throttling do Altcha que reseta em um
dia" da sessão 6 — pode ser algo mais forte/duradouro do lado da Gallica, ou
até instabilidade genuína da infraestrutura da BnF sem relação nenhuma com
nossas tentativas anteriores. **Não foi investigado mais a fundo** (ex.: não
testei se `gallica.bnf.fr` está acessível normalmente por fora do mecanismo de
download) — isso ficou oferecido ao Samuel como próximo passo, sem resposta
ainda. **Nenhuma tentativa de contorno foi feita** (sem disfarce, sem proxy,
sem trocar User-Agent) — mesma linha de sempre. Limpeza feita: pasta de teste
(`saidas/gallica_download_teste/`, só continha falha) removida; confirmado
via `Get-CimInstance`/`tasklist` que não sobrou processo Chrome órfão nem PDF
parcial.

### Mapeamento por curadoria (46.222 itens): FINALIZADO — dedup, categorização e tradução, os três com resultado real

Isso resolve a pendência que estava em aberto desde a sessão 2 (17/09) e o
Achado da sessão 6 sobre 46.222 vs 26.544 (ver seção "O que aconteceu com o
mapeamento da Gallica", mais abaixo, pro histórico completo de como esse
número apareceu). Trabalho pedido explicitamente pelo Samuel nesta sessão
("vamos corrigir definitivamente o problema de duplicatas e categorias"),
executado por um agente em segundo plano (dedup + recategorização) enquanto a
conversa principal seguia noutras coisas, e a tradução rodada eu mesmo depois.
**Tudo verificado de forma independente por mim antes de reportar como
concluído** (reli os scripts gerados, recontei os números).

1. **Deduplicação por ark_id** — script novo `scripts/deduplicar_gallica_por_ark.py`.
   Reaproveita infraestrutura já testada (`core/cruzamento.py::colapsar_por_chave`
   + `core/chaves_gallica.py::extrair_ark_id`), não reimplementa dedup na mão.
   **Confirmado ao vivo**: todos os 46.222 itens têm ark_id extraível (zero sem
   chave — checado antes de rodar, não só depois). Resultado: **46.222 → 26.544
   obras únicas** (7.862 grupos tinham duplicata — o mesmo livro aparecendo sob
   mais de uma trilha de navegação, porque a Gallica cruza links entre
   categorias diferentes). Saída: `saidas/gallica_mapa_livros_dedupado.json`
   (gitignored).
2. **Recategorização sobre a lista deduplicada** — `scripts/categorizar_amostra_gallica.py`
   ajustado pra ler `gallica_mapa_livros_dedupado.json` em vez do bruto.
   **Importante: o algoritmo de categorização (`categorizar()`, os `BALDES`)
   NÃO foi mudado** — ele já estava correto desde a sessão 2 (usa só o ÚLTIMO
   segmento da trilha de navegação + título como reforço, nunca a trilha
   inteira; ver seção "Padrão de planilha aprovado", mais abaixo, pro
   histórico). A única mudança foi a fonte dos dados (deduplicada em vez de
   bruta com repetição) — isso já resolve a distorção de contagem sozinho.
   Distribuição final sobre as 26.544 obras únicas (soma confere exato, sem
   item perdido nem duplicado — o próprio script verifica isso com um assert):
   - Literatura Clássica Francesa: 8.143 (30,7%)
   - **Outros: 6.757 (25,5%)** — ainda a 2ª maior fatia; ver pergunta em aberto abaixo
   - Paris e História Local: 4.961 (18,7%)
   - Quadrinhos: 3.394 (12,8%)
   - Ciências e Natureza: 1.758 (6,6%)
   - Manuscritos Medievais: 746 (2,8%)
   - Referência e Enciclopédias: 451 (1,7%)
   - Traduções e Literaturas Estrangeiras: 231 (0,9%)
   - Religião e Teologia: 103 (0,4%)
   Saída: `saidas/gallica_categorizado_dedupado.json` (gitignored). O arquivo
   antigo `saidas/gallica_categorizado_completo.json` (rodada sobre o bruto,
   46.222 com duplicata) ficou intacto, de referência.
3. **Tradução completa (100%)** — `scripts/traduzir_titulos_lote_gallica.py`
   ajustado pra ler a lista deduplicada+categorizada. **Rodado ao vivo até o
   fim, 4 passadas retomáveis** (o script já é desenhado pra isso — cada
   passada só tenta de novo quem ainda não tem `titulo_traduzido`):
   - Passada 1: 24.635/26.544 (92,8%) em 117,6 min.
   - Passada 2: +1.431 (só os 1.909 pendentes da 1ª) em 11,8 min.
   - Passada 3: +249 (só os 478 pendentes da 2ª) em 3,0 min.
   - Passada 4: +229 (só os 229 pendentes da 3ª) em 0,8 min. **100% concluído,
     zero pendente.**
   **Achado confirmado ao vivo** (a docstring do script já previa isso, mas
   nunca tinha sido confirmado até esta sessão): o motivo de sobrar pendente
   entre passadas não é falha permanente, é timeout de lote em títulos "fora
   do francês comum" (occitano medieval, transliteração árabe) que demoram
   minutos em vez de frações de segundo — retomar com menos itens concorrendo
   pelos mesmos 8 workers deixa eles terminarem dentro da janela de 180s.
   **Nenhum título ficou permanentemente travado** nesta rodada real (zero
   restante depois de 4 passadas) — mas isso pode não valer pra sempre se o
   dataset mudar; se uma sessão futura rodar de novo e ver pendência que não
   cai mesmo depois de várias passadas, não é bug, é esperado (ver docstring
   do script).
   Saída: `saidas/gallica_categorizado_traduzido.json` (gitignored, 26.544
   itens, campos `titulo`, `titulo_traduzido`, `categoria_padronizada`,
   `ark_id`, `link`). Qualidade da tradução ainda é a offline (fr→en→pt via
   argostranslate) — a pergunta de qualidade (aceitar ou tentar melhorar)
   continua em aberto, ver abaixo.
4. **Os 3 `.bat` irmãos corrigidos** (`gallica_crawl.bat`, `gallica_enriquecer.bat`,
   `mapear.bat`) — mesmo fix de 1 caractere que o `jobs.bat` já tinha
   (`-e "%~dp0"` → `-e "%~dp0."`; sem o ponto final, a barra invertida de
   `%~dp0` escapa a aspa final e quebra o argumento do pip). Autorizado
   explicitamente pelo Samuel nesta sessão.

**Achado à parte, sem consequência real (registrado só pra não confundir
sessão futura):** ao imprimir títulos com acento no terminal Git Bash deste
projeto, aparece um caractere de substituição (tipo "ob�issance" em vez de
"obéissance") — **isso é só a codepage do console, não um problema real nos
dados.** Confirmado: o arquivo JSON tem zero ocorrências reais do caractere
de substituição Unicode; escrever o título num arquivo e ler de volta mostra
o acento certinho. Não gastar tempo investigando "corrupção de dado" se isso
aparecer nu terminal de novo — é cosmético do terminal.

**Commit feito e enviado**: `c70a507` na branch `feat/gallica-cruzamento-download`
(ainda não mesclada na `master` — decisão do Samuel em aberto, igual sessões
anteriores). Inclui os 3 scripts (`deduplicar_gallica_por_ark.py` novo,
`categorizar_amostra_gallica.py` e `traduzir_titulos_lote_gallica.py`
ajustados) e os 3 `.bat` corrigidos. **Nada de `saidas/` entrou no commit**
(gitignored, como sempre). 324 testes continuam passando (rodado antes do
commit).

### Perguntas em aberto (exatas) — atualizado nesta sessão

1. **Os 6.757 itens em "Outros" (25,5% das 26.544 obras únicas, número NOVO
   desta sessão — antes era 9.086 sobre o bruto com duplicata)**: criar
   balde(s) novo(s) ou deixar assim? (pergunta antiga, só o número mudou)
2. **Qualidade da tradução offline** (fr→en→pt via argostranslate, sem
   passar por Google/MyMemory que já se mostraram sem cota suficiente pra
   este volume): aceitar como está, ou vale tentar melhorar depois (ex.:
   esperar cota do MyMemory resetar, ou pagar API)? (pergunta antiga)
3. **Gerar a planilha final** (padrão "índice + abas" aprovado em 15/09) a
   partir de `saidas/gallica_categorizado_traduzido.json` — falta rodar
   `scripts/gerar_planilha_padrao_gallica.py` (hoje só roda em cima da
   amostra pequena de teste; precisa confirmar se aceita a lista de 26.544
   direto ou se precisa de ajuste). Perguntei ao Samuel se quer isso agora ou
   prefere decidir a pergunta 1 primeiro — ficou sem resposta (foi pro
   `/checkpoint` antes de decidir).
4. **Download bloqueado (ver seção acima)**: se o bloqueio persistir, vale
   (a) investigar se é a Gallica inteira fora do ar (não só o download) ou
   (b) reduzir mais o lote de teste (5 itens?) ou (c) só esperar mais tempo
   de novo. Não decidido.
5. Pendências mais antigas, ainda sem resposta (ver checkpoints anteriores
   pro texto exato): salvar o relatório de pesquisa do Livro Profecias TIA
   dentro daquele projeto; mesclar `feat/gallica-cruzamento-download` na
   `master`.

**Próximo passo recomendado:** decidir a pergunta 1 (baldes "Outros") e/ou a
pergunta 3 (gerar planilha final) — o mapeamento por curadoria está
tecnicamente pronto pra virar planilha entregável, só falta essa decisão (ou
autorização pra gerar do jeito que está, com "Outros" como categoria
residual). Em paralelo, considerar investigar a causa do 503/timeout do
download (pergunta 4) antes de tentar de novo.

**Como rodar/testar:**
```
D:\programas\BuscadorBaixador\.venv\Scripts\python.exe -m pytest -q
D:\programas\BuscadorBaixador\.venv\Scripts\python.exe scripts\deduplicar_gallica_por_ark.py
D:\programas\BuscadorBaixador\.venv\Scripts\python.exe scripts\categorizar_amostra_gallica.py
D:\programas\BuscadorBaixador\.venv\Scripts\python.exe scripts\traduzir_titulos_lote_gallica.py
```
(os 3 scripts acima são idempotentes/retomáveis — rodar de novo sem mudar
nada não deveria alterar o resultado já salvo, exceto o de tradução, que só
mexe em itens ainda sem `titulo_traduzido`.)

**Ambiente:** nada novo instalado nesta sessão — mesmo `.venv` das sessões
anteriores.

## Checkpoint 23/09/2026 (sessão 6) — Tarefa C4 (download em lote) implementada e testada; lote real BLOQUEADO pela Gallica hoje — leia aqui primeiro

**Contexto que este handoff NÃO tinha até agora:** entre a sessão 5 (checkpoint
abaixo) e esta sessão, houve uma sessão inteira (mesmo dia 22/09, branch nova
`feat/gallica-cruzamento-download`) que implementou um plano grande de
cruzamento + download da Gallica, mas **nunca atualizou este arquivo** — só o
ledger interno (`.superpowers/sdd/vamos-colocar-essas-coisas-federated-cherny/`,
gitignored). Esta seção cobre as duas sessões (22/09 e 23/09) juntas, já que
nenhuma das duas tinha sido registrada aqui ainda.

**Branch:** `feat/gallica-cruzamento-download`, 17 commits (`08ceb4b..7d3615f`),
**enviada ao GitHub nesta sessão pela primeira vez** (não tinha remoto
configurado — 13 commits ficaram só locais por uma sessão inteira até eu notar
e dar `git push -u origin ...`). `master` continua no estado do motor de jobs
(checkpoint 20/09 abaixo) — **esta branch ainda não foi mesclada**, decisão do
Samuel em aberto.

**O que está pronto e commitado nesta branch:**
- **Parte A** (cruzamento/dedup genérico, `core/cruzamento.py`) e **Parte B**
  (backfill de metadado em lote, `core/backfill_gallica.py`) — completas,
  revisadas (subagent-driven-development), sem pendência.
- **Parte C, mecanismo de download (C-nav1 a C-nav8)**: navegador real
  (`seleniumbase`, sem nenhum disfarce/UC-Mode) com janela **escondida**
  (posição fora da tela + flag anti-throttling do Chrome) resolve o desafio
  anti-robô "Altcha" da Gallica sozinho. **Confirmado ao vivo com sucesso**
  nesta sessão: PDF real de 28.543.823 bytes baixado, nenhuma janela visível,
  69,2s (`core/download_gallica_navegador.py::baixar_via_navegador`).
- **Tarefa C4 (motor de download em lote), implementada nesta sessão**:
  `core/baixar_gallica.py` — `CheckpointDownload`, `baixar_um`, `baixar_lote`.
  Mesmo desenho de resiliência do backfill (checkpoint retomável, catálogo
  permanente mesclado via `salvar_json_atomico`, falha isolada de 1 item não
  derruba o lote). **Só validado por teste automatizado (mockado) — a
  execução real contra a Gallica está BLOQUEADA, ver abaixo.**
- **324 testes passando** (`pytest -q`, ~32s).

**A4 (CLI de cruzamento que geraria a lista definitiva de arks faltantes)
NUNCA foi implementada** — só A0-A3 (as peças de apoio) existem. O número
"26.876 obras da lista-alvo" citado no plano original é só a contagem bruta de
ark ids únicos do mapeamento por curadoria (`saidas/gallica_mapa_livros.json`,
46.222 itens), não o resultado de cruzar com a coleta SRU. Pra testar o
download sem esperar A4, usei uma amostra direto desse mapeamento.

**Achado corrigido: `extrair_ark_id` grudava lixo no final do ark id.**
~15% dos ark ids únicos do mapeamento (4.193 de 26.876) vinham com sufixo
grudado (`.item` sem barra antes, `?rk=...` de busca, `#` de fragmento,
pontuação/espaço de raspagem) porque a regex antiga só sabia parar numa barra
`/`. Corrigida pra parar em qualquer caractere não-alfanumérico
(`core/chaves_gallica.py`, commit `eca39fc`, TDD com 4 exemplos reais tirados
do próprio dataset). **Contagem real de ark ids únicos, com o fix: 26.544**
(não 26.876 — usar esse número daqui pra frente, inclusive quando A4 for
implementada).

**Achado corrigido: timeout de download curto demais.** O default de
`baixar_via_navegador` era 60s — a Tarefa C-nav8 (mais cedo nesta sessão) já
tinha levado 69,2s pra completar com sucesso, quase sem margem. Confirmado ao
vivo: um lote de teste com 60s deu **9/9 falhas**. Subi o default pra **180s**
e adicionei `timeout_segundos` configurável em `baixar_um`/`baixar_lote`
(commit `7d3615f`), que antes não existia.

**BLOQUEIO ATUAL (não resolvido, sem tentativa de contorno): o lote real de
download parou de funcionar depois de muitas tentativas seguidas hoje.**
Mesmo com o timeout corrigido pra 180s, um segundo lote de teste real (40
itens, ~115 minutos de execução) deu **40/40 falhas**. Investigado (sem
decidir nada sozinho, sem tentar burlar nada):
- GET simples (sem navegador) na página-base e no `.pdf` devolvem 200 normal
  — não é bloqueio HTTP básico tipo 429. O `.pdf` devolve a própria página
  HTML do desafio ("Gallica | Vérification de sécurité", Altcha).
- Um banner de consentimento de cookies aparece na página (achado via
  screenshot) — testado e **descartado como causa**: cliquei em "Tout
  accepter" via JavaScript (interação normal, sem disfarce) antes de navegar
  pro `.pdf`, e o download **ainda falhou** (controle isolado, 1 item, 90s).
- A explicação mais provável (não confirmada com certeza): a MESMA técnica
  funcionou ao vivo mais cedo no mesmo dia (C-nav8: sucesso, 69,2s) e parou de
  funcionar depois de ~49 tentativas consecutivas nesta sessão (9 + 40). Tem
  cheiro de throttling/escalonamento do desafio Altcha do lado do site em
  resposta ao volume de hoje — mesmo padrão de 429/cooldown já visto várias
  vezes neste projeto (coleta SRU, backfill). **Não é um bug de código** —
  os dois fixes desta sessão (timeout, extrair_ark_id) continuam válidos e
  corretos, só não bastaram pra destravar isso.
- Limpeza feita: `saidas/gallica_download_teste/` (job de teste, todo falha,
  nada de útil pra preservar) removido; nenhum processo `chrome.exe`/
  `chromedriver.exe` órfão (confirmado via `tasklist`).

**Próximo passo recomendado:** esperar (talvez um dia) e tentar de novo o
lote real — o mecanismo em si (C-nav1 a C-nav8) está correto e confirmado
funcionando pelo menos uma vez. A amostra de 40 ark ids usada nesta sessão
não foi salva no repo (ficou só no scratchpad temporário da sessão, perdida);
gerar uma nova amostra real assim (Git Bash, raiz do projeto):

```
.venv/Scripts/python.exe -c "
import json, random, sys
sys.path.insert(0, 'src')
from buscador.core.chaves_gallica import extrair_ark_id
itens = json.load(open('saidas/gallica_mapa_livros.json', encoding='utf-8'))
unicos = sorted({extrair_ark_id(i['link']) for i in itens} - {None})
random.seed(42)  # mesma seed da sessão 6, pra reprodutibilidade
amostra = random.sample(unicos, 40)
json.dump(amostra, open('amostra_c4.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
print(len(unicos), 'unicos;', len(amostra), 'na amostra')
"
```

Depois rodar o lote de verdade (pode levar dezenas de minutos a horas — cada
item passa pelo navegador real; rodar em segundo plano):

```
.venv/Scripts/python.exe -c "
import json, sys
sys.path.insert(0, 'src')
from buscador.core.baixar_gallica import baixar_lote
ark_ids = json.load(open('amostra_c4.json', encoding='utf-8'))
checkpoint = baixar_lote(ark_ids, 'saidas/gallica_download_teste/job',
    'saidas/gallica_download_teste/pdfs', 'saidas/gallica_download_teste/catalogo.json',
    progresso_fct=lambda cp: print(cp))
print(checkpoint)
"
```

O checkpoint é retomável — se parar no meio (interrupção, falha, timeout do
terminal), rodar o mesmo comando de novo continua de onde parou, sem duplicar
nem perder nada já baixado/catalogado. Se o bloqueio persistir mesmo depois
de esperar, considerar: (a) reduzir o tamanho do lote de teste (10-15 itens
em vez de 40) pra gerar menos volume de tentativas seguidas; (b) intervalo
maior entre itens (hoje `baixar_lote` não tem cooldown nenhum entre
downloads, diferente de `backfill`/`coleta_gallica`, que pausam em 429 —
pode valer adicionar um `dormir` fixo pequeno entre itens).

**Pendências antigas (sessão 5, ainda sem decisão do Samuel — não tocadas
nesta sessão, working tree ainda tem):**
1. `scripts/categorizar_amostra_gallica.py` (modificado) e
   `scripts/traduzir_titulos_lote_gallica.py` (novo) — aguardando decisão
   sobre os 9.086 itens em "Outros" e a qualidade da tradução offline (ver
   checkpoint 20/09 abaixo, "Perguntas em aberto pro Samuel", itens 1-3).
2. Os 3 `.bat` irmãos com o mesmo bug de pip do `jobs.bat` — sem correção.
3. 4 PDFs soltos em `Claude outputs/` são de outro projeto (Livro Profecias
   TIA) — não commitar, é conhecido.

**Ambiente:** nada novo instalado nesta sessão — mesmo `.venv` Python 3.12.10
das sessões anteriores. `pywin32` (`win32gui`/`win32api`) já estava disponível
e foi usado só pra diagnóstico (scripts fora do repo, no scratchpad da sessão),
não é dependência nova do projeto.

## Checkpoint 20/09/2026 (sessão 5) — motor de jobs PRONTO (correção + smoke manual feitos, na master); coleta SRU da Gallica TERMINOU — leia aqui primeiro

**Estado:** branch de trabalho `feat/fase1-mapeador` **já integrada na `master`** (merge local sem checkout, fast-forward `fad9010..621748d`, `git push origin master` feito) — a `master` do GitHub tem o motor de jobs completo. **242 testes passando** (rodados nesta sessão, ~21 s). Retomado pelo comando `/projeto`; Samuel pediu "a onda de correção + smoke manual + relançar a coleta" e tudo foi concluído nesta sessão.

**A onda de correção (9 itens do revisor final, ver sessão 4) foi implementada e re-revisada: 9/9 ADDRESSED, 0 Critical/Important.** 9 commits (`d0312a4`..`621748d`), 30 testes novos (212→242). Detalhe de cada item, evidência RED/GREEN e o re-review completo: `.superpowers/sdd/2026-09-17-motor-de-jobs/final-fix-wave-report.md` (relatório do implementador) e `progress.md` (ledger, com o veredito do re-review). Achado do re-review, não bloqueante: o aviso do item 6 (`RuntimeWarning` quando o plano B sem `CREATE_BREAKAWAY_FROM_JOB` é usado) sai *antes* de confirmar que o 2º `Popen` deu certo — cosmético, mais preciso avisar depois.

**Smoke manual (obrigatório, ver sessão 4) — os 3 itens, todos confirmados:**
- **(i) sobrevivência à sessão: PASSOU**, com um teste de laboratório de verdade (não só leitura de código): um processo "sessão" dentro de um Job Object do Windows com `KILL_ON_JOB_CLOSE` inicia um job pelo motor e é morto 1s depois. Com `BREAKAWAY_OK` no job da sessão (o caso real): o executor sobreviveu, terminou `concluido`. Controle sem `BREAKAWAY_OK`: o executor morreu (prova que o teste detecta morte de verdade). **Achado extra, registrado mas não corrigido (fora da onda, é o follow-up "IsProcessInJob" que já estava previsto):** existe uma combinação de laboratório (host cujo processo pai é o launcher do `.venv`, que tem seu próprio job com `SILENT_BREAKAWAY_OK`, dentro de um job do usuário SEM `BREAKAWAY_OK`) onde o `Popen` com `CREATE_BREAKAWAY_FROM_JOB` é aceito em silêncio mas o neto continua preso — o aviso do item 6 não dispara porque não houve `OSError`. **Não reproduz no ambiente real** (medido: processos deste terminal não estão em job nenhum; o launcher do `.venv` cria job próprio mas o neto com breakaway sai de qualquer job). Deixa de ser risco prático aqui, mas é a lacuna que a detecção via `IsProcessInJob` (já listada como follow-up) resolveria de vez.
- **(ii) balão real do Windows, de processo destacado sem console: CONFIRMADO.** `avisar_windows` chamado de um processo `DETACHED_PROCESS` retornou em 0,2s; `win11toast.notify()` chamado direto (sem o try/except de cortesia) devolveu um `ToastNotification` sem levantar exceção — o balão foi de fato criado pelo Windows.
- **(iii) `.bat` corrigido e verificado:** `jobs.bat` (item 7 da onda) não imprime mais o bloco de erro do pip.

**Merge feito (Ruling 25 no ledger):** sem `git checkout` (pra não trocar os arquivos debaixo da coleta que estava rodando) — `git fetch . feat/fase1-mapeador:master` (só avança se for fast-forward) + `git push origin master`. Autorizado pela regra do CLAUDE.md (commit/push regulares sem perguntar cada vez) + pela escolha do Samuel quando perguntado como fechar a branch ("Juntar na master"). **NÃO foi feito merge de Pull Request nem qualquer coisa que precisasse de aprovação no GitHub** — é branch de trabalho de um repo pessoal.

**Coleta SRU da Gallica (`dc.type all "monographie"`) — TERMINOU DE VERDADE nesta sessão**, relançada pelo motor (retomou sozinha do checkpoint em 610.301) e concluiu em 2026-09-20T15:23:22Z: **934.581 registros** (a API revisou o total de 934.427 pra 934.581 durante a coleta — normal, o catálogo muda). Arquivo: `saidas/gallica_crawl/dc-type-all-monographie-4d1e657b14/itens.csv` (357MB, **gitignored** por `saidas/*` — nunca vai pro commit). **Ainda não passou pela Etapa 2** (`gallica_enriquecer`, que verifica link e traduz) — é dado bruto da API por enquanto.

**As DUAS coleções da Gallica não devem ser confundidas** (Samuel perguntou nesta sessão, deixando registrado aqui pra não se perder de novo):
1. **Coleta SRU** (a de cima, recém-terminada) — via API oficial `dc.type all "monographie"`, 934.581 registros, metadado confiável (autor/ano/idioma/domínio público) mas **sem categoria temática boa nem tradução ainda** (falta a Etapa 2).
2. **Mapeamento por curadoria editorial** (sessões 12-17/09, ver checkpoints mais abaixo) — 46.222 itens das páginas "seleções" do site, já categorizados em 9 baldes e com planilha final pronta (`saidas/gallica_livros_padrao.xlsx`, 2,1MB, padrão "índice + abas"). **Os 2 scripts que geraram isso (`scripts/categorizar_amostra_gallica.py` modificado, `scripts/traduzir_titulos_lote_gallica.py` novo) continuam SEM COMMIT**, esperando revisão do Samuel (pergunta 1 abaixo, ainda sem resposta).

**Ledger do plano do motor de jobs — NÃO apagado ainda** (`.superpowers/sdd/2026-09-17-motor-de-jobs/`, gitignored, ~600KB): guarda os 25 `Ruling:` (decisões tomadas em nome do Samuel, cada uma com "custo se errado"), todos os minors deferidos e o histórico completo task a task. Cópia lida só das rulings: `.superpowers/sdd/decisoes-tomadas-motor-de-jobs.md`. Apagar quando o Samuel confirmar que já viu as decisões — não é urgente (gitignored, não pesa no repo).

**Próximo passo recomendado:** nenhum item técnico pendente no motor de jobs em si — as 4 perguntas abertas pro Samuel (ver lista abaixo, carregada da sessão 4, ainda sem resposta) são o que trava o próximo avanço real (rodar a Etapa 2 sobre a coleta SRU, decidir sobre os baldes/tradução do mapeamento por curadoria, ou começar a Fase 2 do roadmap).

## Checkpoint 19/09/2026 (sessão 4) — motor de jobs IMPLEMENTADO (10/10 tasks); falta 1 onda de correção + smoke manual

**Estado:** branch `feat/fase1-mapeador`, HEAD `f799a06`. **212 testes passando** (rodados nesta sessão, ~20 s). O motor de jobs do plano de 17/09 foi construído por completo, task a task, com ajudantes (skill `superpowers:subagent-driven-development`; ~33 agents; cada task teve implementador + revisor, e rodadas de correção quando o revisor achou defeito real — 7 das 10 tasks). **Só validado por testes automatizados; NÃO validado ao vivo com job real** (ver "Smoke manual" abaixo). A revisão final do branch (opus) veio: **0 Critical, "pronto com correções"** → falta UMA onda de 9 correções pequenas.

**O que existe** (`src/buscador/`): `core/jobs_registro.py` (registro JSON em `jobs/registro.json`, escrita atômica, trava entre processos `trava_registro`), `core/jobs_motor.py` (iniciar destacado / executar / reconciliar / parar seguro / progresso / retomar), `core/jobs_executor.py` (processo executor destacado: roda o comando de verdade e grava o resultado), `core/jobs_notificacoes.py` (balão do Windows, import tolerante de `win11toast`), `jobs_cli.py` (`iniciar`/`status`/`parar`/`retomar`), `jobs.bat`, ganchos de 1 import + 2 linhas em `cli.py` e `gallica_crawl.py` (balão quando pegam `AcaoHumanaNecessaria`), `tests/conftest.py` (silencia o balão real em todos os testes). Uso (Git Bash, raiz do projeto — o Git Bash preserva as aspas internas): `.venv/Scripts/python.exe -m buscador.jobs_cli iniciar gallica_crawl 'dc.type all "monographie"'` · `... status` · `... parar <id>` · `... retomar <id>`. `--registro <arquivo>` (opção do parser principal, vem ANTES do subcomando) é só pra testes.

**Como retomar o trabalho (leia nesta ordem):**
1. Ledger local (gitignored, sobrevive ao `/clear`): `.superpowers/sdd/2026-09-17-motor-de-jobs/progress.md` — tabela de preflight, **21 `Ruling:`** (decisões que tomei em nome do Samuel, cada uma com "custo se errado"), achados de cada task, todos os minors deferidos, veredito da revisão final e os próximos passos. Se a pasta sumir (`git clean -fdx`), recupere de `git log` + esta seção.
2. Brief da onda de correção, pronto pra um implementador: `.superpowers/sdd/2026-09-17-motor-de-jobs/final-fix-wave.md`. Os 9 itens: (1) `jobs_registro.py` laço ocupado infinito quando a trava é velha e o `unlink` falha (provado) + docstring errado sobre aninhar; (2) `pid_esta_vivo`: bytes+`errors="replace"`, timeout, `CREATE_NO_WINDOW`, "na dúvida está vivo" (falha do `tasklist` hoje vira "morto" → `retomar` lançaria 2º executor no mesmo checkpoint); (3) `status` mostrar última linha do log + caminho do log para `erro`/`interrompido`/`parado`; (4) `carregar_registro` levantar `ValueError` nomeando o arquivo + `status` capturar; (5) `jobs_executor` gravar traceback no log e marcar `erro` se o executor levantar; (6) `warnings.warn` quando o fallback sem BREAKAWAY for usado; (7) `jobs.bat` linha do pip: `-e "%~dp0."`; (8) retry de `PermissionError` no `os.replace` de `core/checkpoint.py::salvar` e `core/enriquecimento_lote.py::salvar_checkpoint` (risco leitor-vs-escritor do checkpoint); (9) isolar `PASTA_JOBS` em `test_retomar_job_recusa_se_ja_existe_job_identico_rodando`.
3. Próximos passos: **(a)** despachar UM implementador (sonnet) com o brief; **(b)** UM re-review escopado (FIX_BASE `f799a06`); **(c)** smoke manual; **(d)** na mensagem final ao Samuel, listar TODAS as linhas `Ruling:` do ledger ("Rulings I made") e só então apagar a pasta do ledger; **(e)** `superpowers:finishing-a-development-branch` — **não dar merge/PR sem o Samuel escolher**.

**Smoke manual obrigatório (o revisor final NÃO conseguiu verificar isto):** (i) iniciar um job real curto e **fechar o terminal/sessão**: `.venv/Scripts/python.exe -m buscador.jobs_cli iniciar gallica_crawl 'gallica all "Clavius"' --max-resultados 100 --job teste-motor` → fechar tudo → num terminal NOVO `... status` deve mostrar o job vivo ou já `concluido` (é exatamente o bug de 17/09: a coleta SRU morreu junto com a sessão que a lançou); (ii) balão real de processo destacado sem console: `Start-Process -WindowStyle Hidden .venv\Scripts\python.exe -ArgumentList '-c','from buscador.core.jobs_notificacoes import avisar_windows; avisar_windows("BuscadorBaixador","teste de balao")'`; (iii) NUNCA testar `.bat` pelo Git Bash com `cmd /c` (ele converte `/c` em `C:/` e deixa um `cmd` preso esperando entrada — aconteceu; use PowerShell: `cmd /c "jobs.bat status < nul"`).

**Descobertas reais do Windows (caras de redescobrir):** `tasklist` devolve rc 0 tanto pra PID existente quanto inexistente e lista o PID 0 ("System Idle Process") como vivo; o Python do `.venv` é um launcher que cria 2 processos (launcher + interpretador real) → matar com `taskkill /T`; `Get-CimInstance` com erro sai com rc 0 + stdout vazio + erro no STDERR (indistinguível de "processo não existe" sem olhar o stderr); saída do PowerShell/`tasklist` vem em cp850 e decodificar como cp1252 quebra com bytes 0x81/0x8D/0x8F/0x90/0x9D; `CREATE_BREAKAWAY_FROM_JOB` dá `PermissionError` (WinError 5) se o pai está num job object sem breakaway (aqui é aceito); `os.open(O_EXCL)` e `os.replace` dão `PermissionError` transitório sob disputa entre processos; enquanto um leitor tem um arquivo aberto o `os.replace` do escritor falha (Python abre sem FILE_SHARE_DELETE); stdout de filho redirecionado pra arquivo fica em buffer de bloco (usar `PYTHONUNBUFFERED=1`); o Windows reaproveita PIDs (matar por PID cego mata programa alheio → só mata se a linha de comando tiver `jobs_executor` + o id do job).

**Caminhos descartados (e por quê):** processo supervisor único e fila de arquivos (ponto único de falha / peça a mais); `psutil` (dependência à toa; `tasklist`/PowerShell nativos bastam); `git worktree` (o `pip install -e` aponta pro checkout principal); `logar` como job (é interativo, espera Enter); subcomando `_executar` no `jobs_cli` (o executor é módulo próprio pra `iniciar_job` funcionar ponta a ponta antes do Task 8); monkeypatch em memória como forma de o teste dizer qual módulo rodar (o executor é outro processo — por isso o campo `alvo` no registro); `taskkill` cego por PID; API paga do Claude e Claude Agent SDK via Max pra classificação (sessão 2).

**Fora deste plano (follow-ups, em ordem):** **novo estado "esperando você"** (hoje `AcaoHumanaNecessaria` termina o job como `erro`; o spec trata "bloqueado por ação humana" como estado de vida do job — lacuna do PLANO, primeiro item do próximo plano); executor gravar o próprio PID ao subir; passe único de acentuação/polimento do `status` (limite/filtro, truncar linha de log, mensagens do `parar`, `choices=sorted(MODULOS_PERMITIDOS)`); testar o `REMAINDER` no Python 3.11 ou apertar `requires-python` para `>=3.12`; identidade do `retomar` pela chave do checkpoint; um único `tasklist` por `status`; dividir `jobs_motor.py` (464 linhas) quando o plano de estágios chegar; depois o plano de estágios + categorização por IA (spec de 17/09, sessão 2).

**Perguntas em aberto pro Samuel (exatas) — ATUALIZADO na sessão 5: itens 1-3 continuam sem resposta; item 4 RESOLVIDO (ver checkpoint 20/09 no topo):**
1. Gallica (planilha `saidas/gallica_livros_padrao.xlsx`, 46.222 itens, mapeamento por curadoria — **não confundir com a coleta SRU, que é outra coleção**, ver checkpoint 20/09): "os 9.086 itens em 'Outros' (jornais/periódicos e artistas visuais) — deixar assim ou criar balde(s) novo(s)? E a tradução offline fr→en→pt (qualidade inferior ao Google, alguns títulos ficaram em inglês) — aceitar ou refinar quando a cota do MyMemory resetar?" Os 2 scripts (`scripts/categorizar_amostra_gallica.py` modificado, `scripts/traduzir_titulos_lote_gallica.py` novo) seguem **sem commit**, esperando revisão dele.
2. Pesquisa dos livros do projeto Livro Profecias TIA (relatório completo: `.superpowers/sdd/pesquisa_livros_profecias_TIA.md`; achados: Corteville-Laurentin só compra, cap. 4 pp. 83-92 da edição inglesa; Sánchez com copyright, o TIA cita a tradução inglesa de 1968 então a paginação da edição espanhola não bate; **Machado (Holzhauser) só achei em inglês**, não em português; Montfort é domínio público mas as traduções PT têm copyright; Bíblia recomendada: Matos Soares): "Quer que eu salve esse relatório dentro da pasta do projeto Livro Profecias TIA?" — ficou sem resposta.
3. Os 3 `.bat` irmãos (`gallica_crawl.bat`, `gallica_enriquecer.bat`, `mapear.bat`) têm o MESMO defeito do pip que o `jobs.bat` tinha (já corrigido na sessão 5, item 7 da onda) — `-e "%~dp0"` → erro a cada execução; corrigir é 1 caractere: `-e "%~dp0."`: "Posso corrigir os 3 num commit à parte?"
4. ~~A coleta SRU da Gallica está PARADA~~ — **RESOLVIDO na sessão 5**: relançada pelo motor, terminou com 934.581 registros. Falta a Etapa 2 (`gallica_enriquecer`) rodar sobre esse resultado bruto.

**Ambiente:** venv `.venv` Python 3.12.10; instalado nesta sessão: `win11toast` 0.36.3 (via `pip install -e ".[dev]"`, já em `pyproject.toml`). Hardware (Ryzen 7 5800H, 16 GB, GTX 1650 4 GB) e demais decisões da sessão 2 (sem API paga, Ollama local + handoff manual pro Claude Code, cascata de 3 camadas) seguem valendo. Não commitar: `Claude outputs/*.pdf` (soltos, são do projeto Livro Profecias TIA).

**Custo do método:** ~33 agents gastam bastante do limite semanal do Max; se o Samuel pedir, usar um modo mais enxuto (menos revisores) no resto.

## Checkpoint 17/09/2026 (sessão 3) — plano de implementação do motor de jobs pronto, leia aqui primeiro

Continuação da sessão 2 (ver logo abaixo pro desenho completo, que não
mudou). Nesta sessão, a spec virou **plano de implementação** completo,
via skill `superpowers:writing-plans`.

**Plano escrito, autorrevisado e commitado:**
`docs/superpowers/plans/2026-09-17-motor-de-jobs.md` — 10 tasks em estilo
TDD (teste falha → implementa → teste passa → commit), cobrindo **só o
motor central** (registro de jobs, iniciar/status/parar/retomar,
notificação nativa do Windows quando um job trava esperando login/
CAPTCHA) — reaproveitando os comandos que já existem hoje (`cli`,
`gallica_crawl`, `gallica_enriquecer`, `logar`) como jobs isolados.

**Decisão de escopo tomada nesta sessão, registrada no próprio plano:** o
plano deliberadamente NÃO cobre o resto do spec (estágios configuráveis
por job, fluxo de categorização por IA em 3 níveis) — isso fica pra um
segundo plano, construído em cima do motor central depois dele existir e
estar testado com jobs de verdade. Motivo: são peças de escopo próprio
(a peça de estágios depende de refatorar `cli.py`), e o motor sozinho já
resolve o pedido original (rodar mais de uma tarefa ao mesmo tempo, ver
progresso, parar/retomar, ser avisado quando travar).

**Autorrevisão do plano encontrou e já corrigiu um bug real antes de
qualquer código ser escrito:** o comando `iniciar` do `jobs_cli.py` usava
`nargs="*"` pro argv repassado ao comando de verdade — isso quebraria com
qualquer flag tipo `--adapter phpbb` (o argparse tentaria interpretar
`--adapter` como opção do próprio `jobs_cli`, que não existe, e falharia).
Corrigido pra `nargs=argparse.REMAINDER` no próprio arquivo do plano.

**Decisões técnicas principais do plano** (arquitetura já estava fechada
na spec; aqui são decisões de implementação):
- Cada job é lançado por um pequeno processo "executor"
  (`python -m buscador.jobs_cli _executar <id>`) que roda o comando de
  verdade e atualiza o registro sozinho quando termina — nenhum processo
  supervisor permanente.
- `tasklist`/`taskkill` nativos do Windows pra checar se um processo
  ainda está vivo e pra matar (com `/T` pra matar a árvore inteira) — sem
  adicionar `psutil`.
- Nova dependência: `win11toast` (notificação nativa, sem precisar de
  admin).
- Status lê os checkpoints que já existem (`core/checkpoint.py` pro
  `gallica_crawl`, `core/enriquecimento_lote.py` pro `gallica_enriquecer`)
  em vez de duplicar o mecanismo de progresso.

**Pergunta em aberto (17/09/2026) — retomar exatamente aqui:** perguntei
ao Samuel se prefere execução **Subagent-Driven** (um subagente novo por
task, com revisão entre cada uma) ou **Inline** (executar as tasks nesta
mesma sessão, em lote, com checkpoints de revisão) — ficou sem resposta
porque ele pediu `/checkpoint` antes de escolher. Não decidir sozinho —
perguntar nessa mesma bifurcação antes de começar a implementar qualquer
task.

**Os dois jobs da Gallica que estavam rodando em paralelo (ver sessão 2)
— atualização:**
- **Categorização + tradução do mapeamento por curadoria (46.222 itens):
  TERMINOU DE VERDADE nesta sessão.** Planilha final gerada em
  `saidas/gallica_livros_padrao.xlsx` (2,1MB, Índice + 9 abas). Achado
  real confirmado ao vivo: Google Translate e MyMemory falharam 100% nas
  46 mil chamadas (rate limit/cota esgotada) — a solução usou a tradução
  offline (`argostranslate`, fr→en→pt) já existente no projeto. **Duas
  decisões que ficaram pro Samuel, não decididas sozinhas pelo agente:**
  (1) os 9.086 itens em "Outros" (majoritariamente jornais/periódicos e
  artistas visuais) — não força um 9º balde inventado; (2) qualidade da
  tradução offline é inferior ao Google (alguns títulos pararam em inglês
  em vez de chegar em português) — resolver isso exigiria esperar a cota
  do MyMemory resetar ou pagar API, nenhuma das duas decidida ainda.
  **Nada commitado ainda** — `scripts/categorizar_amostra_gallica.py`
  (modificado) e `scripts/traduzir_titulos_lote_gallica.py` (novo)
  continuam no working tree esperando revisão do Samuel.
- **Coleta SRU da Gallica** (`gallica_crawl`): continua rodando, agora em
  **492.950 / 934.427 registros (~52,8%)**, atualizado às 23:34:53 UTC de
  17/09. Ainda não concluída no momento deste checkpoint — uma sessão
  futura deve checar `saidas/gallica_crawl/dc-type-all-monographie-4d1e657b14/checkpoint.json`
  de novo, e se ainda não terminou, rodar o mesmo comando de novo (retoma
  sozinho).

**Testes:** `pytest` rodado nesta sessão, **143 passando** (nada novo
implementado ainda — o plano só foi escrito, não executado).

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
