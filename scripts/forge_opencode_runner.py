"""
FORGE — opencode Provider
Executa cenários FORGE via opencode CLI com ollama-cloud/gemma4:26b.

opencode tem seus próprios file tools nativos (bash, read, write, edit) —
não usa as FORGE tools. O runner passa o workdir via --dir, executa, e
avalia os artefatos produzidos.

Uso:
    python3 forge_opencode_runner.py --scenario F5
    python3 forge_opencode_runner.py --all --runs 3
    python3 forge_opencode_runner.py --scenario F5 --model ollama-cloud/qwen3.5:9b-48k
"""

import argparse
import json
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

DEFAULT_MODEL   = "ollama-cloud/gemma4:26b"
OPENCODE_SLUG   = "opencode-gemma4-26b"
TASK_TIMEOUT_S  = 600


def _slug_from_model(model: str) -> str:
    return "opencode-" + model.split("/")[-1].replace(":", "-").replace(".", "")


def run_opencode_agent(prompt: str, workdir: Path,
                       model: str = DEFAULT_MODEL) -> dict:
    t_start        = time.time()
    error          = None
    final_response = ""
    tool_calls_log = []
    turns          = 0
    tok_total      = 0

    cmd = [
        "opencode", "run",
        "--model", model,
        "--format", "json",
        "--dir", str(workdir),
        "--dangerously-skip-permissions",
        prompt,
    ]

    print(f"\n  [opencode] modelo={model}")
    print(f"  [opencode] workdir={workdir}")
    print(f"  [opencode] executando", end="", flush=True)

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=TASK_TIMEOUT_S,
            cwd=str(workdir),
        )

        for line in proc.stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                ev    = json.loads(line)
                etype = ev.get("type", "")
                part  = ev.get("part", {})

                if etype == "text" and part.get("type") == "text":
                    final_response += part.get("text", "")

                elif etype == "step_finish":
                    turns += 1
                    tok_total += part.get("tokens", {}).get("total", 0)
                    print(".", end="", flush=True)

                elif etype in ("tool_use", "tool_call"):
                    tool_calls_log.append({
                        "turn":   turns,
                        "name":   part.get("tool", part.get("name", "?")),
                        "args":   part.get("input", {}),
                        "result": "",
                    })

            except (json.JSONDecodeError, KeyError):
                pass

        if proc.returncode != 0 and not final_response:
            stderr_msg = proc.stderr.strip()[:300] if proc.stderr else ""
            error = f"opencode exit {proc.returncode}: {stderr_msg}"

    except subprocess.TimeoutExpired:
        error = f"timeout {TASK_TIMEOUT_S}s"
    except Exception as e:
        error = str(e)

    print(f" done ({turns} steps, {tok_total} tok)")
    duration_ms = int((time.time() - t_start) * 1000)

    return {
        "turns":          turns,
        "tool_calls":     tool_calls_log,
        "final_response": final_response.strip(),
        "error":          error,
        "duration_ms":    duration_ms,
        "tok_total":      tok_total,
        "loop_exhausted": False,
        "provider":       "opencode",
        "model":          model,
    }


def main():
    parser = argparse.ArgumentParser(description="FORGE — opencode Provider")
    parser.add_argument("--scenario",  nargs="+")
    parser.add_argument("--all",       action="store_true")
    parser.add_argument("--runs",      type=int, default=1)
    parser.add_argument("--port-base", type=int, default=8600)
    parser.add_argument("--mock",      action="store_true")
    parser.add_argument("--model",     type=str, default=DEFAULT_MODEL)
    args = parser.parse_args()

    slug = _slug_from_model(args.model)

    if args.all:
        scenario_ids = [p.stem for p in sorted(SCENARIOS_BASE.glob("*.json"))]
    elif args.scenario:
        scenario_ids = args.scenario
    else:
        parser.error("Especifique --scenario F5 ou --all")

    print(f"\n{'='*64}")
    print(f"  FORGE — opencode Provider")
    print(f"  Modelo    : {args.model}")
    print(f"  Slug      : {slug}")
    print(f"  Cenários  : {', '.join(scenario_ids)}")
    print(f"  Runs/cen. : {args.runs}")
    print(f"{'='*64}")

    for i, sid in enumerate(scenario_ids):
        print(f"\n{'─'*64}")
        try:
            scenario = load_scenario(sid)
        except FileNotFoundError as e:
            print(f"  ERRO: {e}")
            continue

        port    = args.port_base + i
        workdir = RESULTS_BASE / sid / slug / "workdir"
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

        # Prompt
        prompt_vars = dict(scenario.get("prompt_vars", {}))
        if args.mock:
            prompt_vars.update(scenario.get("prompt_vars_mock", {}))

        # opencode tem seus próprios file tools — usa o prompt padrão
        # mas informa o workdir explicitamente
        prompt_template = scenario.get("aurelia_prompt") or scenario["prompt"]
        prompt = prompt_template.format(
            model_slug=slug, port=port,
            workdir=str(workdir), **prompt_vars
        )

        if prd_rel:
            prompt = f"Leia e execute o TASK.md em {workdir}. O diretório de trabalho é {workdir}."

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

            agent_result = run_opencode_agent(prompt, workdir, model=args.model)
            auto_eval    = auto_evaluate(scenario, workdir, agent_result, slug,
                                         extra_vars={"port": port})
            out_file     = save_run_result(sid, slug, run_idx, workdir,
                                           agent_result, auto_eval, scenario)

            run_summaries.append({**auto_eval, "error": agent_result["error"],
                                   "loop_exhausted": agent_result["loop_exhausted"]})

            print(f"\n  Auto score : {auto_eval['score']}/{auto_eval['max_score']} ({auto_eval['pct']}%)")
            for label, c in auto_eval["checks"].items():
                mark = "✓" if c["passed"] else "✗"
                print(f"    {mark} {label}: {c['detail']}")
            print(f"  Salvo em   : {out_file.name}")

            if run_idx < args.runs:
                time.sleep(10)

        if args.runs > 1:
            agg = aggregate_runs(run_summaries)
            print(f"\n  ── Agregado ({args.runs} runs) ──")
            print(f"  AUTO mean  : {agg['auto_pct_mean']}% ± {agg['auto_pct_std']}%")

    print(f"\n{'='*64}\n")


if __name__ == "__main__":
    main()
