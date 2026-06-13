#!/usr/bin/env python3
"""
FORGE Pipeline Orchestrator — encadeia cenários automaticamente.

Fluxo:
  1. Aguarda batch do cenário atual terminar (monitora log)
  2. Roda o judge (Gemini externo)
  3. Filtra modelos que completaram a tarefa (entregaram arquivos obrigatórios)
  4. Avisa no Telegram com resumo
  5. Dispara batch do próximo cenário com modelos aprovados
  6. Reinicia o watcher para o novo cenário

Uso:
    python3 forge_pipeline.py --start F1 --through F5
    python3 forge_pipeline.py --start F2 --models qwen3.5:9b,qwen3.5:27b
"""
import argparse
import json
import os
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

FORGE_DIR   = Path(__file__).parent
RESULTS_DIR = FORGE_DIR / "results"
SCRIPTS_DIR = FORGE_DIR / "scripts"

TOKEN   = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CHAT_ID = int(os.environ.get("TELEGRAM_CHAT_ID", "0"))

JUDGE_MODEL  = "gemini-2.5-flash"
SCENARIOS    = ["F1", "F2", "F3", "F4", "F5"]

ALL_MODELS = [
    "granite4.1:3b", "rnj-1:8b", "lfm2.5:8b", "qwen3:8b",
    "granite4.1:8b", "ministral-3:8b", "qwen3.5:9b", "qwen3.5:9b-48k",
    "gemma4:12b", "phi4:14b", "ministral-3:14b", "phi4-tools:14b",
    "qwen3:14b", "gemma4:e4b-it-q4_K_M", "lfm2:24b-a2b",
    "devstral-small-2:24b", "qwen3.5:27b", "qwen3.6:27b",
    "gemma4:26b", "granite4.1:30b",
]


# ── Telegram ────────────────────────────────────────────────────────────────

def send(text: str):
    if not TOKEN or not CHAT_ID:
        print(f"[pipeline] sem credenciais Telegram — msg: {text[:80]}")
        return
    url  = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    data = urllib.parse.urlencode({"chat_id": CHAT_ID, "text": text}).encode()
    try:
        urllib.request.urlopen(
            urllib.request.Request(url, data=data), timeout=10
        )
        print(f"[pipeline] >> {text[:100]}")
    except Exception as e:
        print(f"[pipeline] Telegram ERRO: {e}")


# ── Aguardar fim do batch ────────────────────────────────────────────────────

def wait_for_batch(scenario: str, poll_s: int = 30):
    log_path  = Path(f"/tmp/forge_{scenario.lower()}_batch.log")
    sentinel  = f"Pipeline {scenario} concluído"
    print(f"[pipeline] aguardando fim do batch {scenario} (log: {log_path})")
    while True:
        if log_path.exists():
            content = log_path.read_text(errors="replace")
            if sentinel in content:
                print(f"[pipeline] batch {scenario} concluído detectado")
                return
        time.sleep(poll_s)


# ── Rodar judge ──────────────────────────────────────────────────────────────

def run_judge(scenario: str):
    results_dir = RESULTS_DIR / scenario
    if not results_dir.exists():
        print(f"[pipeline] diretório de resultados não encontrado: {results_dir}")
        return
    env = {**os.environ}
    # garante que GEMINI_API_KEY está disponível
    if not env.get("GEMINI_API_KEY"):
        # tenta carregar do .env.secrets
        secrets = Path.home() / ".env.secrets"
        if secrets.exists():
            for line in secrets.read_text().splitlines():
                if line.startswith("GEMINI_API_KEY="):
                    env["GEMINI_API_KEY"] = line.split("=", 1)[1].strip()
                    break
    print(f"[pipeline] rodando judge {JUDGE_MODEL} em {scenario}...")
    subprocess.run(
        [sys.executable, str(SCRIPTS_DIR / "forge_judge.py"),
         str(results_dir), "--model", JUDGE_MODEL],
        cwd=str(FORGE_DIR), env=env, check=False
    )


# ── Filtrar modelos aprovados ────────────────────────────────────────────────

def get_passing_models(scenario: str) -> list[str]:
    """
    Retorna modelos que completaram a tarefa (sem judge_blocked_reason)
    e cujo result JSON existe.
    """
    results_dir = RESULTS_DIR / scenario
    passing     = []
    blocked     = []
    no_result   = []

    for model in ALL_MODELS:
        slug       = model.replace(":", "-").replace("/", "_")
        model_dir  = results_dir / slug
        json_files = sorted(model_dir.glob("*.json")) if model_dir.exists() else []
        json_files = [f for f in json_files if "workdir" not in str(f)]

        if not json_files:
            no_result.append(model)
            continue

        latest = json_files[-1]
        try:
            data   = json.loads(latest.read_text())
            reason = data.get("judge_blocked_reason")
            score  = data.get("auto_pct", 0)
            if reason:
                blocked.append((model, reason, score))
            else:
                passing.append((model, score))
        except Exception as e:
            no_result.append(model)

    print(f"\n[pipeline] Resultado {scenario}:")
    print(f"  Aprovados ({len(passing)}): {[m for m,_ in passing]}")
    print(f"  Bloqueados ({len(blocked)}): {[m for m,_,_ in blocked]}")
    print(f"  Sem resultado ({len(no_result)}): {no_result}")

    return [m for m, _ in passing]


# ── Resumo para Telegram ─────────────────────────────────────────────────────

def build_summary(scenario: str, passing: list[str]) -> str:
    results_dir = RESULTS_DIR / scenario
    lines = [f"FORGE - {scenario} - Batch completo\n"]

    for model in ALL_MODELS:
        slug       = model.replace(":", "-").replace("/", "_")
        model_dir  = results_dir / slug
        json_files = sorted(model_dir.glob("*.json")) if model_dir.exists() else []
        json_files = [f for f in json_files if "workdir" not in str(f)]

        if not json_files:
            lines.append(f"  {model}: sem resultado")
            continue

        try:
            data    = json.loads(json_files[-1].read_text())
            score   = f"{data.get('auto_score','?')}/{data.get('auto_max','?')} ({data.get('auto_pct','?')}%)"
            blocked = data.get("judge_blocked_reason")
            status  = "OK" if not blocked else "BLOQUEADO"
            lines.append(f"  [{status}] {model}: {score}")
        except Exception:
            lines.append(f"  {model}: erro ao ler")

    next_models = ", ".join(passing) if passing else "nenhum"
    lines.append(f"\nAvancam para proximo cenario ({len(passing)}):\n{next_models}")
    return "\n".join(lines)


# ── Iniciar batch ────────────────────────────────────────────────────────────

def start_batch(scenario: str, models: list[str]):
    """Atualiza a lista de modelos no batch script e inicia o processo."""
    # Gera arquivo temporário com lista de modelos para o batch
    models_file = FORGE_DIR / f".models_{scenario.lower()}.txt"
    models_file.write_text("\n".join(models))

    log_path = f"/tmp/forge_{scenario.lower()}_batch.log"

    # Gera script de batch inline para este cenário específico
    batch_content = _render_batch_script(scenario, models)
    batch_path    = FORGE_DIR / f"run_{scenario.lower()}_batch.sh"
    batch_path.write_text(batch_content)
    batch_path.chmod(0o755)

    print(f"[pipeline] iniciando batch {scenario} com {len(models)} modelos")
    subprocess.Popen(
        ["bash", str(batch_path)],
        cwd=str(FORGE_DIR),
        stdout=open(log_path, "w"),
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )


def _render_batch_script(scenario: str, models: list[str]) -> str:
    models_block = "\n".join(f'  "{m}"' for m in models)
    return f"""#!/bin/bash
# FORGE {scenario} — Batch gerado pelo pipeline orchestrator
set -euo pipefail

FORGE_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$FORGE_DIR"

MODELS=(
{models_block}
)

log() {{ echo "$@"; }}

unload_all() {{
  log "[batch] descarregando modelos da VRAM..."
  curl -s http://localhost:11434/api/ps | python3 -c "
import sys, json
models = json.load(sys.stdin).get('models', [])
for m in models:
    print(m['name'])
" | while read -r name; do
    curl -s -X POST http://localhost:11434/api/generate \\
      -d "{{\\\"model\\\":\\\"$name\\\",\\\"keep_alive\\\":0}}" > /dev/null
    log "  descarregado: $name"
  done
}}

vram_status() {{
  local used
  used=$(curl -s http://localhost:11434/api/ps | python3 -c "
import sys, json
models = json.load(sys.stdin).get('models', [])
total = sum(m.get('size_vram', 0) for m in models)
print(total // 1024 // 1024)
")
  log "[vram] uso atual: ${{used}} MB"
}}

log "================================================================"
log "  FORGE {scenario} — Batch"
log "  $(date '+%Y-%m-%d %H:%M:%S')"
log "  Ollama: $(docker exec ollama ollama --version 2>/dev/null | awk '{{print $NF}}')"
log "  Modelos: ${{#MODELS[@]}}"
log "================================================================"

unload_all
vram_status

PASSED=0; FAILED=0

for model in "${{MODELS[@]}}"; do
  log ""
  log "----------------------------------------------------------------"
  log "  >>> $model  $(date '+%H:%M:%S')"
  log "----------------------------------------------------------------"

  if python3 -u scripts/forge_runner.py "$model" --scenario "{scenario}"; then
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
log "  Pipeline {scenario} concluído — $(date '+%Y-%m-%d %H:%M:%S')"
log "  OK: $PASSED | ERRO: $FAILED"
log "================================================================"
"""


# ── Iniciar watcher ──────────────────────────────────────────────────────────

def start_watcher(scenario: str):
    subprocess.Popen(
        [sys.executable, str(FORGE_DIR / "forge_notify_watcher.py"), scenario],
        cwd=str(FORGE_DIR),
        env={**os.environ},
        start_new_session=True,
        stdout=open(f"/tmp/forge_watcher_{scenario.lower()}.log", "w"),
        stderr=subprocess.STDOUT,
    )
    print(f"[pipeline] watcher iniciado para {scenario}")


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--start",   required=True, help="Cenário de início (ex: F1)")
    parser.add_argument("--through", default="F5",  help="Cenário final (ex: F5)")
    parser.add_argument("--models",  default="",    help="Lista de modelos CSV (omitir = todos)")
    args = parser.parse_args()

    start_idx   = SCENARIOS.index(args.start)
    end_idx     = SCENARIOS.index(args.through)
    pipeline    = SCENARIOS[start_idx:end_idx + 1]

    current_models = (
        [m.strip() for m in args.models.split(",") if m.strip()]
        if args.models else ALL_MODELS
    )

    print(f"[pipeline] iniciando: {' → '.join(pipeline)}")
    print(f"[pipeline] modelos iniciais: {len(current_models)}")

    for i, scenario in enumerate(pipeline):
        is_last = (i == len(pipeline) - 1)

        # Aguarda batch (se já estiver rodando) ou inicia
        batch_log = Path(f"/tmp/forge_{scenario.lower()}_batch.log")
        if batch_log.exists() and f"Pipeline {scenario} concluído" in batch_log.read_text(errors="replace"):
            print(f"[pipeline] {scenario} já concluído — pulando para judge")
        else:
            # Se o batch ainda não começou, inicia
            runner_running = bool(subprocess.run(
                ["pgrep", "-f", f"forge_runner.py.*--scenario.*{scenario}"],
                capture_output=True
            ).returncode == 0)
            if not runner_running:
                send(f"FORGE - {scenario} - Iniciando batch com {len(current_models)} modelos")
                start_batch(scenario, current_models)
                start_watcher(scenario)

            wait_for_batch(scenario)

        # Judge
        send(f"FORGE - {scenario} - Rodando judge (Gemini)...")
        run_judge(scenario)

        # Filtra aprovados
        passing = get_passing_models(scenario)

        # Resumo e notificação
        summary = build_summary(scenario, passing)
        send(summary)

        if not passing:
            send(f"FORGE - {scenario} - Nenhum modelo passou! Pipeline encerrado.")
            print("[pipeline] nenhum modelo aprovado — encerrando")
            return

        if is_last:
            send(f"FORGE - Pipeline completo! Chegaram ao {scenario}: {len(passing)} modelos")
            return

        # Prepara próximo cenário
        next_scenario   = pipeline[i + 1]
        current_models  = passing
        send(f"FORGE - {scenario} aprovados: {len(passing)} modelos\nAvancando para {next_scenario}...")
        time.sleep(5)


if __name__ == "__main__":
    main()
