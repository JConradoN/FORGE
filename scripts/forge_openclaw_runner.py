"""
FORGE — OpenClaw Provider
Executa cenários FORGE via OpenClaw Gateway + ACP coding agent.

OpenClaw roteia tarefas para gemma4:26b via Ollama local.
O Gateway precisa estar rodando: `openclaw gateway run --force &`

Uso:
    # Inicia gateway primeiro
    OLLAMA_API_KEY=ollama-local openclaw gateway run --force &
    sleep 5

    python3 forge_openclaw_runner.py --scenario F5
    python3 forge_openclaw_runner.py --all

Arquitetura:
    FORGE runner → openclaw agent → Gateway → Ollama gemma4:26b
                                           ↓
                                    file tools via ACP
"""

import argparse
import json
import os
import shutil
import subprocess
import time
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))
from forge_runner import (
    auto_evaluate, save_run_result, aggregate_runs,
    load_scenario, RESULTS_BASE, SCENARIOS_BASE,
)

OPENCLAW_SLUG  = "openclaw-gemma4-26b"
OPENCLAW_MODEL = "ollama/gemma4:26b"
TASK_TIMEOUT_S = 600
GATEWAY_PORT   = 19000   # porta padrão do OpenClaw Gateway

_ENV = {**os.environ, "OLLAMA_API_KEY": "ollama-local"}


def run_openclaw_agent(scenario_id: str, prompt: str, workdir: Path) -> dict:
    """
    Executa via `openclaw agent --local --agent main`.
    Modo local: sem Gateway, fala direto com Ollama.
    """
    t_start        = time.time()
    error          = None
    final_response = ""
    tool_calls_log = []
    tok_total      = 0

    print(f"\n  [openclaw] modelo={OPENCLAW_MODEL} (local)")
    print(f"  [openclaw] workdir={workdir}")

    cmd = [
        "openclaw", "agent",
        "--local",
        "--agent", "main",
        "--model", OPENCLAW_MODEL,
        "--message", prompt,
        "--json",
    ]

    print(f"  [openclaw] enviando tarefa ({len(prompt)} chars)...", end="", flush=True)

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=TASK_TIMEOUT_S,
            cwd=str(workdir),
            env=_ENV,
        )
        if result.returncode == 0:
            try:
                d = json.loads(result.stdout.strip())
                payloads = d.get("payloads", [])
                final_response = " ".join(p.get("text", "") for p in payloads if p.get("text"))
                usage = d.get("meta", {}).get("agentMeta", {}).get("usage", {})
                tok_total = usage.get("total", 0)
            except json.JSONDecodeError:
                final_response = result.stdout.strip()
        else:
            error = result.stderr.strip()[:300] or f"exit {result.returncode}"
        print(f" done ({len(final_response)} chars, {tok_total} tok)")

    except subprocess.TimeoutExpired:
        error = f"timeout {TASK_TIMEOUT_S}s"
        print(" TIMEOUT")
    except Exception as e:
        error = str(e)
        print(f" ERRO: {e}")

    duration_ms = int((time.time() - t_start) * 1000)
    return {
        "turns":          1,
        "tool_calls":     tool_calls_log,
        "final_response": final_response,
        "error":          error,
        "duration_ms":    duration_ms,
        "tok_total":      tok_total,
        "loop_exhausted": False,
        "provider":       "openclaw",
    }


def main():
    parser = argparse.ArgumentParser(description="FORGE — OpenClaw Provider")
    parser.add_argument("--scenario",  nargs="+")
    parser.add_argument("--all",       action="store_true")
    parser.add_argument("--runs",      type=int, default=1)
    parser.add_argument("--port-base", type=int, default=8800)
    parser.add_argument("--mock",      action="store_true")
    args = parser.parse_args()

    if args.all:
        scenario_ids = [p.stem for p in sorted(SCENARIOS_BASE.glob("*.json"))]
    elif args.scenario:
        scenario_ids = args.scenario
    else:
        parser.error("Especifique --scenario F5 ou --all")

    print(f"\n{'='*64}")
    print(f"  FORGE — OpenClaw Provider")
    print(f"  Modelo    : {OPENCLAW_MODEL}")
    print(f"  Cenários  : {', '.join(scenario_ids)}")
    print(f"  Runs/cen. : {args.runs}")
    print(f"  Modo      : local (--local, sem Gateway)")
    print(f"{'='*64}")

    for i, sid in enumerate(scenario_ids):
        print(f"\n{'─'*64}")
        try:
            scenario = load_scenario(sid)
        except FileNotFoundError as e:
            print(f"  ERRO: {e}")
            continue

        port    = args.port_base + i
        workdir = RESULTS_BASE / sid / OPENCLAW_SLUG / "workdir"
        workdir.mkdir(parents=True, exist_ok=True)

        # Copia fixtures e PRD
        for fixture_rel in scenario.get("fixture_dirs", []):
            src = SCENARIOS_BASE / fixture_rel
            dst = workdir / src.name
            if dst.exists():
                shutil.rmtree(dst)
            shutil.copytree(src, dst)
            print(f"  [fixture] copiado: {src.name}/")
        prd_rel = scenario.get("prd_file")
        if prd_rel:
            src = SCENARIOS_BASE / prd_rel
            shutil.copy(src, workdir / "TASK.md")
            print(f"  [prd] copiado: {src.name} → TASK.md")

        prompt_vars = dict(scenario.get("prompt_vars", {}))
        if args.mock:
            prompt_vars.update(scenario.get("prompt_vars_mock", {}))

        if prd_rel:
            prompt = f"Leia e execute o TASK.md em {workdir}."
        else:
            prompt_template = scenario.get("aurelia_prompt") or scenario["prompt"]
            prompt = prompt_template.format(
                model_slug=OPENCLAW_SLUG, port=port,
                workdir=str(workdir), **prompt_vars
            )

        if "aurelia_auto_checks" in scenario:
            scenario = dict(scenario, auto_checks=scenario["aurelia_auto_checks"])

        print(f"  [{sid}] {scenario['name']}")
        print(f"  workdir : {workdir}")

        run_summaries = []

        for run_idx in range(1, args.runs + 1):
            if args.runs > 1:
                print(f"\n  ── Run {run_idx}/{args.runs} ──")
                for f in workdir.glob("*"):
                    if f.is_file() and f.name not in {"TASK.md"}:
                        f.unlink()

            agent_result = run_openclaw_agent(sid, prompt, workdir)
            auto_eval    = auto_evaluate(scenario, workdir, agent_result, OPENCLAW_SLUG,
                                         extra_vars={"port": port})
            out_file     = save_run_result(sid, OPENCLAW_SLUG, run_idx, workdir,
                                           agent_result, auto_eval, scenario)

            run_summaries.append({**auto_eval, "error": agent_result["error"],
                                   "loop_exhausted": agent_result["loop_exhausted"]})

            print(f"\n  Auto score : {auto_eval['score']}/{auto_eval['max_score']} ({auto_eval['pct']}%)")
            for label, c in auto_eval["checks"].items():
                mark = "✓" if c["passed"] else "✗"
                print(f"    {mark} {label}: {c['detail']}")
            print(f"  Salvo em   : {out_file.name}")

        if args.runs > 1:
            agg = aggregate_runs(run_summaries)
            print(f"\n  ── Agregado ({args.runs} runs) ──")
            print(f"  AUTO mean  : {agg['auto_pct_mean']}% ± {agg['auto_pct_std']}%")

    print(f"\n{'='*64}\n")


if __name__ == "__main__":
    main()
