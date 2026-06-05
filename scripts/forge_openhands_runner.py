"""
FORGE — OpenHands Provider
Executa cenários FORGE via OpenHands REST API (Docker).

O OpenHands roda num sandbox Docker com o workdir montado como workspace.
O runner gerencia o ciclo de vida do container para cada run.

Pré-requisitos:
    docker pull ghcr.io/all-hands-ai/openhands:0.42
    docker pull ghcr.io/all-hands-ai/runtime:0.42-nikolaik

Uso:
    python3 forge_openhands_runner.py --scenario F5
    python3 forge_openhands_runner.py --all
"""

import argparse
import json
import shutil
import subprocess
import time
import urllib.request
import urllib.error
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))
from forge_runner import (
    auto_evaluate, save_run_result, aggregate_runs,
    load_scenario, RESULTS_BASE, SCENARIOS_BASE,
)

OPENHANDS_IMAGE   = "ghcr.io/all-hands-ai/openhands:0.42"
RUNTIME_IMAGE     = "ghcr.io/all-hands-ai/runtime:0.42-nikolaik"
OPENHANDS_SLUG    = "openhands-gemma4-26b"
LLM_MODEL         = "ollama/gemma4:26b"
OPENHANDS_PORT    = 3011          # porta dedicada ao runner (evita conflito com :3010 web)
POLL_INTERVAL_S   = 5
TASK_TIMEOUT_S    = 600
CONTAINER_NAME    = "forge-openhands"

# IP do host acessível de dentro do container Docker
_HOST_IP = None


def _host_ip() -> str:
    global _HOST_IP
    if _HOST_IP:
        return _HOST_IP
    try:
        result = subprocess.run(
            ["ip", "route", "show", "default"],
            capture_output=True, text=True
        )
        _HOST_IP = result.stdout.split()[2]
    except Exception:
        import socket
        _HOST_IP = socket.gethostbyname(socket.gethostname())
    return _HOST_IP


def _oh_request(method: str, path: str, body: dict | None = None) -> dict:
    url  = f"http://localhost:{OPENHANDS_PORT}{path}"
    data = json.dumps(body).encode() if body else None
    req  = urllib.request.Request(url, data=data,
                                   headers={"Content-Type": "application/json"},
                                   method=method)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def _wait_healthy(timeout_s: int = 60) -> bool:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            r = urllib.request.urlopen(f"http://localhost:{OPENHANDS_PORT}/alive", timeout=3)
            if r.status == 200:
                return True
        except Exception:
            pass
        time.sleep(2)
    return False


def _start_container(workdir: Path) -> bool:
    """Inicia container OpenHands com workdir montado como workspace."""
    # Para container anterior se existir
    subprocess.run(["docker", "rm", "-f", CONTAINER_NAME],
                   capture_output=True)
    time.sleep(2)

    host_ip = _host_ip()
    cmd = [
        "docker", "run", "-d",
        "--name", CONTAINER_NAME,
        "-p", f"{OPENHANDS_PORT}:3000",
        "-e", f"LLM_MODEL={LLM_MODEL}",
        "-e", f"LLM_BASE_URL=http://{host_ip}:11434",
        "-e", "LLM_API_KEY=ollama",
        "-e", f"SANDBOX_RUNTIME_CONTAINER_IMAGE={RUNTIME_IMAGE}",
        "-e", f"WORKSPACE_MOUNT_PATH={workdir}",
        "-v", "/var/run/docker.sock:/var/run/docker.sock",
        "-v", f"{workdir}:/opt/workspace_base",
        OPENHANDS_IMAGE,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"\n  [openhands] ERRO ao iniciar container: {result.stderr[:200]}")
        return False
    return True


def _configure_settings() -> bool:
    host_ip = _host_ip()
    try:
        _oh_request("POST", "/api/settings", {
            "llm_model":   LLM_MODEL,
            "llm_base_url": f"http://{host_ip}:11434",
            "llm_api_key": "ollama",
            "agent":       "CodeActAgent",
            "language":    "pt",
            "enable_default_condenser": False,
        })
        return True
    except Exception as e:
        print(f"  [openhands] AVISO settings: {e}")
        return False


def run_openhands_agent(scenario_id: str, prompt: str, workdir: Path) -> dict:
    t_start = time.time()
    error   = None
    final_response = ""
    tool_calls_log = []

    print(f"\n  [openhands] iniciando container (workdir={workdir.name})")
    if not _start_container(workdir):
        return {"error": "falha ao iniciar container", "turns": 0, "tool_calls": [],
                "final_response": "", "duration_ms": 0, "tok_total": 0,
                "loop_exhausted": False, "provider": "openhands"}

    print(f"  [openhands] aguardando serviço...", end="", flush=True)
    if not _wait_healthy(timeout_s=60):
        return {"error": "timeout aguardando container", "turns": 0, "tool_calls": [],
                "final_response": "", "duration_ms": 0, "tok_total": 0,
                "loop_exhausted": False, "provider": "openhands"}
    print(" ok")

    _configure_settings()

    # Cria conversa
    print(f"  [openhands] enviando tarefa ({len(prompt)} chars)...", end="", flush=True)
    try:
        resp = _oh_request("POST", "/api/conversations",
                           {"initial_user_msg": prompt})
        conv_id = resp.get("conversation_id")
        if not conv_id:
            raise RuntimeError(f"sem conversation_id: {resp}")
    except Exception as e:
        return {"error": str(e), "turns": 0, "tool_calls": [],
                "final_response": "", "duration_ms": 0, "tok_total": 0,
                "loop_exhausted": False, "provider": "openhands"}

    # Aguarda conclusão via polling de status
    deadline = time.time() + TASK_TIMEOUT_S
    last_event_id = 0
    finished = False

    while time.time() < deadline:
        time.sleep(POLL_INTERVAL_S)
        try:
            # Busca status da conversa
            conv = _oh_request("GET", f"/api/conversations/{conv_id}")
            status = conv.get("status", "UNKNOWN")
            print(".", end="", flush=True)

            if status in ("STOPPED", "ERROR"):
                finished = True
                if status == "ERROR":
                    error = "OpenHands reportou status ERROR"
                break

            # Coleta eventos novos
            events_resp = _oh_request("GET",
                f"/api/conversations/{conv_id}/events?start_id={last_event_id}&limit=50")
            events = events_resp if isinstance(events_resp, list) else \
                     events_resp.get("events", [])

            for ev in events:
                eid = ev.get("id", 0)
                if eid > last_event_id:
                    last_event_id = eid

                src  = ev.get("source", "")
                etype = ev.get("type", "")

                if src == "agent" and etype == "message":
                    msg = ev.get("message", "") or ev.get("content", "")
                    if msg:
                        final_response = msg

                elif etype in ("run", "write", "read", "browse", "ipython_run_cell"):
                    tool_calls_log.append({
                        "name": etype,
                        "args": {"content": str(ev.get("command", ev.get("path", "")))[:100]},
                    })

                elif etype == "agent_state_changed":
                    state = ev.get("agent_state", "")
                    if state in ("FINISHED", "STOPPED", "ERROR"):
                        finished = True

            if finished:
                break

        except Exception as e:
            print(f"\n  [openhands] poll error: {e}")
            time.sleep(5)

    if not finished:
        error = f"timeout {TASK_TIMEOUT_S}s"

    print(f" {'concluído' if not error else 'ERRO'} ({len(tool_calls_log)} tool calls)")

    # Para container
    subprocess.run(["docker", "rm", "-f", CONTAINER_NAME], capture_output=True)

    duration_ms = int((time.time() - t_start) * 1000)
    return {
        "turns":          len([t for t in tool_calls_log]),
        "tool_calls":     tool_calls_log,
        "final_response": final_response,
        "error":          error,
        "duration_ms":    duration_ms,
        "tok_total":      0,
        "loop_exhausted": not finished,
        "provider":       "openhands",
    }


def main():
    parser = argparse.ArgumentParser(description="FORGE — OpenHands Provider")
    parser.add_argument("--scenario",  nargs="+")
    parser.add_argument("--all",       action="store_true")
    parser.add_argument("--runs",      type=int, default=1)
    parser.add_argument("--port-base", type=int, default=8700)
    parser.add_argument("--mock",      action="store_true")
    args = parser.parse_args()

    if args.all:
        scenario_ids = [p.stem for p in sorted(SCENARIOS_BASE.glob("*.json"))]
    elif args.scenario:
        scenario_ids = args.scenario
    else:
        parser.error("Especifique --scenario F5 ou --all")

    print(f"\n{'='*64}")
    print(f"  FORGE — OpenHands Provider")
    print(f"  LLM       : {LLM_MODEL}")
    print(f"  Container : {OPENHANDS_IMAGE}")
    print(f"  Runtime   : {RUNTIME_IMAGE}")
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
        workdir = RESULTS_BASE / sid / OPENHANDS_SLUG / "workdir"
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

        # Prompt — OpenHands trabalha em /opt/workspace_base dentro do container
        prompt_vars = dict(scenario.get("prompt_vars", {}))
        if args.mock:
            prompt_vars.update(scenario.get("prompt_vars_mock", {}))

        if prd_rel:
            prompt = (
                f"Leia o arquivo TASK.md no diretório de trabalho e execute "
                f"todas as etapas descritas. O diretório de trabalho é /opt/workspace_base."
            )
        else:
            prompt_template = scenario.get("aurelia_prompt") or scenario["prompt"]
            prompt = prompt_template.format(
                model_slug=OPENHANDS_SLUG, port=port,
                workdir="/opt/workspace_base", **prompt_vars
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

            agent_result = run_openhands_agent(sid, prompt, workdir)
            auto_eval    = auto_evaluate(scenario, workdir, agent_result, OPENHANDS_SLUG,
                                         extra_vars={"port": port})
            out_file     = save_run_result(sid, OPENHANDS_SLUG, run_idx, workdir,
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
