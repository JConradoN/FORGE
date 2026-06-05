"""
FORGE — Telegram Provider (semi-manual, PRD-mode)

Fluxo:
  1. Se o cenário tem `prd_file`: copia o PRD para o workdir como TASK.md
     e exibe mensagem curta: "execute o TASK.md"
  2. Senão: exibe o prompt completo para copiar
  3. Aguarda Enter (confirma que você enviou)
  4. Monitora o workdir até estabilizar (ignora TASK.md pré-existente)
  5. Avalia e salva resultado

Por que semi-manual:
  sendMessage via Bot API envia como o próprio bot — o Claudio ignora
  mensagens de si mesmo. O envio precisa vir da conta do usuário.
  Isso também testa exatamente o comportamento de uso diário.

Uso:
    python3 forge_telegram_runner.py --scenario F1
    python3 forge_telegram_runner.py --all --mock
    python3 forge_telegram_runner.py --scenario F3 --response "ANÁLISE CONCLUÍDA: ..."
"""

import argparse
import json
import shutil
import time
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))
from forge_runner import auto_evaluate, save_run_result, aggregate_runs, load_scenario, RESULTS_BASE

TELEGRAM_SLUG   = "telegram-gemma4-26b"
SCENARIOS_BASE  = Path(__file__).parent.parent / "scenarios"
POLL_INTERVAL_S = 5
TASK_TIMEOUT_S  = 600


def _workdir_snapshot(workdir: Path) -> dict:
    snap = {}
    for f in workdir.rglob("*"):
        if f.is_file():
            try:
                snap[str(f)] = f.stat().st_mtime
            except OSError:
                pass
    return snap


def wait_for_workdir(workdir: Path, seed_files: set,
                     timeout_s: int = TASK_TIMEOUT_S, stable_s: int = 30) -> bool:
    """
    Monitora o workdir até aparecerem arquivos além dos seed_files (ex: TASK.md).
    Retorna True quando estabilizar, False se timeout sem novos arquivos.
    """
    deadline    = time.time() + timeout_s
    last_snap   = {k: v for k, v in _workdir_snapshot(workdir).items()
                   if Path(k).name not in seed_files}
    last_change = time.time()

    print(f"  [monitor] aguardando arquivos de output "
          f"(timeout {timeout_s}s, estável >{stable_s}s)...", end="", flush=True)

    while time.time() < deadline:
        time.sleep(POLL_INTERVAL_S)
        snap = {k: v for k, v in _workdir_snapshot(workdir).items()
                if Path(k).name not in seed_files}

        if snap != last_snap:
            new_files = set(snap) - set(last_snap)
            if new_files:
                names = [Path(p).name for p in new_files]
                print(f" +{','.join(names)}", end="", flush=True)
            last_snap   = snap
            last_change = time.time()
        else:
            elapsed = time.time() - last_change
            if last_snap and elapsed >= stable_s:
                print(f" estável ({len(last_snap)} arquivo(s))")
                return True
            print(".", end="", flush=True)

    has_files = bool(last_snap)
    status    = f"com {len(last_snap)} arquivo(s)" if has_files else "vazio"
    print(f" TIMEOUT ({status})")
    return has_files


def _await_enter():
    try:
        with open("/dev/tty", "r") as tty:
            print("  >> Pressione ENTER após enviar as mensagens no Telegram... ",
                  end="", flush=True)
            tty.readline()
    except OSError:
        print("  >> (sem TTY — aguardando 20s automaticamente...)")
        time.sleep(20)
    print()


def run_telegram_agent(scenario_id: str, scenario: dict, workdir: Path,
                       port: int, prompt_vars: dict,
                       response_override: str = "") -> dict:
    """
    PRD-mode: se o cenário tem prd_file, copia TASK.md e envia mensagem curta.
    Senão: exibe o prompt completo para o usuário copiar.
    """
    t_start    = time.time()
    error      = None
    seed_files = set()          # arquivos colocados antes do agente começar

    prd_rel = scenario.get("prd_file")

    # Copiar fixtures de diretório (ex: buggy-module/) para o workdir
    for fixture_rel in scenario.get("fixture_dirs", []):
        src = SCENARIOS_BASE / fixture_rel
        dst = workdir / src.name
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(src, dst)
        # marcar todos os arquivos copiados como seed (não são outputs)
        for f in dst.rglob("*"):
            if f.is_file():
                seed_files.add(str(f.relative_to(workdir)))
        print(f"  [fixture] copiado: {src.name}/ → {dst}")

    if prd_rel:
        # ── PRD-mode ──────────────────────────────────────────────────────────
        prd_src = SCENARIOS_BASE / prd_rel
        prd_dst = workdir / "TASK.md"
        shutil.copy(prd_src, prd_dst)
        seed_files.add("TASK.md")
        print(f"  [prd] copiado: {prd_src.name} → {prd_dst}")

        cwd_cmd   = f"/cwd {workdir}"
        task_msg  = f"Execute o TASK.md que está no diretório fixado."

        print()
        print("  ┌─ ENVIE NO TELEGRAM ───────────────────────────────────────────┐")
        print(f"  │  1. {cwd_cmd}")
        print(f"  │  2. {task_msg}")
        print("  └────────────────────────────────────────────────────────────────┘")
        print()

    else:
        # ── prompt completo ───────────────────────────────────────────────────
        prompt_template = scenario.get("aurelia_prompt") or scenario["prompt"]
        prompt = prompt_template.format(
            model_slug=TELEGRAM_SLUG, port=port,
            workdir=str(workdir), **prompt_vars
        )
        full_prompt = (
            f"FORGE BENCHMARK — Cenário {scenario_id}\n"
            f"Diretório de trabalho: {workdir}\n"
            f"Salve todos os arquivos neste caminho absoluto.\n\n"
            f"{prompt}"
        )

        cwd_cmd = f"/cwd {workdir}"
        print()
        print("  ┌─ ENVIE NO TELEGRAM ───────────────────────────────────────────┐")
        print(f"  │  1. {cwd_cmd}")
        print("  │  2. (mensagem abaixo)")
        print("  └────────────────────────────────────────────────────────────────┘")
        print()
        print("  ┄" * 32)
        print(full_prompt)
        print("  ┄" * 32)
        print()

    _await_enter()

    completed = wait_for_workdir(workdir, seed_files, timeout_s=TASK_TIMEOUT_S)
    if not completed:
        error = f"timeout {TASK_TIMEOUT_S}s — sem arquivos de output"

    duration_ms = int((time.time() - t_start) * 1000)
    return {
        "turns":          1,
        "tool_calls":     [],
        "final_response": response_override,
        "error":          error,
        "duration_ms":    duration_ms,
        "tok_total":      0,
        "loop_exhausted": False,
        "provider":       "telegram",
        "prd_mode":       bool(prd_rel),
        "note":           "semi-manual: usuário enviou via Telegram, runner monitorou workdir",
    }


def main():
    parser = argparse.ArgumentParser(description="FORGE — Telegram Provider (semi-manual)")
    parser.add_argument("--scenario",  nargs="+")
    parser.add_argument("--all",       action="store_true")
    parser.add_argument("--runs",      type=int, default=1)
    parser.add_argument("--port-base", type=int, default=8500)
    parser.add_argument("--mock",      action="store_true")
    parser.add_argument("--response",  type=str, default="",
                        help="Texto da resposta final do bot (para checks de texto)")
    args = parser.parse_args()

    if args.all:
        scenario_ids = [p.stem for p in sorted(SCENARIOS_BASE.glob("*.json"))]
    elif args.scenario:
        scenario_ids = args.scenario
    else:
        parser.error("Especifique --scenario F1 ou --all")

    print(f"\n{'='*64}")
    print(f"  FORGE — Telegram Provider (semi-manual)")
    print(f"  Cenários : {', '.join(scenario_ids)}")
    print(f"  Runs/cen.: {args.runs}")
    print(f"  Mock     : {'sim' if args.mock else 'não'}")
    print(f"{'='*64}")
    print()
    print("  Fluxo: runner prepara workdir → você envia no Telegram → runner avalia")
    print()

    for i, sid in enumerate(scenario_ids):
        print(f"{'─'*64}")
        try:
            scenario = load_scenario(sid)
        except FileNotFoundError as e:
            print(f"  ERRO: {e}")
            continue

        port    = args.port_base + i
        workdir = RESULTS_BASE / sid / TELEGRAM_SLUG / "workdir"
        workdir.mkdir(parents=True, exist_ok=True)

        prompt_vars = dict(scenario.get("prompt_vars", {}))
        if args.mock:
            prompt_vars.update(scenario.get("prompt_vars_mock", {}))

        checks_key = "aurelia_auto_checks"
        if checks_key in scenario:
            scenario = dict(scenario, auto_checks=scenario[checks_key])

        print(f"  [{sid}] {scenario['name']}")
        print(f"  workdir : {workdir}")
        if scenario.get("prd_file"):
            print(f"  PRD     : {scenario['prd_file']}  →  TASK.md")

        run_summaries = []

        for run_idx in range(1, args.runs + 1):
            if args.runs > 1:
                print(f"\n  ── Run {run_idx}/{args.runs} ──")

            # limpa outputs do run anterior (preserva apenas fixtures externas)
            for f in workdir.glob("*"):
                if f.is_file() and f.name != "TASK.md":
                    f.unlink()

            agent_result = run_telegram_agent(
                sid, scenario, workdir, port, prompt_vars,
                response_override=args.response
            )
            auto_eval = auto_evaluate(scenario, workdir, agent_result, TELEGRAM_SLUG)
            out_file  = save_run_result(sid, TELEGRAM_SLUG, run_idx, workdir,
                                        agent_result, auto_eval, scenario)

            run_summaries.append({**auto_eval, "error": agent_result["error"],
                                   "loop_exhausted": agent_result["loop_exhausted"]})

            print(f"\n  Auto score : {auto_eval['score']}/{auto_eval['max_score']} ({auto_eval['pct']}%)")
            for label, c in auto_eval["checks"].items():
                mark = "✓" if c["passed"] else "✗"
                print(f"    {mark} {label}: {c['detail']}")
            print(f"  Salvo em   : {out_file.name}")

            if run_idx < args.runs:
                print(f"\n  Aguardando 30s antes do próximo run...")
                time.sleep(30)

        if args.runs > 1:
            agg = aggregate_runs(run_summaries)
            print(f"\n  ── Agregado ({args.runs} runs) ──")
            print(f"  AUTO mean  : {agg['auto_pct_mean']}% ± {agg['auto_pct_std']}%")

    print(f"\n{'='*64}\n")


if __name__ == "__main__":
    main()
