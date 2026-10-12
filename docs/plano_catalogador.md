# Plano do Catalogador (Fase 4) — discutido em 09–12/10/2026 (sessão 9, nuvem)

**Estado: em discussão. Nenhuma linha de código do catalogador foi escrita.**
Pergunta pendente para o Samuel: **começar pelas fatias 1 (motor) + 3 (mesa de conferência) juntas?**
(recomendação: sim — sem a mesa não dá para ver/corrigir o que o motor leu; listas logo depois).

## Para que serve
O Samuel põe uma **pasta de livros baixados** (ex.: `saidas\telegram\topico_81988\arquivos`) e o
app ajuda a catalogar: lê cada arquivo, sugere título/autor/ano/tema (**palpite**), o humano confere
e confirma; depois (fatia futura) o app renomeia, grava metadados no PDF e move para a pasta certa,
com registro para desfazer.

## Decisões do Samuel
- **Leitura em degraus**: identificar (sha256; já no catálogo → "Já no acervo/Duplicado") →
  metadado embutido (com o **filtro de lixo do RenomeadorLivros**: Microsoft Word, CamScanner,
  untitled, título = nome do arquivo…) → texto do PDF → **OCR Tesseract** (pág. 1–6; depois
  últimas/15%/50%) → (futuro) IA local → **Claude por lote** para o que ficar fraco (sem chave de API,
  usa o Claude Pro, como na conferência/Renomeador).
- **Texto → ficha = regras + Claude.** As regras simples erram muito; melhorar com **várias pistas**,
  cada uma com evidência (trecho + página):
  1. nome do arquivo (nos downloads muitas vezes já é bom);
  2. layout da folha de rosto (Tesseract `image_to_data`: maior letra na metade de cima = título;
     "por/by/par/auctore" → autor; cidade/editora/ano embaixo);
  3. autores já confirmados (lista de autoridade com variantes);
  4. itens de listas subidas;
  5. metadado embutido filtrado.
  **Confiança = concordância entre pistas.** Regra: **não inventar** (sem evidência → vazio).
- **Gabarito**: 50–100 livros já marcados **Certo** (conferência / Renomeador) com as respostas
  verdadeiras; a cada mudança nas regras o programa mede o % de acerto (título/autor/ano).
- **Listas**: subir **planilhas .xlsx/.csv** (escolher colunas Título/Autor/Ano/Tema) e as
  **listas do próprio app** (Telegram/Mapear).
  - Lista dá **tema** aos livros que casam; tema escolhido **por lote** e **1 a 1**.
  - Exportar lista (título+autor) → Claude sugere tema CDU → importar de volta como sugestão.
  - Item de lista sem livro = **Não adquirido** (Mapa da Ignorância); vira **adquirido sozinho**
    quando o livro é baixado/catalogado (se o casamento for incerto, **pergunta**).
- **Tema**: **CDU** (lista inicial `dados/temas_cdu.csv`, a conferir). Sugestões: listas,
  **mesmo autor já catalogado**, **Library of Congress** (no teste da conferência acertou 54/200 e
  trouxe 26 registros errados — só sugestão).
- **Autor**: forma autorizada **SOBRENOME, Nome** (ex.: `AQUINO, Tomás de`), com variantes.
- **Pastas físicas**: `Tema(CDU) \ AUTOR \`. No app: ver por **tema** e por **etapa**.
- **Nome do arquivo**: `AUTOR - Título (Ano) - SB-0001.pdf`.
- **Código SB-xxxx**: só ao **confirmar** a ficha (humano).
- **Identidade** do livro = **sha256 original** (gravar metadado no PDF muda o hash).
- **Esteira**: Não adquirido → A restaurar → Restaurando → Restaurado → Pronto p/ impressão → Impresso.
- **IA local** (em vista, fatia futura, testar no PC — muda a regra "sem IA local" do CLAUDE.md):
  Florence-2 / SmolVLM (lê imagem, 0,2–0,5 GB) e Qwen/Llama ~1B via Ollama (entende o texto).

## Mesa de conferência (como o `D:\programas\biblioteca digital conferencia\Conferencia.html`)
- Prova à esquerda (imagem da página, ◀ ▶ / trecho lido); ficha à direita (título, autor com
  sugestões, editora, ano, idioma, tipo, tema CDU, etapa), pistas/evidências, nome e pasta propostos.
- **Certo / Errado / Dúvida** (teclas C/E/D; corrigir antes de "Errado" grava a correção),
  comentário automático, **prints** colados (Ctrl+V) com comentário, **Abrir arquivo** (A), copiar caminho.
- Filtros: sem marcar, todos, vermelhos, errados, dúvidas, com comentário, pasta, **tema**, **etapa**,
  lista; barra de progresso; **tema por lote**.
- Diferença para o HTML antigo: tudo gravado **no catálogo (HD)**, não no navegador — nada se perde
  e Samuel/Kaique veem o mesmo. **Certo** → gera SB.

## Fatias
1. **Motor**: `core/catalogo_db.py` (SQLite `dados/catalogo.db`), `catalogo_leitura.py`,
   `catalogo_palpite.py`, `catalogo_gabarito.py`, `catalogo_nomes.py`; processar pasta em segundo
   plano (padrão `core/mapear_segundo_plano.py`); botão **Preparar OCR** (winget Tesseract +
   `tessdata_fast` por/lat/spa/fra/ita/eng em `ferramentas/tessdata`). Deps: `pymupdf`, `pytesseract`.
2. **Listas**: `core/catalogo_listas.py`.
3. **Mesa de conferência**: `app/pagina_catalogar.py`.
4. Registro + **Aplicar/Desfazer** (renomear, metadados no PDF, mover Tema\Autor).
5. Importar leituras antigas como palpites. 6. IA local.

## O que já existe nos outros projetos (para reaproveitar)
Lido em 09/10/2026 (só leitura, pelo HD):
- `D:\programas\RenomeadorLivros` — 2.707 PDFs `Found_*`; regras "não inventar", filtro do
  metadado (Fase 1), `render.py` (páginas/DPI), `nomes.py` (limpeza de nome), `hashes.jsonl`.
  Fase 2 (200 livros): 94,5% identificados. **Fase 3 parada no meio** (lotes 0041–0079 prontos,
  0080–0087 em andamento sem validar, 0088–0190 pendentes) — o HANDOFF dele está desatualizado
  em relação ao `controle.json`.
- `D:\programas\biblioteca digital conferencia` — catálogo de 12.744 documentos de
  `D:\Livros para editar` (`rows_v3.json`; alta 10.247 / média 2.313 / baixa 184), OCR Tesseract
  (`ocr.py`), tema por Library of Congress (`build2.py`), `Conferencia.html` (2.497 itens a
  conferir, 22 marcados). Sem sha256.
- `D:\programas\Biblioteca Digital` — pesquisa: código **SB-0001** (etiqueta + nome do PDF + ficha),
  Calibre para o digital, BiblioteQ/Biblivre para o físico, Tainacan para o público, esteira de
  status; protótipos visuais. Nenhum app.
- `D:\programas\_claude-projeto-sao-bento\memory.md` — "a máquina classifica por sinais objetivos;
  o humano faz todo julgamento editorial"; nunca usar `000LH_Abrev.pdf` e `LDH-04.pdf`.
- **Os dois acervos (Renomeador × Livros para editar) nunca foram cruzados**; SB nunca foi atribuído.
