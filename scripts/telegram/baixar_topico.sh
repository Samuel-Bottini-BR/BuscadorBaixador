#!/usr/bin/env bash
# Baixa todos os arquivos de um export do tdl, em rodadas, até completar.
# Uso: baixar_topico.sh <export.json> <pasta_destino> <log_rodadas>
# Pula só figurinhas. Repetidos são baixados e comparados depois (por hash).
EXPORT="$1"; DEST="$2"; LOG="$3"
PY=/d/programas/BuscadorBaixador/.venv/Scripts/python.exe
TDL=/d/programas/ferramentas/tdl/tdl.exe
LISTA="${EXPORT%.json}_faltando.json"
mkdir -p "$DEST"

conta() { ls "$DEST" | grep -vc '\.tmp$'; }

for rodada in $(seq 1 20); do
  rm -f "$DEST"/*.tmp
  falta=$(EXPORT="$EXPORT" DEST="$DEST" LISTA="$LISTA" "$PY" - <<'EOF'
import json, os
exp, dest, lista = os.environ["EXPORT"], os.environ["DEST"], os.environ["LISTA"]
d = json.load(open(exp, encoding="utf-8"))
have = {int(n.split("_", 1)[0]) for n in os.listdir(dest) if not n.endswith(".tmp")}
falt = []
for m in sorted(d["messages"], key=lambda m: m["id"]):
    doc = (m["raw"].get("Media") or {}).get("Document") or {}
    if doc.get("MimeType") in ("image/webp", "application/x-tgsticker"):
        continue
    if m["id"] not in have:
        falt.append({k: v for k, v in m.items() if k != "raw"})
json.dump({"id": d["id"], "messages": falt}, open(lista, "w", encoding="utf-8"), ensure_ascii=False)
print(len(falt))
EOF
)
  antes=$(conta)
  echo "$(date +%H:%M) rodada $rodada: baixados=$antes faltando=$falta" >> "$LOG"
  [ "$falta" = "0" ] && { echo "COMPLETO" >> "$LOG"; exit 0; }
  "$TDL" dl -f "$(cygpath -m "$LISTA")" -d "$(cygpath -m "$DEST")" \
    --template "{{ .MessageID }}_{{ filenamify .FileName }}" \
    --skip-same --restart --disable-progress-ps -l 4 > "${LOG%.log}_rodada$rodada.log" 2>&1
  cod=$?
  depois=$(conta)
  echo "$(date +%H:%M) rodada $rodada terminou (codigo $cod), +$((depois - antes)) arquivos" >> "$LOG"
  if [ "$depois" -le "$antes" ]; then
    echo "SEM PROGRESSO - parando" >> "$LOG"; exit 1
  fi
done
echo "LIMITE DE RODADAS" >> "$LOG"
exit 1
