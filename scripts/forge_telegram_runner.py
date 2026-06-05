"""
FORGE — Telegram Provider (semi-manual)

Fluxo:
  1. Exibe os comandos para você enviar no Telegram
  2. Aguarda Enter (confirma que você enviou)
  3. Monitora o workdir até estabilizar
  4. Avalia e salva resultado

Por que semi-manual:
  sendMessage via Bot API envia como o próprio bot — o Claudio ignora
  mensagens de si mesmo. O envio precisa vir da conta do usuário.
  Isso também testa exatamente o comportamento de uso diário.

Uso:
    python3 forge_telegram_runner.py --scenario F1
    python3 forge_telegram_runner.py --all
    python3 forge_telegram_runner.py --scenario F1 --response "PÁGINA PUBLICADA: ..."
"""

import argparse
import json
import time
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))
from forge_runner import auto_evaluate, save_run_result, aggregate_runs, load_scenario, RESULTS_BASE

TELEGRAM_SLUG   = "telegram-gemma4-26b"
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


def wait_for_workdir(workdir: Path, timeout_s: int = TASK_TIMEOUT_S,
                     stable_s: int = 30) -> bool:
    """
    Monitora o workdir até os arquivos estabilizarem.
    Retorna True se há arquivos estáveis, False se timeout com workdir vazio.
    """
    deadline    = time.time() + timeout_s
    last_snap   = _workdir_snapshot(workdir)
    last_change = time.time()

    print(f"  [monitor] aguardando arquivos (timeout {timeout_s}s, estável >{stable_s}s)...",
          end="", flush=True)

    while time.time() < deadline:
        time.sleep(POLL_INTERVAL_S)
        snap = _workdir_snapshot(workdir)

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


def run_telegram_agent(scenario_id: str, cwd_cmd: str, full_prompt: str,
                       workdir: Path, response_override: str = "") -> dict:
    """
    Fluxo semi-manual:
    - Exibe os comandos a enviar no Telegram
    - Aguarda Enter do usuário
    - Monitora workdir
    """
    t_start = time.time()
    error   = None

    # ── exibe instruções ──────────────────────────────────────────────────────
    print()
    print("  ┌─ ENVIE AGORA NO TELEGRAM ─────────────────────────────────────┐")
    print(f"  │  1. {cwd_cmd}")
    print("  │")
    print("  │  2. (mensagem abaixo — copie tudo entre as linhas tracejadas)")
    print("  └────────────────────────────────────────────────────────────────┘")
    print()
    print("  ┄" * 32)
    print(full_prompt)
    print("  ┄" * 32)
    print()
    input("  >> Pressione ENTER após enviar as mensagens no Telegram... ")
    print()

    # ── monitora workdir ──────────────────────────────────────────────────────
    completed = wait_for_workdir(workdir, timeout_s=TASK_TIMEOUT_S)

    if not completed:
        error = f"timeout {TASK_TIMEOUT_S}s — workdir vazio"

    # resposta final: pode ser passada via --response se quiser capturar texto
    response_text = response_override

    duration_ms = int((time.time() - t_start) * 1000)
    return {
        "turns":          1,
        "tool_calls":     [],
        "final_response": response_text,
        "error":          error,
        "duration_ms":    duration_ms,
        "tok_total":      0,
        "loop_exhausted": False,
        "provider":       "telegram",
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
                        help="Texto da resposta final do bot (opcional, para checks de texto)")
    args = parser.parse_args()

    if args.all:
        scenario_ids = [p.stem for p in sorted(
            (Path(__file__).parent.parent / "scenarios").glob("*.json")
        )]
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
    print("  Como funciona:")
    print("  - O runner exibe os comandos a enviar no Telegram")
    print("  - Você envia manualmente pelo seu celular/app")
    print("  - O runner monitora o workdir e avalia quando pronto")
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

        prompt_template = scenario.get("aurelia_prompt") or scenario["prompt"]
        prompt = prompt_template.format(
            model_slug=TELEGRAM_SLUG,
            port=port,
            workdir=str(workdir),
            **prompt_vars
        )

        cwd_cmd     = f"/cwd {workdir}"
        full_prompt = (
            f"FORGE BENCHMARK — Cenário {sid}\n"
            f"Diretório de trabalho: {workdir}\n"
            f"Salve todos os arquivos neste caminho absoluto.\n\n"
            f"{prompt}"
        )

        if "aurelia_auto_checks" in scenario:
            scenario = dict(scenario, auto_checks=scenario["aurelia_auto_checks"])

        print(f"  [{sid}] {scenario['name']}")
        print(f"  workdir : {workdir}")

        run_summaries = []

        for run_idx in range(1, args.runs + 1):
            if args.runs > 1:
                print(f"\n  ── Run {run_idx}/{args.runs} ──")

            # limpa workdir para nova run
            if run_idx > 1:
                for f in workdir.glob("*"):
                    if f.is_file():
                        f.unlink()

            agent_result = run_telegram_agent(
                sid, cwd_cmd, full_prompt, workdir,
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
