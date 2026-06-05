#!/usr/bin/env bash
# ===========================================================
# FORGE F5 — Overnight Batch
# Controle Sonnet + todos os modelos Ollama × 3 harnesses
#
# Harnesses:
#   1. FORGE direct (Ollama API direta)
#   2. opencode (CLI nativo, file tools)
#   3. OpenHands (Docker sandbox)
#
# Uso: bash scripts/run_f5_overnight.sh 2>&1 | tee logs/f5_overnight.log
# ===========================================================

set -uo pipefail
cd "$(dirname "$0")/.."

mkdir -p logs results
TIMESTAMP=$(date +%Y-%m-%d_%H-%M)
LOG_FILE="logs/f5_overnight_${TIMESTAMP}.log"
SUMMARY_FILE="logs/f5_summary_${TIMESTAMP}.md"

PYTHON_VENV="/home/conrado/.venv/bin/python3"
PYTHON_SYS="python3"

log() { echo "[$(date +%H:%M:%S)] $*" | tee -a "$LOG_FILE"; }

OLLAMA_MODELS=(
    "gemma4:26b"
    "granite4.1:30b"
    "qwen3.6:27b"
    "qwen3.5:27b"
    "devstral-small-2:24b"
    "lfm2:24b-a2b"
    "gemma4:e4b-it-q4_K_M"
    "qwen3:14b"
    "ministral-3:14b"
    "phi4-tools:14b"
    "phi4:14b"
    "qwen3.5:9b-48k"
    "qwen3.5:9b"
    "ministral-3:8b"
    "granite4.1:8b"
    "qwen3:8b"
    "lfm2.5:8b"
    "rnj-1:8b"
    "granite4.1:3b"
)

model_slug() {
    # Mesma lógica do forge_runner.py
    echo "$1" | sed 's/[:\/.]/\-/g' | sed 's/--*/-/g' | sed 's/-$//'
}

unload_ollama() {
    curl -s http://localhost:11434/api/generate \
        -d '{"model":"gemma4:26b","keep_alive":0}' > /dev/null 2>&1 || true
    sleep 2
}

read_score() {
    local json_dir="$1"
    local json=$(ls "${json_dir}/"*.json 2>/dev/null | sort -r | head -1)
    if [[ -f "$json" ]]; then
        python3 -c "
import json
try:
    d=json.load(open('$json'))
    print(f\"{d.get('auto_score','?')}/{d.get('auto_max','?')} ({d.get('auto_pct','?')}%)\")
except: print('err')
" 2>/dev/null || echo "err"
    else
        echo "no result"
    fi
}

declare -A SCORE_DIRECT
declare -A SCORE_OPENCODE
declare -A SCORE_OPENHANDS

# ─── FASE 0: Controle Sonnet ──────────────────────────────────────────────────
log "═══ FASE 0: Controle Claude Sonnet 4.6 ═══"
$PYTHON_VENV -u scripts/forge_claude_runner.py --scenario F5 2>&1 | tee -a "$LOG_FILE" || true
SCORE_SONNET=$(read_score "results/F5/claude-sonnet-4-6")
log "Sonnet: $SCORE_SONNET"

# ─── FASE 1: FORGE direct ─────────────────────────────────────────────────────
log ""
log "═══ FASE 1: FORGE Direct (${#OLLAMA_MODELS[@]} modelos) ═══"

for MODEL in "${OLLAMA_MODELS[@]}"; do
    log "── direct: $MODEL"
    unload_ollama
    $PYTHON_SYS -u scripts/forge_runner.py "$MODEL" --scenario F5 2>&1 | tee -a "$LOG_FILE" || true
    SLUG=$(model_slug "$MODEL")
    SCORE=$(read_score "results/F5/${SLUG}")
    SCORE_DIRECT["$MODEL"]="$SCORE"
    log "  → $MODEL (direct): $SCORE"
done

# ─── FASE 2: opencode ─────────────────────────────────────────────────────────
log ""
log "═══ FASE 2: opencode (${#OLLAMA_MODELS[@]} modelos) ═══"

for MODEL in "${OLLAMA_MODELS[@]}"; do
    log "── opencode: $MODEL"
    unload_ollama
    OC_SLUG="opencode-$(model_slug "$MODEL")"
    $PYTHON_SYS -u scripts/forge_opencode_runner.py \
        --scenario F5 --model "ollama-cloud/${MODEL}" 2>&1 | tee -a "$LOG_FILE" || true
    SCORE=$(read_score "results/F5/${OC_SLUG}")
    SCORE_OPENCODE["$MODEL"]="$SCORE"
    log "  → $MODEL (opencode): $SCORE"
done

# ─── FASE 3: OpenHands — todos os modelos ─────────────────────────────────────
log ""
log "═══ FASE 3: OpenHands (${#OLLAMA_MODELS[@]} modelos) ═══"

for MODEL in "${OLLAMA_MODELS[@]}"; do
    log "── openhands: $MODEL"
    unload_ollama
    OH_SLUG="openhands-$(model_slug "$MODEL")"
    $PYTHON_SYS -u scripts/forge_openhands_runner.py \
        --scenario F5 --model "ollama/${MODEL}" 2>&1 | tee -a "$LOG_FILE" || true
    SCORE=$(read_score "results/F5/${OH_SLUG}")
    SCORE_OPENHANDS["$MODEL"]="$SCORE"
    log "  → $MODEL (openhands): $SCORE"
done

# ─── RELATÓRIO FINAL ──────────────────────────────────────────────────────────
log ""
log "═══ RELATÓRIO FINAL ═══"

{
echo "# FORGE F5 — Overnight Results"
echo "Executado: $(date)"
echo ""
echo "## Controle"
echo "| Modelo | Harness | Score |"
echo "|--------|---------|-------|"
echo "| claude-sonnet-4-6 | Claude API | ${SCORE_SONNET} |"
echo ""
echo "## Resultados por modelo"
echo ""
echo "| Modelo | FORGE direct | opencode | OpenHands | Melhor |"
echo "|--------|-------------|----------|-----------|--------|"
for MODEL in "${OLLAMA_MODELS[@]}"; do
    D="${SCORE_DIRECT[$MODEL]:-—}"
    O="${SCORE_OPENCODE[$MODEL]:-—}"
    H="${SCORE_OPENHANDS[$MODEL]:-—}"
    BEST=$(python3 -c "
import re
scores = {'direct': '$D', 'opencode': '$O', 'openhands': '$H'}
def pct(s):
    m = re.search(r'(\d+)%', s)
    return int(m.group(1)) if m else -1
best = max(scores.items(), key=lambda x: pct(x[1]))
print(f'{best[0]}: {best[1]}')
" 2>/dev/null || echo "—")
    echo "| \`$MODEL\` | $D | $O | $H | $BEST |"
done
echo ""
echo "## Modelos com score ≥ 50% (algum harness)"
echo ""
for MODEL in "${OLLAMA_MODELS[@]}"; do
    for SCORE in "${SCORE_DIRECT[$MODEL]:-0}" "${SCORE_OPENCODE[$MODEL]:-0}" "${SCORE_OPENHANDS[$MODEL]:-0}"; do
        PCT=$(echo "$SCORE" | grep -oP '\d+(?=%)' || echo "0")
        if [[ "$PCT" -ge 50 ]]; then
            echo "  - \`$MODEL\`: $SCORE"
            break
        fi
    done
done
} | tee "$SUMMARY_FILE"

log "Batch concluído. Resumo: $SUMMARY_FILE"
