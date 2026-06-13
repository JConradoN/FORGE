#!/bin/bash
# FORGE — Batch por cenário (funil eliminatório)
# Uso: bash run_scenario_batch.sh --scenario F1 [--log /tmp/forge_f1.log]
set -euo pipefail

FORGE_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$FORGE_DIR"

# ── Defaults ────────────────────────────────────────────────────────────────
SCENARIO=""
LOG=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --scenario) SCENARIO="$2"; shift 2 ;;
    --log)      LOG="$2";      shift 2 ;;
    *) echo "Uso: $0 --scenario <ID> [--log <arquivo>]"; exit 1 ;;
  esac
done

[[ -z "$SCENARIO" ]] && { echo "ERRO: --scenario obrigatório"; exit 1; }

LOG="${LOG:-/tmp/forge_${SCENARIO,,}_batch.log}"

# ── Modelos (ordem crescente de VRAM) ───────────────────────────────────────
# F1: todos os 20 modelos disponíveis — funil eliminatório
# F2+: editar esta lista com os aprovados em F1
MODELS=(
  "granite4.1:3b"
  "rnj-1:8b"
  "lfm2.5:8b"
  "qwen3:8b"
  "granite4.1:8b"
  "ministral-3:8b"
  "qwen3.5:9b"
  "qwen3.5:9b-48k"
  "gemma4:12b"
  "phi4:14b"
  "ministral-3:14b"
  "phi4-tools:14b"
  "qwen3:14b"
  "gemma4:e4b-it-q4_K_M"
  "lfm2:24b-a2b"
  "devstral-small-2:24b"
  "qwen3.5:27b"
  "qwen3.6:27b"
  "gemma4:26b"
  "granite4.1:30b"
)
# claude-sonnet-4-6 roda separado via forge_claude_runner.py (API, sem Ollama)

# ── Funções ──────────────────────────────────────────────────────────────────
log() { echo "$@" | tee -a "$LOG"; }

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

# ── Início ───────────────────────────────────────────────────────────────────
> "$LOG"  # limpa log anterior
log "================================================================"
log "  FORGE ${SCENARIO} — Batch"
log "  $(date '+%Y-%m-%d %H:%M:%S')"
log "  Ollama: $(docker exec ollama ollama --version 2>/dev/null | awk '{print $NF}')"
log "  Modelos: ${#MODELS[@]}"
log "================================================================"

unload_all
vram_status

PASSED=0
FAILED=0

for model in "${MODELS[@]}"; do
  log ""
  log "----------------------------------------------------------------"
  log "  >>> $model  $(date '+%H:%M:%S')"
  log "----------------------------------------------------------------"

  if python3 -u scripts/forge_runner.py "$model" --scenario "$SCENARIO" 2>&1 | tee -a "$LOG"; then
    log "  [OK] $model concluído"
    PASSED=$((PASSED + 1))
  else
    log "  [ERRO] $model falhou com exit $? — pulando"
    FAILED=$((FAILED + 1))
  fi

  unload_all
  vram_status
  sleep 3
done

log ""
log "================================================================"
log "  Pipeline ${SCENARIO} concluído — $(date '+%Y-%m-%d %H:%M:%S')"
log "  OK: $PASSED | ERRO: $FAILED"
log "================================================================"
log ""

# ── Resumo de resultados ─────────────────────────────────────────────────────
log "Resultados ${SCENARIO}:"
for model in "${MODELS[@]}"; do
  slug=$(echo "$model" | tr ':' '-' | tr '/' '_')
  result=$(ls "results/${SCENARIO}/${slug}/"*.json 2>/dev/null | grep -v workdir | tail -1)
  if [[ -n "$result" ]]; then
    score=$(python3 -c "
import json
d = json.load(open('$result'))
auto   = f\"{d.get('auto_score','?')}/{d.get('auto_max','?')} ({d.get('auto_pct','?')}%)\"
stop   = d.get('stop_reason','?')
turns  = d.get('turns','?')
print(f'  auto={auto}  turns={turns}  stop={stop}')
" 2>/dev/null || echo "  erro ao ler resultado")
    log "  $model: $score"
  else
    log "  $model: sem resultado"
  fi
done
