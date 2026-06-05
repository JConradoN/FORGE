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
from pathlib import Path

# Importar ferramentas e avaliação do runner principal
import sys
sys.path.insert(0, str(Path(__file__).parent))
from forge_runner import (
    dispatch_tool, auto_evaluate, save_run_result, aggregate_runs,
    load_scenario, RESULTS_BASE, MAX_TURNS, _kill_port, _extract_server_port,
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


# ── Loop do agente Claude ─────────────────────────────────────
def run_claude_agent(model_id: str, scenario_id: str, prompt: str, workdir: Path) -> dict:
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

    print(f"\n  [claude] modelo={model_id} | max_turns={MAX_TURNS}")

    try:
        current_prompt = prompt

        while turns < MAX_TURNS:
            turns += 1
            print(f"  [turn {turns}] chamando API Anthropic...", end=" ", flush=True)

            # Construir mensagens no formato Anthropic
            if not messages:
                messages = [{"role": "user", "content": current_prompt}]

            try:
                resp = client.messages.create(
                    model=model_id,
                    max_tokens=4096,
                    tools=CLAUDE_TOOLS,
                    messages=messages,
                )
            except anthropic.APIError as e:
                error = str(e)
                print(f"ERRO API: {error}")
                break

            tok_input  += resp.usage.input_tokens
            tok_output += resp.usage.output_tokens

            # Processar conteúdo da resposta
            text_parts  = []
            tool_uses   = []

            if not hasattr(resp, "content") or not resp.content:
                pass
            else:
                for block in resp.content:
                if block.type == "text":
                    text_parts.append(block.text)
                elif block.type == "tool_use":
                    tool_uses.append(block)

            text_content = "\n".join(text_parts)

            if resp.stop_reason == "end_turn" and not tool_uses:
                final_response = text_content
                print(f"resposta final ({len(final_response)} chars)")
                messages.append({"role": "assistant", "content": resp.content})
                break

            print(f"{len(tool_uses)} tool(s): {[t.name for t in tool_uses]}")
            messages.append({"role": "assistant", "content": resp.content})

            # Executar ferramentas e coletar resultados
            tool_results = []
            for tu in tool_uses:
                name = tu.name
                args = dict(tu.input)
                print(f"    → {name}({list(args.keys())})", end=" ... ", flush=True)

                result = dispatch_tool(name, args, workdir, cleanup_ports)
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

            messages.append({"role": "user", "content": tool_results})
        else:
            print(f"  [claude] loop expirado após {MAX_TURNS} turns")

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
        "loop_exhausted": turns >= MAX_TURNS and not final_response,
        "cleanup_ports":  cleanup_ports,
        # Claude não tem tok/s no mesmo sentido — registrar latência
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

            agent_result = run_claude_agent(model_id, sid, prompt, workdir)
            auto_eval    = auto_evaluate(scenario, workdir, agent_result, slug)

            # Enriquecer com metadados do provider antes de salvar
            agent_result["model_display"] = model_id
            out_file = save_run_result(sid, model_id, run_idx, workdir,
                                       agent_result, auto_eval, scenario)

            run_summaries.append({**auto_eval, "error": agent_result["error"],
                                   "loop_exhausted": agent_result["loop_exhausted"]})

            # Using Sonnet pricing as baseline
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
