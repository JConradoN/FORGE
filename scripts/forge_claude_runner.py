"""
FORGE — Claude Provider
Executa cenários FORGE usando a API Anthropic com as mesmas ferramentas
do forge_runner.py (run_bash, write_file, read_file, http_get, http_post, send_claudio).

Permite comparação direta entre modelos locais (Ollama) e Claude.

Uso:
    python3 forge_claude_runner.py claude-sonnet-4-6 --scenario F1 --runs 3
    python3 forge_claude_runner.py claude-opus-4-8 --all --mock
    python3 forge_claude_runner.py --list-models

Modelos suportados:
    claude-sonnet-4-6      (padrão — melhor custo/benefício)
    claude-opus-4-8        (máximo — mais caro)
    claude-haiku-4-5-20251001  (rápido — mais barato)
"""

import argparse
import datetime
import json
import os
import time
import random
from pathlib import Path

# Importar ferramentas e avaliação do runner principal
import sys
sys.path.insert(0, str(Path(__file__).parent))
from forge_runner import (
    dispatch_tool, auto_evaluate, save_run_result, aggregate_runs,
    load_scenario, RESULTS_BASE, MAX_TURNS, WALL_TIMEOUT_S, STUCK_WINDOW, HARNESS_VERSION,
    _kill_port, _extract_server_port,
    _check_bash_safety,
)

try:
    import anthropic
except ImportError:
    print("ERRO: anthropic SDK não instalado. Execute: pip install anthropic")
    sys.exit(1)

# ── Configuração ──────────────────────────────────────────────
DEFAULT_MODEL = "claude-sonnet-4-6"
MODELS = {
    "claude-sonnet-4-6":          "claude-sonnet-4-6",
    "claude-opus-4-8":            "claude-opus-4-8",
    "claude-haiku-4-5":           "claude-haiku-4-5-20251001",
    "claude-haiku-4-5-20251001":  "claude-haiku-4-5-20251001",
}

# Ferramentas no formato Anthropic (mapeamento das FORGE tools)
CLAUDE_TOOLS = [
    {
        "name": "run_bash",
        "description": (
            "Executa um comando bash no servidor local e retorna o stdout. "
            "Use para criar diretórios, executar scripts Python, iniciar servidores, "
            "verificar portas, rodar testes. Comandos destrutivos são bloqueados."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Comando bash a executar."}
            },
            "required": ["command"]
        }
    },
    {
        "name": "write_file",
        "description": (
            "Escreve conteúdo em um arquivo no diretório de trabalho do cenário. "
            "Use caminhos relativos. Cria diretórios intermediários automaticamente."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path":    {"type": "string"},
                "content": {"type": "string"}
            },
            "required": ["path", "content"]
        }
    },
    {
        "name": "read_file",
        "description": "Lê o conteúdo de um arquivo no diretório de trabalho.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"}
            },
            "required": ["path"]
        }
    },
    {
        "name": "http_get",
        "description": (
            "Faz HTTP GET e retorna o body como texto. "
            "HTML é convertido para texto limpo. Resposta limitada a 4000 chars."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "url":     {"type": "string"},
                "headers": {"type": "object"}
            },
            "required": ["url"]
        }
    },
    {
        "name": "http_post",
        "description": "Faz HTTP POST com body JSON.",
        "input_schema": {
            "type": "object",
            "properties": {
                "url":     {"type": "string"},
                "body":    {"type": "object"},
                "headers": {"type": "object"}
            },
            "required": ["url", "body"]
        }
    },
    {
        "name": "append_file",
        "description": (
            "Adiciona conteúdo ao final de um arquivo existente. "
            "Use quando o conteúdo for grande demais para um único write_file — "
            "escreva o arquivo em múltiplos chunks com write_file + append_file. "
            "Se o arquivo não existir, ele é criado."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path":    {"type": "string"},
                "content": {"type": "string"}
            },
            "required": ["path", "content"]
        }
    },
    {
        "name": "send_claudio",
        "description": "Envia mensagem pelo bot Telegram do Claudio.",
        "input_schema": {
            "type": "object",
            "properties": {
                "message": {"type": "string"}
            },
            "required": ["message"]
        }
    },
]


SYSTEM_PROMPT = (
    "Você é um agente de engenharia rodando em um servidor Linux. "
    "Ao usar a ferramenta write_file, SEMPRE inclua o conteúdo completo do arquivo "
    "no parâmetro 'content' da chamada da ferramenta — nunca no texto da resposta. "
    "Ao usar run_bash, SEMPRE inclua o comando no parâmetro 'command'. "
    "Não explique o que vai fazer antes de chamar a ferramenta — execute diretamente."
)


# ── Loop do agente Claude ─────────────────────────────────────
def run_claude_agent(model_id: str, scenario_id: str, prompt: str, workdir: Path,
                     scenario: dict | None = None,
                     read_max_chars: int | None = None) -> dict:
    api_key = os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_API_KEY_FOXDEV")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY ou ANTHROPIC_API_KEY_FOXDEV não definida.")

    client  = anthropic.Anthropic(api_key=api_key)
    messages = []
    t_start  = time.time()

    turns          = 0
    tool_calls_log = []
    final_response = ""
    error          = None
    tok_input      = 0
    tok_output     = 0
    cleanup_ports  = []

    wall_timeout = int((scenario or {}).get("wall_timeout_s", WALL_TIMEOUT_S))
    stuck_window = int((scenario or {}).get("stuck_window",   STUCK_WINDOW))

    print(f"\n  [claude] modelo={model_id} | wall_timeout={wall_timeout}s")

    stop_reason  = None
    recent_calls = []

    try:
        current_prompt = prompt

        while True:
            elapsed = time.time() - t_start
            if elapsed >= wall_timeout:
                stop_reason = "wall_timeout"
                print(f"\n  [claude] wall_timeout após {elapsed:.0f}s / {turns} turns")
                break

            turns += 1
            print(f"  [turn {turns}] chamando API Anthropic...", end=" ", flush=True)

            if not messages:
                messages = [{"role": "user", "content": current_prompt}]

            resp = None
            for attempt in range(5):
                try:
                    resp = client.messages.create(
                        model=model_id,
                        max_tokens=16384,
                        system=SYSTEM_PROMPT,
                        tools=CLAUDE_TOOLS,
                        messages=messages,
                    )
                    break
                except anthropic.RateLimitError:
                    wait = (2 ** attempt) * 10 + random.uniform(0, 5)
                    print(f"\n  [429] rate limit — aguardando {wait:.0f}s (tentativa {attempt+1}/5)...")
                    time.sleep(wait)
                except anthropic.APIError as e:
                    error = str(e)
                    print(f"ERRO API: {error}")
                    break
            else:
                error = "429 rate limit após 5 tentativas"
                print(f"  ABORTANDO: {error}")

            if resp is None:
                stop_reason = "api_error"
                break

            tok_input  += resp.usage.input_tokens
            tok_output += resp.usage.output_tokens

            text_parts = []
            tool_uses  = []

            for block in resp.content:
                if block.type == "text":
                    text_parts.append(block.text)
                elif block.type == "tool_use":
                    tool_uses.append(block)

            text_content = "\n".join(text_parts)

            if resp.stop_reason == "end_turn" and not tool_uses:
                final_response = text_content
                stop_reason    = "converged"
                print(f"resposta final ({len(final_response)} chars)")
                messages.append({"role": "assistant", "content": resp.content})
                break

            print(f"{len(tool_uses)} tool(s): {[t.name for t in tool_uses]}")
            messages.append({"role": "assistant", "content": resp.content})

            if resp.stop_reason == "max_tokens":
                print(f"  [WARN] stop_reason=max_tokens — considere usar append_file para conteúdo grande.")

            tool_results = []
            for tu in tool_uses:
                name = tu.name
                args = dict(tu.input)
                print(f"    → {name}({list(args.keys())})", end=" ... ", flush=True)

                result = dispatch_tool(name, args, workdir, cleanup_ports,
                                      read_max_chars=read_max_chars)
                print(f"({len(str(result))} chars)")

                tool_calls_log.append({
                    "turn":   turns,
                    "name":   name,
                    "args":   {k: str(v)[:200] for k, v in args.items()},
                    "result": str(result)[:500]
                })

                tool_results.append({
                    "type":        "tool_result",
                    "tool_use_id": tu.id,
                    "content":     str(result)
                })

                sig = f"{name}:{list(args.values())[0][:80] if args else ''}"
                recent_calls.append(sig)
                if len(recent_calls) > stuck_window:
                    recent_calls.pop(0)
                if len(recent_calls) == stuck_window and len(set(recent_calls)) == 1:
                    stop_reason = "stuck_loop"
                    error = f"Loop preso detectado: {stuck_window} chamadas idênticas a '{sig}'"
                    print(f"\n  [claude] STUCK: {error}")
                    break

            messages.append({"role": "user", "content": tool_results})

            if stop_reason == "stuck_loop":
                break

    finally:
        for port in cleanup_ports:
            print(f"  [cleanup] encerrando servidor na porta {port}")
            _kill_port(port)

    duration_ms = int((time.time() - t_start) * 1000)
    tok_total   = tok_input + tok_output

    return {
        "turns":          turns,
        "tool_calls":     tool_calls_log,
        "final_response": final_response,
        "error":          error,
        "duration_ms":    duration_ms,
        "tok_total":      tok_total,
        "tok_input":      tok_input,
        "tok_output":     tok_output,
        "stop_reason":    stop_reason,
        "loop_exhausted": stop_reason in ("wall_timeout", "stuck_loop"),
        "cleanup_ports":  cleanup_ports,
        "provider":       "anthropic",
    }


# ── Entry point ───────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="FORGE — Claude Provider")
    parser.add_argument("model", nargs="?", default=DEFAULT_MODEL,
                        help=f"Modelo Claude (default: {DEFAULT_MODEL})")
    parser.add_argument("--scenario",    nargs="+")
    parser.add_argument("--all",         action="store_true")
    parser.add_argument("--runs",        type=int, default=1)
    parser.add_argument("--port-base",   type=int, default=8300)
    parser.add_argument("--mock",        action="store_true")
    parser.add_argument("--list-models", action="store_true")
    args = parser.parse_args()

    if args.list_models:
        print("Modelos Claude disponíveis no FORGE:")
        for alias, model_id in MODELS.items():
            marker = " (default)" if alias == DEFAULT_MODEL else ""
            print(f"  {alias}{marker}")
        return

    model_alias = args.model
    model_id    = MODELS.get(model_alias, model_alias)
    slug        = f"claude-{model_alias.replace('claude-','').replace(':','-')}"

    if args.all:
        scenario_ids = [p.stem for p in sorted(
            (Path(__file__).parent.parent / "scenarios").glob("*.json")
        )]
    elif args.scenario:
        scenario_ids = args.scenario
    else:
        parser.error("Especifique --scenario F1 ou --all")

    print(f"\n{'='*64}")
    print(f"  FORGE — Claude Provider")
    print(f"  Modelo    : {model_id} (slug: {slug})")
    print(f"  Cenários  : {', '.join(scenario_ids)}")
    print(f"  Runs/cen. : {args.runs}")
    print(f"  Mock URLs : {'SIM (porta 9900)' if args.mock else 'NÃO'}")
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

        # Copiar fixtures e PRD (mesma lógica do Telegram runner)
        import shutil
        for fixture_rel in scenario.get("fixture_dirs", []):
            src = (Path(__file__).parent.parent / "scenarios") / fixture_rel
            dst = workdir / src.name
            if dst.exists():
                shutil.rmtree(dst)
            shutil.copytree(src, dst)
            print(f"  [fixture] copiado: {src.name}/")
        prd_rel = scenario.get("prd_file")
        if prd_rel:
            src = (Path(__file__).parent.parent / "scenarios") / prd_rel
            shutil.copy(src, workdir / "TASK.md")
            print(f"  [prd] copiado: {src.name} → TASK.md")

        prompt_vars = dict(scenario.get("prompt_vars", {}))
        if args.mock:
            mock_vars = scenario.get("prompt_vars_mock", {})
            prompt_vars.update(mock_vars)

        prompt = scenario["prompt"].format(
            model_slug=slug, port=port, workdir=str(workdir), **prompt_vars
        )

        print(f"  [{sid}] {scenario['name']}")
        print(f"  workdir : {workdir}")
        print(f"  prompt  : {prompt[:100]}...")

        run_summaries = []

        for run_idx in range(1, args.runs + 1):
            if args.runs > 1:
                print(f"\n  ── Run {run_idx}/{args.runs} ──")

            read_max = scenario.get("read_max_chars")
            agent_result = run_claude_agent(model_id, sid, prompt, workdir,
                                            scenario=scenario,
                                            read_max_chars=read_max)
            auto_eval    = auto_evaluate(scenario, workdir, agent_result, slug,
                                         extra_vars={"port": port})

            # Enriquecer com metadados do provider antes de salvar
            agent_result["model_display"] = model_id
            out_file = save_run_result(sid, model_id, run_idx, workdir,
                                       agent_result, auto_eval, scenario)

            run_summaries.append({**auto_eval, "error": agent_result["error"],
                                   "loop_exhausted": agent_result["loop_exhausted"]})

            cost_est = (agent_result["tok_input"] * 3 + agent_result["tok_output"] * 15) / 1_000_000
            print(f"\n  Auto score : {auto_eval['score']}/{auto_eval['max_score']} ({auto_eval['pct']}%)")
            print(f"  Tokens     : {agent_result['tok_input']} in + {agent_result['tok_output']} out")
            print(f"  Custo est. : ~${cost_est:.4f} USD (Sonnet pricing)")
            for label, c in auto_eval["checks"].items():
                mark = "✓" if c["passed"] else "✗"
                print(f"    {mark} {label}: {c['detail']}")
            print(f"  Salvo em   : {out_file.name}")

            if run_idx < args.runs:
                time.sleep(5)  # pausa menor — sem VRAM para limpar

        if args.runs > 1:
            agg = aggregate_runs(run_summaries)
            print(f"\n  ── Agregado ({args.runs} runs) ──")
            print(f"  AUTO mean  : {agg['auto_pct_mean']}% ± {agg['auto_pct_std']}%")

    print(f"\n{'='*64}\n")


if __name__ == "__main__":
    main()
