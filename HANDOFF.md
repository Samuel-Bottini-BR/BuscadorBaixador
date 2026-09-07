# Buscador e Baixador — estado atual

## O que é e para quem

Aplicativo local (Windows) para o Instituto São Bento achar, baixar e
catalogar obras digitalizadas (livros esgotados, artigos) espalhadas em
sites e fóruns. Usuários: Samuel e o Kaique (leigo, sem formação técnica —
interface precisa ser simples, em português). Regras completas do projeto,
arquitetura e protocolo de decisões estão em `CLAUDE.md` — leia lá primeiro.

## Estado atual

Fase 1 ("mapear um site → planilha") em andamento. Feito até agora:
- Pacote Python instalável (`pyproject.toml`, `src/buscador/`), `.venv` com
  Python 3.12 (instalado à parte do 3.14 global, por causa do `argostranslate`).
- Repositório git criado e publicado: https://github.com/Samuel-Bottini-BR/BuscadorBaixador
  (branch de trabalho: `feat/fase1-mapeador`).
- Decidido: dois adaptadores nesta fase — fórum Grand Sud Médiéval (phpBB,
  raspagem educada) e Deutsche Digitale Bibliothek/DDB (API oficial). zvdd.de
  foi descartado como caso de teste (ver seção 12 do CLAUDE.md) e fica só
  como adaptador futuro opcional, por lista de PPN manual.
- Ainda não escrita: nenhuma lógica dos adaptadores, tradução ou geração de
  planilha (isso é o restante da Fase 1).

## Decisões fechadas

- `requests` para raspagem educada (Grand Sud); `httpx` para a API (DDB).
- Tradução híbrida: `deep-translator` (online) com fallback pra
  `argostranslate` (offline).
- Empacotamento: pacote instalável de verdade (`pip install -e .`), não
  hack de `sys.path`.
- Chave da API da DDB: nunca no código — variável de ambiente `DDB_API_KEY`
  ou arquivo `buscador.local.cfg` (gitignored). Samuel ainda não se cadastrou.
- Ver seções 3 e 7 do CLAUDE.md para o protocolo de decisões e a árvore de
  acesso a sites (nunca burlar robots.txt/paywall/login).

## O que falta

Ver o plano técnico completo (sequenciamento em fatias) — se não estiver
mais disponível na sessão ativa, refazer o plan mode da Fase 1 descrito na
seção 4 do CLAUDE.md antes de continuar. Resumo do que falta:
1. Extrair a lógica de `verificar_links.py` para `core/verificacao_links.py`.
2. Adaptador do fórum Grand Sud (extração de posts, paginação).
3. Módulo de tradução híbrida.
4. Geração da planilha `.xlsx` (formato-alvo: ver
   `Garimpo_GSM_MESTRE_VERIFICADO.xlsx` em
   `C:\Users\fotog\Desktop\Projeto São Bento\SITE GRAND SUL MEDIEVAL\GARIMPO\`).
5. CLI ligando tudo, primeira planilha real gerada a partir do Grand Sud.
6. Adaptador da DDB (com fixture sintética; execução real pendente da API key).

## Como rodar

```
D:\programas\BuscadorBaixador\.venv\Scripts\python.exe -m pytest -q
```
(o `.venv` já está criado com Python 3.12 e o pacote instalado em modo
editável — `pip install -e ".[dev]"` se precisar reinstalar.)
