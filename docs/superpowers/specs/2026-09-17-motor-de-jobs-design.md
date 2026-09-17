# Motor de Jobs — Desenho

Data: 2026-09-17
Status: aprovado por Samuel, pronto para virar plano de implementação.

## Contexto e objetivo

Hoje cada comando do BuscadorBaixador (`cli.py`, `gallica_crawl.py`,
`gallica_enriquecer.py`, `logar.py`, scripts em `scripts/`) é um script
isolado, invocado na mão em terminais separados. Samuel quer rodar mais de
uma tarefa ao mesmo tempo, acompanhar o progresso de cada uma, e poder
parar/retomar/adicionar trabalho sem reabrir terminal toda vez.

A motivação de fundo é maior que "rodar dois comandos ao mesmo tempo": é o
primeiro passo de uma peça permanente do programa — um **motor de jobs** —
pensando já em um uso futuro onde o Kaique (usuário leigo) também consiga
disparar/acompanhar tarefas, sem terminal. Esse uso pelo Kaique exige uma
interface (dashboard) que **não é** o escopo deste desenho — ver seção
"Fora de escopo".

## Escopo desta fase

**Dentro:** o motor de jobs em si — backend controlável por Samuel via
terminal. Reaproveita ao máximo o que já existe (checkpoints,
`AcaoHumanaNecessaria`, os comandos atuais como scripts a serem invocados).

**Fora (fica para depois, cada um como seu próprio projeto/design):**
- Dashboard/interface para o Kaique usar sem terminal — o motor desenhado
  aqui é a peça que esse dashboard futuro vai chamar por baixo.
- Fase 4 do roadmap (catalogar via OCR) e Fase 5 (organizar por
  categoria/tema/autor + integração com o outro app de biblioteca que
  Samuel está construindo) — ver nota na seção de categorização sobre como
  o desenho de hoje já acomoda isso sem precisar mudar de forma.
- Download de fato (Fase 2) — o estágio "Baixar" é referenciado no modelo
  de estágios abaixo, mas sua implementação real é trabalho futuro.

## Abordagem arquitetural

Avaliadas três abordagens (subprocessos + registro; processo supervisor
único; fila baseada em arquivos). Escolhida: **subprocessos + registro em
JSON**.

- Cada job roda como um processo isolado do Windows (do mesmo jeito que já
  acontece hoje quando Samuel roda um comando na mão) — um job travar ou
  crashar nunca derruba os outros nem o motor.
- Não existe processo permanente que precise ficar de pé o tempo todo —
  descartado por ser um ponto único de falha (se cair, derruba jobs de
  horas em andamento) e por exigir infraestrutura extra (serviço do
  Windows, etc.) sem necessidade real no tamanho atual do projeto (4 tipos
  de job, 1-2 pessoas disparando).
- Um registro em JSON (`jobs/registro.json`), com escrita atômica no mesmo
  padrão de `core/checkpoint.py` (arquivo `.tmp` + `os.replace`), guarda
  por job: PID, comando, estágios ativos, horário de início, estado atual.
- O progresso de cada job é lido diretamente dos checkpoints que os jobs já
  produzem hoje (`core/checkpoint.py`, `core/enriquecimento_lote.py`) — o
  motor não duplica esse mecanismo, só o consulta.

## Modelo de job e estágios

Um job = um alvo (site/consulta) + uma lista de estágios ativados.

**Estágios definidos:**
1. **Mapear** — obrigatório, sempre primeiro. Descobre os itens e captura
   o **máximo de metadado disponível** na fonte (não só título+link —
   autor, ano, idioma, domínio público, etc., quando a fonte oferecer).
2. **Verificar links** — opcional, independente de Traduzir.
3. **Traduzir** — opcional, independente de Verificar links.
4. **Baixar** — opcional, depende de Verificar links já ter rodado
   (não baixar link quebrado). Implementação real é trabalho futuro
   (Fase 2).

Estágios podem ser ligados/desligados por job, **inclusive depois que
outros estágios já rodaram** — exemplo do próprio Samuel: mapear sem
traduzir primeiro (mais rápido), decidir depois se quer adicionar
Traduzir e/ou Baixar sobre o que já foi mapeado, sem repetir o mapeamento.

## Ciclo de vida do job e pausas

Além de rodando/parado/concluído/com erro, um job pode entrar em estados de
**pausa esperando ação de Samuel**, generalizando o que `AcaoHumanaNecessaria`
já faz hoje para login/CAPTCHA/chave de API:

- **Bloqueado por ação humana** (login, CAPTCHA, chave de API) — já existe
  hoje via `AcaoHumanaNecessaria`; o motor passa a notificar ativamente em
  vez de só logar.
- **Aguardando decisão de categoria** — ver fluxo completo abaixo.
- **Aguardando classificação manual** — job exportou um arquivo e espera
  Samuel trazer o resultado de volta (ver "Backends de IA").

Em qualquer pausa, o motor dispara uma **notificação nativa do Windows**
(toast) no momento em que o job entra nesse estado — sem precisar Samuel
ficar olhando terminal.

## Categorização no estágio Mapear

Ordem de tentativa, do mais barato/confiável para o mais caro:

1. **Categoria/subcategoria formal da própria API/metadado do site.** Só
   conta como confiável se vier de um campo estruturado da fonte (API/
   metadado formal) — nunca algo extraído de navegação/HTML. Se existir,
   usa direto, sem acionar mais nada. (Hoje nenhum adapter lê isso ainda,
   mas o Internet Archive já oferece isso na própria API — é o caso mais
   simples de resolver quando chegar a hora.)
2. **Se não tiver, tenta a trilha de navegação** (`secao` — breadcrumb já
   coletado hoje por `PhpbbAdapter` e pelo mapeamento por curadoria da
   Gallica) e **sugere para Samuel aprovar**, mostrando as trilhas mais
   comuns e quantos itens em cada. Se aprovada, classifica direto os itens
   que já carregam essa trilha. (Sabemos, pelo caso real da Gallica, que
   essa trilha pode estar contaminada — cabe a Samuel julgar, não o motor
   decidir sozinho.)
3. **Se nenhuma das duas resolver, entra a IA**, em duas frentes:
   - **(a) Descobrir a lista de categorias:** a IA propõe candidatos a
     partir de uma amostra do conteúdo. Samuel aprova em **rodadas por
     exclusão** — aprova o que serve, rejeita o que não serve, pede
     alternativas só para as vagas que sobraram; cada rodada nova não
     repete o que já foi aprovado nem o que já foi rejeitado. Repete até
     Samuel fechar a lista.
   - **(b) Classificar cada item** dentro da lista já aprovada, usando os
     metadados disponíveis (título, autor, ano, idioma — não o conteúdo
     completo da obra), para gastar o mínimo possível.

### Nota sobre Fase 4/5 (OCR e catalogação)

O passo 3(b) acima foi desenhado para não precisar mudar de forma quando o
OCR (Fase 4 do roadmap) existir: hoje a IA classifica com os metadados
disponíveis; quando houver OCR, o mesmo passo passa a receber também o
texto extraído do livro baixado, como entrada adicional — mesma peça do
desenho, entrada mais rica. A ideia de Samuel de organizar por
categoria/tema/autor com ajuda do OCR, e integrar com seu outro app de
biblioteca (Fase 5), fica registrada como visão futura, a ser desenhada
quando a Fase 4 realmente começar.

## Backends de IA — sem API paga em lugar nenhum

Tanto a descoberta de categorias (3a) quanto a classificação por item (3b)
usam um destes dois caminhos, escolhido por Samuel conforme a necessidade —
**nunca a API paga da Anthropic**:

1. **Modelo local (Ollama)** — automático, sem precisar de Samuel presente,
   gratuito. Estimativa (a confirmar com teste real numa amostra de
   200-300 itens): um modelo pequeno (~3B parâmetros, ex. Llama 3.2 3B ou
   Qwen2.5 3B) cabe folgado na GPU de Samuel (GTX 1650, 4GB) e classificaria
   os 46.222 itens da Gallica em algo como 3-5 horas rodando em lotes,
   como job de segundo plano.
2. **Handoff manual via Claude Code** — o job exporta um arquivo (itens +
   lista de categorias aprovada) e entra em pausa "aguardando classificação
   manual". Samuel leva esse arquivo a uma sessão de Claude Code, pede a
   classificação, recebe um arquivo de volta, e roda um comando do motor
   (`jobs importar-classificacao <job> <arquivo>`) para aplicar o resultado
   e retomar o job. Gratuito (dentro da assinatura Max de Samuel), mais
   rápido que o modelo local quando Samuel está disponível para fazer a
   troca — mas não é "liga e esquece": precisa de atenção de Samuel na hora
   da troca de arquivo.

Motivo de excluir a API paga: Samuel não tem orçamento disponível para
isso agora, e usar a assinatura Max via automação não supervisionada (ex.:
Claude Agent SDK chamado sozinho pelo script) é tecnicamente possível mas
de uso incerto dentro dos termos do plano — o handoff manual evita esse
risco por ser sempre uma sessão real, iniciada por Samuel.

## Verificação

Sem código escrito ainda neste desenho — a verificação real acontece no
plano de implementação. Pontos que o plano de implementação deve garantir
testáveis:
- Registro de jobs sobrevive a reinício do motor (não perde jobs em
  andamento se Samuel fechar e reabrir o terminal).
- Status lido do checkpoint bate com o progresso real de um job de
  verdade rodando (ex.: `gallica_crawl` já em andamento).
- Parar um job mata o processo sem corromper o checkpoint (retomar depois
  continua de onde parou).
- Notificação dispara no momento exato em que um job entra em pausa
  (login, categoria, classificação manual) — não só quando alguém consulta
  status manualmente.
