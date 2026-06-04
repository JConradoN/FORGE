"""
FORGE — Framework for Open Real-world Generic Evaluation
Runner principal: executa cenários com loop de tool use real via Ollama API.

Uso:
    python3 forge_runner.py <modelo> --scenario F1
    python3 forge_runner.py <modelo> --scenario F1 F2 F3
    python3 forge_runner.py <modelo> --all

Ferramentas disponíveis para o agente:
    run_bash(command)           — executa comando no shell
    write_file(path, content)   — escreve arquivo no workdir do modelo
    read_file(path)             — lê arquivo do workdir
    http_get(url)               — HTTP GET, retorna body
    http_post(url, body, headers) — HTTP POST
    send_claudio(message)       — envia mensagem pelo bot Telegram
"""

import argparse
import datetime
import json
import os
import subprocess
import sys
import time
import traceback
import urllib.request
import urllib.parse
from pathlib import Path

# ── Configuração ──────────────────────────────────────────────
OLLAMA_URL    = "http://localhost:11434/api/chat"
RESULTS_BASE  = Path(__file__).parent.parent / "results"
MAX_TURNS     = 20
TIMEOUT_S     = 300
TEMPERATURE   = 0

# Carregar token do Telegram a partir da config do Aurelia
def _load_telegram():
    cfg = Path.home() / ".aurelia/config/app.json"
    try:
        d = json.loads(cfg.read_text())
        return d.get("telegram_bot_token",""), d.get("telegram_allowed_user_ids",[])[0]
    except:
        return "", ""

TELEGRAM_TOKEN, TELEGRAM_CHAT_ID = _load_telegram()


# ── Definição das ferramentas ─────────────────────────────────
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "run_bash",
            "description": (
                "Executa um comando bash no servidor local e retorna o stdout. "
                "Use para criar diretórios, instalar pacotes, iniciar servidores, "
                "executar scripts, verificar portas, etc."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "Comando bash a executar."}
                },
                "required": ["command"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": (
                "Escreve conteúdo em um arquivo no diretório de trabalho do cenário. "
                "Use caminhos relativos (ex: 'index.html', 'subdir/app.py'). "
                "Cria diretórios intermediários automaticamente."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path":    {"type": "string", "description": "Caminho relativo do arquivo."},
                    "content": {"type": "string", "description": "Conteúdo a escrever."}
                },
                "required": ["path", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Lê o conteúdo de um arquivo no diretório de trabalho.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Caminho relativo do arquivo."}
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "http_get",
            "description": (
                "Faz uma requisição HTTP GET e retorna o body como texto. "
                "Use para buscar dados de APIs públicas, verificar páginas, etc."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "url":     {"type": "string", "description": "URL completa."},
                    "headers": {"type": "object", "description": "Headers opcionais.", "default": {}}
                },
                "required": ["url"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "http_post",
            "description": "Faz uma requisição HTTP POST com body JSON.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url":     {"type": "string"},
                    "body":    {"type": "object", "description": "Body JSON."},
                    "headers": {"type": "object", "default": {}}
                },
                "required": ["url", "body"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "send_claudio",
            "description": (
                "Envia uma mensagem de texto pelo bot Telegram do Claudio. "
                "Use para notificar o usuário sobre o resultado de uma tarefa."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "message": {"type": "string", "description": "Mensagem a enviar (suporta Markdown)."}
                },
                "required": ["message"]
            }
        }
    },
]


# ── Implementação das ferramentas ─────────────────────────────
def exec_run_bash(command: str, workdir: Path) -> str:
    try:
        result = subprocess.run(
            ["bash", "-c", command],
            capture_output=True, text=True,
            timeout=TIMEOUT_S, cwd=workdir
        )
        out = result.stdout
        if result.returncode != 0 and result.stderr:
            out += f"\n[STDERR] {result.stderr.strip()}"
        return out or "(sem output)"
    except subprocess.TimeoutExpired:
        return f"[ERRO] Timeout após {TIMEOUT_S}s"
    except Exception as e:
        return f"[ERRO] {e}"


def exec_write_file(path: str, content: str, workdir: Path) -> str:
    target = (workdir / path).resolve()
    # Segurança: não permite escrita fora do workdir
    if not str(target).startswith(str(workdir.resolve())):
        return "[ERRO] Caminho fora do diretório de trabalho."
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return f"Arquivo escrito: {path} ({len(content)} chars)"


def exec_read_file(path: str, workdir: Path) -> str:
    target = (workdir / path).resolve()
    if not str(target).startswith(str(workdir.resolve())):
        return "[ERRO] Caminho fora do diretório de trabalho."
    if not target.exists():
        return f"[ERRO] Arquivo não encontrado: {path}"
    return target.read_text(encoding="utf-8")


def exec_http_get(url: str, headers: dict) -> str:
    try:
        req = urllib.request.Request(url, headers=headers or {})
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.read().decode("utf-8", errors="replace")[:8000]
    except Exception as e:
        return f"[ERRO] {e}"


def exec_http_post(url: str, body: dict, headers: dict) -> str:
    try:
        data = json.dumps(body).encode()
        h = {"Content-Type": "application/json"}
        h.update(headers or {})
        req = urllib.request.Request(url, data=data, headers=h, method="POST")
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.read().decode("utf-8", errors="replace")[:4000]
    except Exception as e:
        return f"[ERRO] {e}"


def exec_send_claudio(message: str) -> str:
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return "[ERRO] Credenciais Telegram não disponíveis."
    try:
        data = urllib.parse.urlencode({
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "Markdown"
        }).encode()
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            data=data
        )
        with urllib.request.urlopen(req, timeout=15) as r:
            resp = json.loads(r.read())
            return f"Mensagem enviada. message_id={resp.get('result',{}).get('message_id','?')}"
    except Exception as e:
        return f"[ERRO] {e}"


def dispatch_tool(name: str, args: dict, workdir: Path) -> str:
    """Despacha chamada de ferramenta para a implementação correta."""
    if name == "run_bash":
        return exec_run_bash(args.get("command",""), workdir)
    if name == "write_file":
        return exec_write_file(args.get("path",""), args.get("content",""), workdir)
    if name == "read_file":
        return exec_read_file(args.get("path",""), workdir)
    if name == "http_get":
        return exec_http_get(args.get("url",""), args.get("headers",{}))
    if name == "http_post":
        return exec_http_post(args.get("url",""), args.get("body",{}), args.get("headers",{}))
    if name == "send_claudio":
        return exec_send_claudio(args.get("message",""))
    return f"[ERRO] Ferramenta desconhecida: {name}"


# ── Chamada à API Ollama ──────────────────────────────────────
def call_ollama(model: str, messages: list) -> dict:
    payload = {
        "model":    model,
        "messages": messages,
        "tools":    TOOLS,
        "stream":   False,
        "think":    False,
        "options":  {"temperature": TEMPERATURE}
    }
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        OLLAMA_URL,
        data=data,
        headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode()[:300]
        raise RuntimeError(f"HTTP {e.code}: {body}")
    except Exception as e:
        raise RuntimeError(str(e))


def extract_tool_calls(resp: dict) -> list:
    calls = []
    for tc in resp.get("message", {}).get("tool_calls", []):
        fn   = tc.get("function", {})
        name = fn.get("name", "")
        args = fn.get("arguments", {})
        if isinstance(args, str):
            try: args = json.loads(args)
            except: args = {"_raw": args}
        calls.append({"name": name, "arguments": args})
    return calls


# ── Loop principal do agente ──────────────────────────────────
def run_agent(model: str, scenario_id: str, prompt: str, workdir: Path) -> dict:
    """
    Executa o loop de agente para um cenário.
    Retorna dict com: turns, tool_calls, final_response, error, duration_ms, tok_total
    """
    messages = [{"role": "user", "content": prompt}]
    t_start  = time.time()

    turns         = 0
    tool_calls_log = []
    final_response = ""
    error          = None
    tok_total      = 0

    print(f"\n  [agente] iniciando loop (max {MAX_TURNS} turns)")

    while turns < MAX_TURNS:
        turns += 1
        print(f"  [turn {turns}] chamando API...", end=" ", flush=True)

        try:
            resp = call_ollama(model, messages)
        except RuntimeError as e:
            error = str(e)
            print(f"ERRO: {error}")
            break

        # Performance
        tok_total += resp.get("eval_count", 0) + resp.get("prompt_eval_count", 0)

        msg      = resp.get("message", {})
        content  = msg.get("content") or ""
        tc_list  = extract_tool_calls(resp)

        # Sem tool calls → resposta final
        if not tc_list:
            final_response = content
            print(f"resposta final ({len(content)} chars)")
            messages.append({"role": "assistant", "content": content})
            break

        print(f"{len(tc_list)} tool(s): {[t['name'] for t in tc_list]}")
        messages.append({"role": "assistant", "content": content, "tool_calls": resp["message"].get("tool_calls", [])})

        # Executar cada tool call
        for tc in tc_list:
            name = tc["name"]
            args = tc["arguments"]
            print(f"    → {name}({list(args.keys())})", end=" ... ", flush=True)
            result = dispatch_tool(name, args, workdir)
            print(f"({len(str(result))} chars)")

            tool_calls_log.append({
                "turn":   turns,
                "name":   name,
                "args":   {k: str(v)[:200] for k, v in args.items()},
                "result": str(result)[:500]
            })

            messages.append({
                "role":    "tool",
                "content": str(result)
            })
    else:
        print(f"  [agente] loop expirado após {MAX_TURNS} turns")

    duration_ms = int((time.time() - t_start) * 1000)
    return {
        "turns":          turns,
        "tool_calls":     tool_calls_log,
        "final_response": final_response,
        "error":          error,
        "duration_ms":    duration_ms,
        "tok_total":      tok_total,
        "loop_exhausted": turns >= MAX_TURNS and not final_response,
    }


# ── Carregamento de cenários ──────────────────────────────────
def load_scenario(scenario_id: str) -> dict:
    path = Path(__file__).parent.parent / "scenarios" / f"{scenario_id}.json"
    if not path.exists():
        raise FileNotFoundError(f"Cenário não encontrado: {path}")
    return json.loads(path.read_text())


# ── Avaliação automática ──────────────────────────────────────
def auto_evaluate(scenario: dict, workdir: Path, agent_result: dict) -> dict:
    """
    Executa os checks automáticos definidos no cenário.
    Retorna dict com scores e detalhes por critério.
    """
    checks = scenario.get("auto_checks", [])
    results = {}
    score   = 0
    max_score = 0

    for check in checks:
        ctype  = check["type"]
        label  = check["label"]
        weight = check.get("weight", 1)
        max_score += weight
        passed = False
        detail = ""

        if ctype == "file_exists":
            p = workdir / check["path"]
            passed = p.exists()
            detail = str(p)

        elif ctype == "file_contains":
            p = workdir / check["path"]
            if p.exists():
                content = p.read_text(errors="replace")
                needle  = check["needle"]
                passed  = needle.lower() in content.lower()
                detail  = f"buscando '{needle}' em {check['path']}"
            else:
                detail = f"arquivo não encontrado: {check['path']}"

        elif ctype == "http_ok":
            url = check["url"]
            try:
                with urllib.request.urlopen(url, timeout=10) as r:
                    passed  = r.status == 200
                    detail  = f"HTTP {r.status}"
            except Exception as e:
                detail = str(e)

        elif ctype == "tool_called":
            tool_name = check["tool"]
            passed = any(t["name"] == tool_name for t in agent_result["tool_calls"])
            detail = f"tool '{tool_name}' {'chamada' if passed else 'NÃO chamada'}"

        elif ctype == "response_contains":
            needle = check["needle"]
            passed = needle.lower() in agent_result["final_response"].lower()
            detail = f"buscando '{needle}' na resposta final"

        elif ctype == "no_error":
            passed = agent_result["error"] is None
            detail = agent_result["error"] or "sem erro"

        if passed:
            score += weight

        results[label] = {"passed": passed, "weight": weight, "detail": detail}

    return {
        "score":     score,
        "max_score": max_score,
        "pct":       round(score / max_score * 100) if max_score else 0,
        "checks":    results
    }


# ── Salvar resultado ──────────────────────────────────────────
def save_result(scenario_id: str, model: str, workdir: Path,
                agent_result: dict, auto_eval: dict, scenario: dict):
    slug     = model.replace(":", "-").replace("/", "_")
    ts       = datetime.datetime.now().strftime("%Y-%m-%d")
    out_dir  = RESULTS_BASE / scenario_id / slug
    out_dir.mkdir(parents=True, exist_ok=True)

    summary = {
        "scenario":       scenario_id,
        "scenario_name":  scenario.get("name", ""),
        "model":          model,
        "date":           ts,
        "turns":          agent_result["turns"],
        "tool_calls_n":   len(agent_result["tool_calls"]),
        "loop_exhausted": agent_result["loop_exhausted"],
        "error":          agent_result["error"],
        "duration_ms":    agent_result["duration_ms"],
        "tok_total":      agent_result["tok_total"],
        "tok_per_s":      round(agent_result["tok_total"] / (agent_result["duration_ms"]/1000), 1) if agent_result["duration_ms"] else None,
        "auto_score":     auto_eval["score"],
        "auto_max":       auto_eval["max_score"],
        "auto_pct":       auto_eval["pct"],
        "auto_checks":    auto_eval["checks"],
        "tool_calls_log": agent_result["tool_calls"],
        "final_response": agent_result["final_response"][:2000],
        # Campos para preenchimento posterior
        "llm_judge_score":   None,
        "claude_score":      None,
        "human_score":       None,
        "composite_score":   None,
        "notes":             ""
    }

    out_file = out_dir / f"{scenario_id}-{slug}-{ts}.json"
    out_file.write_text(json.dumps(summary, indent=2, ensure_ascii=False))
    return out_file


# ── Entry point ───────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="FORGE runner")
    parser.add_argument("model",      help="Nome do modelo Ollama (ex: gemma4:26b)")
    parser.add_argument("--scenario", nargs="+", help="Cenário(s) a executar (ex: F1 F2)")
    parser.add_argument("--all",      action="store_true", help="Executar todos os cenários disponíveis")
    parser.add_argument("--port-base",type=int, default=8200, help="Porta base para servidores web (default: 8200)")
    args = parser.parse_args()

    model = args.model
    slug  = model.replace(":", "-").replace("/", "_")

    # Determinar cenários
    if args.all:
        scenario_ids = [p.stem for p in sorted((Path(__file__).parent.parent / "scenarios").glob("*.json"))]
    elif args.scenario:
        scenario_ids = args.scenario
    else:
        parser.error("Especifique --scenario F1 ou --all")

    print(f"\n{'='*60}")
    print(f"  FORGE — Framework for Open Real-world Generic Evaluation")
    print(f"  Modelo   : {model}")
    print(f"  Cenários : {', '.join(scenario_ids)}")
    print(f"  Max turns: {MAX_TURNS}")
    print(f"{'='*60}")

    for i, sid in enumerate(scenario_ids):
        print(f"\n{'─'*60}")
        print(f"  [{sid}] carregando cenário...")
        try:
            scenario = load_scenario(sid)
        except FileNotFoundError as e:
            print(f"  ERRO: {e}")
            continue

        # Criar workdir isolado para este modelo+cenário
        workdir = RESULTS_BASE / sid / slug / "workdir"
        workdir.mkdir(parents=True, exist_ok=True)

        # Injetar variáveis no prompt
        port = args.port_base + i
        prompt = scenario["prompt"].format(
            model_slug=slug,
            port=port,
            workdir=str(workdir),
            **scenario.get("prompt_vars", {})
        )

        print(f"  [{sid}] {scenario['name']}")
        print(f"  workdir: {workdir}")
        print(f"  prompt:  {prompt[:120]}...")

        # Executar agente
        agent_result = run_agent(model, sid, prompt, workdir)

        # Avaliar automaticamente
        auto_eval = auto_evaluate(scenario, workdir, agent_result)

        # Salvar
        out = save_result(sid, model, workdir, agent_result, auto_eval, scenario)

        # Sumário
        print(f"\n  ── Resultado {sid} ──")
        print(f"  Turns         : {agent_result['turns']}")
        print(f"  Tool calls    : {len(agent_result['tool_calls'])}")
        print(f"  Loop expirado : {agent_result['loop_exhausted']}")
        print(f"  Erro          : {agent_result['error'] or 'nenhum'}")
        print(f"  Duração       : {agent_result['duration_ms']/1000:.1f}s")
        print(f"  Auto score    : {auto_eval['score']}/{auto_eval['max_score']} ({auto_eval['pct']}%)")
        for label, c in auto_eval["checks"].items():
            mark = "✓" if c["passed"] else "✗"
            print(f"    {mark} {label}: {c['detail']}")
        print(f"  Salvo em      : {out}")

    print(f"\n{'='*60}")
    print(f"  Pipeline concluído.")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
