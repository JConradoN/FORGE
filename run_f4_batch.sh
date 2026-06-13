#!/bin/bash
# FORGE F4 — Batch gerado pelo pipeline orchestrator
set -euo pipefail

FORGE_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$FORGE_DIR"

MODELS=(
  "qwen3:8b"
  "qwen3.5:9b"
  "gemma4:12b"
  "phi4-tools:14b"
  "qwen3:14b"
  "gemma4:e4b-it-q4_K_M"
  "lfm2:24b-a2b"
  "devstral-small-2:24b"
  "qwen3.5:27b"
  "qwen3.6:27b"
  "gemma4:26b"
)

log() { echo "$@"; }

unload_all() {
  log "[batch] descarregando modelos da VRAM..."
  curl -s http://localhost:11434/api/ps | python3 -c "
import sys, json
models = json.load(sys.stdin).get('models', [])
for m in models:
    print(m['name'])
" | while read -r name; do
    curl -s -X POST http://localhost:11434/api/generate \
      -d "{\"model\":\"$name\",\"keep_alive\":0}" > /dev/null
    log "  descarregado: $name"
  done
}

vram_status() {
  local used
  used=$(curl -s http://localhost:11434/api/ps | python3 -c "
import sys, json
models = json.load(sys.stdin).get('models', [])
total = sum(m.get('size_vram', 0) for m in models)
print(total // 1024 // 1024)
")
  log "[vram] uso atual: ${used} MB"
}

log "================================================================"
log "  FORGE F4 — Batch"
log "  $(date '+%Y-%m-%d %H:%M:%S')"
log "  Ollama: $(docker exec ollama ollama --version 2>/dev/null | awk '{print $NF}')"
log "  Modelos: ${#MODELS[@]}"
log "================================================================"

unload_all
vram_status

PASSED=0; FAILED=0

for model in "${MODELS[@]}"; do
  log ""
  log "----------------------------------------------------------------"
  log "  >>> $model  $(date '+%H:%M:%S')"
  log "----------------------------------------------------------------"

  if python3 -u scripts/forge_runner.py "$model" --scenario "F4"; then
    log "  [OK] $model concluído"
    PASSED=$((PASSED + 1))
  else
    log "  [ERRO] $model falhou com exit $?"
    FAILED=$((FAILED + 1))
  fi

  unload_all
  vram_status
  sleep 3
done

log ""
log "================================================================"
log "  Pipeline F4 concluído — $(date '+%Y-%m-%d %H:%M:%S')"
log "  OK: $PASSED | ERRO: $FAILED"
log "================================================================"
