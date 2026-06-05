"""
FORGE — Aurelia Provider
Executa cenários FORGE via Chat API do Aurelia (:18790).

O modelo (gemma4:26b) roda através do harness completo de produção:
pipeline Go, memória em 3 camadas, loop de tool use nativo, gestão de sessão.

Isso torna a comparação com o Claude justa: ambos têm seu agente de produção,
não apenas o modelo nu via API.

Uso:
    python3 forge_aurelia_runner.py --scenario F1
    python3 forge_aurelia_runner.py --all --runs 3 --mock
"""

import argparse
import datetime
import json
import time
import urllib.request
import urllib.error
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))
from forge_runner import auto_evaluate, save_run_result, aggregate_runs, load_scenario, RESULTS_BASE

AURELIA_URL  = "http://localhost:18790/api/chat"
AURELIA_SLUG = "aurelia-gemma4-26b"
TIMEOUT_S    = 620   # ligeiramente acima do defaultTimeout do server (600s)


def _aurelia_model() -> str:
    """Descobre qual modelo o Aurelia está usando via config."""
    try:
        cfg = (Path.home() / ".aurelia/config/app.json").read_text()
        return json.loads(cfg).get("default_model", "desconhecido")
    except:
        return "desconhecido"


def call_aurelia(text: str, session_key: str | None = None) -> dict:
    """
    Chama a Chat API do Aurelia.
    session_key mantém continuidade de sessão (herda /cwd binding).
    Retorna {"response": str, "chat_id": int, "latency_ms": int}.
    """
    payload = {"text": text}
    if session_key:
        payload["session_key"] = session_key

    data = json.dumps(payload).encode()
    req  = urllib.request.Request(
        AURELIA_URL, data=data,
        headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as r:
            return json.loads(r.read())
    except urllib.error.URLError as e:
        raise RuntimeError(f"Aurelia indisponível: {e}")
    except Exception as e:
        raise RuntimeError(str(e))


def run_aurelia_agent(scenario_id: str, prompt: str, workdir: Path) -> dict:
    """
    Executa um cenário via Aurelia.
    O Aurelia gerencia internamente o loop de tool use com o modelo.
    """
    t_start     = time.time()
    error       = None
    response_text = ""
    chat_id     = None
    # session_key fixo garante que /cwd e tarefa compartilhem a mesma sessão Aurelia
    session_key = f"forge-{scenario_id}-{int(t_start)}"

    print(f"\n  [aurelia] modelo={_aurelia_model()} | endpoint={AURELIA_URL}")
    print(f"  [aurelia] session_key={session_key}")

    # Injetar workdir no prompt para que o Aurelia saiba onde criar arquivos
    full_prompt = (
        f"FORGE BENCHMARK — Cenário {scenario_id}\n"
        f"Diretório de trabalho: {workdir}\n"
        f"IMPORTANTE: Salve todos os arquivos em '{workdir}/' (caminho absoluto).\n\n"
        f"{prompt}"
    )

    # Passo 1: bind do workdir na mesma session_key para ativar file tools
    print(f"  [aurelia] binding workdir: {workdir}")
    try:
        r0 = call_aurelia(f"/cwd {workdir}", session_key=session_key)
        chat_id = r0.get("chat_id")
        print(f"  [aurelia] cwd bound (chat_id={chat_id}, resp: {r0.get('response','')[:80]})")
    except RuntimeError as e:
        print(f"  [aurelia] AVISO: falha no bind do cwd: {e}")

    # Passo 2: tarefa na mesma session_key — herda o /cwd binding
    print(f"  [aurelia] enviando tarefa ({len(full_prompt)} chars)...")
    try:
        resp = call_aurelia(full_prompt, session_key=session_key)
        response_text = resp.get("response", "")
        chat_id       = resp.get("chat_id")
        latency_ms    = resp.get("latency_ms", 0)
        print(f"  [aurelia] resposta recebida ({len(response_text)} chars, {latency_ms}ms)")

        if response_text.startswith("⏱️"):
            print(f"  [aurelia] AVISO: heartbeat ainda presente — rebuildar Aurelia com o fix do server.go")
    except RuntimeError as e:
        error = str(e)
        print(f"  [aurelia] ERRO: {error}")

    duration_ms = int((time.time() - t_start) * 1000)

    # O Aurelia não expõe tool_calls individuais — registramos o que sabemos
    return {
        "turns":          1,        # Aurelia encapsula multi-turn internamente
        "tool_calls":     [],       # não exposto pela Chat API
        "final_response": response_text,
        "error":          error,
        "duration_ms":    duration_ms,
        "tok_total":      0,        # não exposto pela Chat API
        "loop_exhausted": False,
        "chat_id":        chat_id,
        "provider":       "aurelia",
        "internal_model": _aurelia_model(),
    }


def main():
    parser = argparse.ArgumentParser(description="FORGE — Aurelia Provider")
    parser.add_argument("--scenario",  nargs="+")
    parser.add_argument("--all",       action="store_true")
    parser.add_argument("--runs",      type=int, default=1)
    parser.add_argument("--port-base", type=int, default=8400)
    parser.add_argument("--mock",      action="store_true")
    args = parser.parse_args()

    model_name = _aurelia_model()

    if args.all:
        scenario_ids = [p.stem for p in sorted(
            (Path(__file__).parent.parent / "scenarios").glob("*.json")
        )]
    elif args.scenario:
        scenario_ids = args.scenario
    else:
        parser.error("Especifique --scenario F1 ou --all")

    print(f"\n{'='*64}")
    print(f"  FORGE — Aurelia Provider (harness de produção)")
    print(f"  Modelo    : {model_name}")
    print(f"  Endpoint  : {AURELIA_URL}")
    print(f"  Cenários  : {', '.join(scenario_ids)}")
    print(f"  Runs/cen. : {args.runs}")
    print(f"  Mock URLs : {'SIM (porta 9900)' if args.mock else 'NÃO'}")
    print(f"{'='*64}")

    # Verificar Aurelia disponível
    try:
        call_aurelia("ping")
    except RuntimeError as e:
        print(f"\n  ERRO: Aurelia não está respondendo: {e}")
        return

    for i, sid in enumerate(scenario_ids):
        print(f"\n{'─'*64}")
        try:
            scenario = load_scenario(sid)
        except FileNotFoundError as e:
            print(f"  ERRO: {e}")
            continue

        port    = args.port_base + i
        workdir = RESULTS_BASE / sid / AURELIA_SLUG / "workdir"
        workdir.mkdir(parents=True, exist_ok=True)

        prompt_vars = dict(scenario.get("prompt_vars", {}))
        if args.mock:
            prompt_vars.update(scenario.get("prompt_vars_mock", {}))

        # Usar aurelia_prompt (linguagem natural, sem tool names do FORGE)
        # Fallback para prompt padrão se não existir
        prompt_template = scenario.get("aurelia_prompt") or scenario["prompt"]
        prompt = prompt_template.format(
            model_slug=AURELIA_SLUG,
            port=port,
            workdir=str(workdir),
            **prompt_vars
        )

        # Usar aurelia_auto_checks se existir (sem tool_called checks)
        if "aurelia_auto_checks" in scenario:
            scenario = dict(scenario, auto_checks=scenario["aurelia_auto_checks"])

        print(f"  [{sid}] {scenario['name']}")
        print(f"  workdir : {workdir}")

        run_summaries = []

        for run_idx in range(1, args.runs + 1):
            if args.runs > 1:
                print(f"\n  ── Run {run_idx}/{args.runs} ──")

            agent_result = run_aurelia_agent(sid, prompt, workdir)
            auto_eval    = auto_evaluate(scenario, workdir, agent_result, AURELIA_SLUG)
            out_file     = save_run_result(sid, AURELIA_SLUG, run_idx, workdir,
                                           agent_result, auto_eval, scenario)

            run_summaries.append({**auto_eval, "error": agent_result["error"],
                                   "loop_exhausted": agent_result["loop_exhausted"]})

            print(f"\n  Auto score : {auto_eval['score']}/{auto_eval['max_score']} ({auto_eval['pct']}%)")
            for label, c in auto_eval["checks"].items():
                mark = "✓" if c["passed"] else "✗"
                print(f"    {mark} {label}: {c['detail']}")
            print(f"  Resposta   : {agent_result['final_response'][:200]}...")
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
