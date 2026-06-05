"""
FORGE — Telegram Provider
Executa cenários FORGE enviando tarefas diretamente pelo Telegram.

O modelo (gemma4:26b) opera via Aurelia com a sessão real do Telegram:
- binding de cwd persistido no SQLite
- file tools habilitadas
- memória em 3 camadas ativa
- pipeline idêntico ao uso diário

Fluxo:
  1. Envia /cwd {workdir} → aguarda confirmação do binding
  2. Envia prompt da tarefa → aguarda resposta completa
  3. Avalia workdir (arquivos criados, conteúdo, servidor)

Uso:
    python3 forge_telegram_runner.py --scenario F1
    python3 forge_telegram_runner.py --all --runs 1
"""

import argparse
import json
import time
import urllib.request
import urllib.parse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))
from forge_runner import auto_evaluate, save_run_result, aggregate_runs, load_scenario, RESULTS_BASE

TELEGRAM_SLUG   = "telegram-gemma4-26b"
POLL_INTERVAL_S = 5     # segundos entre polls de getUpdates
TASK_TIMEOUT_S  = 600   # timeout máximo por tarefa


def _load_telegram():
    cfg = Path.home() / ".aurelia/config/app.json"
    try:
        d = json.loads(cfg.read_text())
        return d.get("telegram_bot_token", ""), d.get("telegram_allowed_user_ids", [])[0]
    except:
        raise RuntimeError("Credenciais Telegram não encontradas em ~/.aurelia/config/app.json")


TOKEN, CHAT_ID = _load_telegram()
BASE_URL = f"https://api.telegram.org/bot{TOKEN}"


def tg_request(method: str, params: dict = None) -> dict:
    url  = f"{BASE_URL}/{method}"
    data = urllib.parse.urlencode(params or {}).encode() if params else None
    req  = urllib.request.Request(url, data=data)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def send_message(text: str) -> int:
    """Envia mensagem para o chat do usuário. Retorna message_id."""
    resp = tg_request("sendMessage", {
        "chat_id":    CHAT_ID,
        "text":       text,
        "parse_mode": "Markdown"
    })
    return resp["result"]["message_id"]


def get_bot_response(after_message_id: int, timeout_s: int = TASK_TIMEOUT_S) -> str | None:
    """
    Aguarda a próxima mensagem do BOT (não do usuário) após after_message_id.
    Retorna o texto quando receber, ou None se timeout.
    """
    # Pegar o update_id atual para não processar mensagens antigas
    upd = tg_request("getUpdates", {"limit": 1, "timeout": 0})
    offset = 0
    updates = upd.get("result", [])
    if updates:
        offset = updates[-1]["update_id"] + 1

    deadline = time.time() + timeout_s
    print(f"  [tg] aguardando resposta do bot (timeout {timeout_s}s)...", end="", flush=True)

    while time.time() < deadline:
        resp    = tg_request("getUpdates", {"offset": offset, "limit": 10, "timeout": POLL_INTERVAL_S})
        updates = resp.get("result", [])

        for upd in updates:
            offset = upd["update_id"] + 1
            msg    = upd.get("message") or upd.get("edited_message")
            if not msg:
                continue

            # Mensagem do bot (from é o bot, não o usuário)
            sender = msg.get("from", {})
            if not sender.get("is_bot", False):
                continue

            # Deve ser no nosso chat
            if msg.get("chat", {}).get("id") != CHAT_ID:
                continue

            # Deve ser depois da nossa mensagem
            if msg.get("message_id", 0) <= after_message_id:
                continue

            text = msg.get("text") or msg.get("caption") or ""
            print(f" recebido ({len(text)} chars)")
            return text

        print(".", end="", flush=True)

    print(" TIMEOUT")
    return None


def run_telegram_agent(scenario_id: str, prompt: str, workdir: Path) -> dict:
    t_start       = time.time()
    error         = None
    response_text = ""

    print(f"\n  [telegram] chat_id={CHAT_ID}")

    # Passo 1: bind do workdir via /cwd
    print(f"  [telegram] enviando /cwd {workdir}...")
    cwd_msg_id = send_message(f"/cwd {workdir}")
    cwd_resp   = get_bot_response(cwd_msg_id, timeout_s=60)

    if not cwd_resp:
        error = "timeout aguardando confirmação do /cwd"
        print(f"  [telegram] ERRO: {error}")
    elif "✅" in cwd_resp or "fixado" in cwd_resp.lower():
        print(f"  [telegram] binding OK: {cwd_resp[:80]}")
    else:
        print(f"  [telegram] AVISO: resposta inesperada do /cwd: {cwd_resp[:80]}")

    # Passo 2: enviar a tarefa FORGE
    full_prompt = (
        f"FORGE BENCHMARK — Cenário {scenario_id}\n"
        f"Diretório de trabalho: `{workdir}`\n"
        f"Salve todos os arquivos neste caminho absoluto.\n\n"
        f"{prompt}"
    )

    print(f"  [telegram] enviando tarefa ({len(full_prompt)} chars)...")
    task_msg_id = send_message(full_prompt)

    response_text = get_bot_response(task_msg_id, timeout_s=TASK_TIMEOUT_S) or ""

    if not response_text:
        error = f"timeout após {TASK_TIMEOUT_S}s aguardando resposta da tarefa"
        print(f"  [telegram] ERRO: {error}")
    else:
        print(f"  [telegram] resposta: {response_text[:150]}...")

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
    }


def main():
    parser = argparse.ArgumentParser(description="FORGE — Telegram Provider")
    parser.add_argument("--scenario",  nargs="+")
    parser.add_argument("--all",       action="store_true")
    parser.add_argument("--runs",      type=int, default=1)
    parser.add_argument("--port-base", type=int, default=8500)
    parser.add_argument("--mock",      action="store_true")
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
    print(f"  FORGE — Telegram Provider (sessão real de produção)")
    print(f"  Chat ID  : {CHAT_ID}")
    print(f"  Cenários : {', '.join(scenario_ids)}")
    print(f"  Runs/cen.: {args.runs}")
    print(f"{'='*64}")

    for i, sid in enumerate(scenario_ids):
        print(f"\n{'─'*64}")
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

        if "aurelia_auto_checks" in scenario:
            scenario = dict(scenario, auto_checks=scenario["aurelia_auto_checks"])

        print(f"  [{sid}] {scenario['name']}")
        print(f"  workdir : {workdir}")

        run_summaries = []

        for run_idx in range(1, args.runs + 1):
            if args.runs > 1:
                print(f"\n  ── Run {run_idx}/{args.runs} ──")

            agent_result = run_telegram_agent(sid, prompt, workdir)
            auto_eval    = auto_evaluate(scenario, workdir, agent_result, TELEGRAM_SLUG)
            out_file     = save_run_result(sid, TELEGRAM_SLUG, run_idx, workdir,
                                           agent_result, auto_eval, scenario)

            run_summaries.append({**auto_eval, "error": agent_result["error"],
                                   "loop_exhausted": agent_result["loop_exhausted"]})

            print(f"\n  Auto score : {auto_eval['score']}/{auto_eval['max_score']} ({auto_eval['pct']}%)")
            for label, c in auto_eval["checks"].items():
                mark = "✓" if c["passed"] else "✗"
                print(f"    {mark} {label}: {c['detail']}")
            print(f"  Salvo em   : {out_file.name}")

            if run_idx < args.runs:
                time.sleep(30)

        if args.runs > 1:
            agg = aggregate_runs(run_summaries)
            print(f"\n  ── Agregado ({args.runs} runs) ──")
            print(f"  AUTO mean  : {agg['auto_pct_mean']}% ± {agg['auto_pct_std']}%")

    print(f"\n{'='*64}\n")


if __name__ == "__main__":
    main()
