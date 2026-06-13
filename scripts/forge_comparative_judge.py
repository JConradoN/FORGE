#!/usr/bin/env python3
"""
FORGE Comparative Judge — avalia todos os modelos de um cenário lado a lado.

Em vez de julgar cada relatório individualmente (sujeito a inflação de score
e rate limits), envia todos juntos para o Gemini e pede um ranking qualitativo.

Uso:
    python3 forge_comparative_judge.py F2 --model gemini-2.5-flash
    python3 forge_comparative_judge.py F3 --model gemini-2.5-flash
"""

import argparse
import json
import os
import time
import urllib.request
from pathlib import Path

FORGE_DIR   = Path(__file__).parent.parent
RESULTS_DIR = FORGE_DIR / "results"
SCENARIOS   = FORGE_DIR / "scenarios"

JUDGE_MODEL = "claude-sonnet-4-6"

COMPARATIVE_SYSTEM = """Você é um avaliador técnico rigoroso de agentes de IA.
Vai receber múltiplos relatórios produzidos por modelos diferentes para a MESMA tarefa.
Sua missão: ranqueá-los do melhor ao pior com análise qualitativa fundamentada.

Para cada modelo avalie:
- Qualidade do conteúdo (profundidade, precisão, utilidade)
- Clareza e estrutura do relatório
- Uso correto dos dados/fontes (para tarefas com dados externos: os números batem?)
- O que se destaca positivamente
- O que está faltando ou é fraco

Responda APENAS em JSON válido:
{
  "ranking": [
    {
      "posicao": 1,
      "modelo": "nome-do-modelo",
      "nota": 0-10,
      "pontos_fortes": "o que foi bom",
      "pontos_fracos": "o que faltou",
      "resumo": "uma frase objetiva"
    }
  ],
  "criterio_decisivo": "o principal fator que separou os melhores dos piores",
  "observacoes_gerais": "padrões observados no conjunto"
}"""


def _call_claude(prompt: str, model: str) -> str:
    try:
        import anthropic
    except ImportError:
        raise RuntimeError("anthropic SDK não instalado")
    api_key = (os.environ.get("ANTHROPIC_API_KEY")
               or os.environ.get("ANTHROPIC_API_KEY_FOXDEV"))
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY não definida")
    client = anthropic.Anthropic(api_key=api_key)
    resp = client.messages.create(
        model=model,
        max_tokens=4096,
        system=COMPARATIVE_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )
    return resp.content[0].text if resp.content else ""


def _call_gemini(prompt: str, model: str) -> str:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        # tenta carregar do .env.secrets
        secrets = Path.home() / ".env.secrets"
        if secrets.exists():
            for line in secrets.read_text().splitlines():
                if line.startswith("GEMINI_API_KEY="):
                    api_key = line.split("=", 1)[1].strip()
                    os.environ["GEMINI_API_KEY"] = api_key
                    break
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY não definida")

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    payload = {
        "systemInstruction": {"parts": [{"text": COMPARATIVE_SYSTEM}]},
        "contents":          [{"parts": [{"text": prompt}]}],
        "generationConfig":  {
            "temperature": 0,
            "maxOutputTokens": 4096,
            "thinkingConfig": {"thinkingBudget": 0},
        },
    }
    data = json.dumps(payload).encode()
    req  = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}
    )
    # Retry com backoff em 429
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                raw  = json.loads(r.read())
                text = raw["candidates"][0]["content"]["parts"][0]["text"]
                return text
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < 3:
                wait = 30 * (attempt + 1)
                print(f"  [judge] 429 — aguardando {wait}s antes de retry {attempt+2}/4...")
                time.sleep(wait)
            else:
                raise
    return ""


def _parse_json(text: str) -> dict | None:
    stripped = text.strip()
    # Remove markdown fences (```json ... ``` ou ``` ... ```)
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        # Remove primeira linha (```json ou ```)
        inner = lines[1:]
        # Remove última linha se for ```
        if inner and inner[-1].strip() == "```":
            inner = inner[:-1]
        stripped = "\n".join(inner).strip()
    # Tenta parse direto
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        pass
    # Fallback: extrai entre o primeiro { e último }
    start = stripped.find("{")
    end   = stripped.rfind("}") + 1
    if start >= 0 and end > start:
        try:
            return json.loads(stripped[start:end])
        except json.JSONDecodeError:
            pass
    return None


def collect_reports(scenario: str) -> list[dict]:
    """
    Coleta relatórios + metadados de todos os modelos para o cenário.
    Retorna lista de dicts: {model, slug, result_path, report_content, auto_score, tool_calls_http}
    """
    scenario_path = SCENARIOS / f"{scenario}.json"
    if not scenario_path.exists():
        raise FileNotFoundError(f"Cenário não encontrado: {scenario_path}")

    scenario_data = json.loads(scenario_path.read_text())
    required_files = [
        c["path"] for c in scenario_data.get("auto_checks", [])
        if c.get("type") == "file_exists" and c.get("weight", 0) > 0
    ]

    reports = []
    results_dir = RESULTS_DIR / scenario

    for model_dir in sorted(results_dir.iterdir()):
        if not model_dir.is_dir():
            continue
        json_files = sorted(
            [f for f in model_dir.glob("*.json") if "workdir" not in str(f)]
        )
        if not json_files:
            continue

        result_file = json_files[-1]
        data = json.loads(result_file.read_text())

        if data.get("judge_blocked_reason"):
            continue  # descarta incompletos

        model = data.get("model", model_dir.name)
        slug  = model.replace(":", "-").replace("/", "_")

        # Resolve paths com model_slug
        workdir = model_dir / "workdir"
        report_content = ""
        for req_path in required_files:
            resolved = req_path.format(model_slug=slug)
            fp = workdir / resolved
            if fp.exists():
                report_content += f"\n--- {resolved} ---\n"
                report_content += fp.read_text(encoding="utf-8", errors="replace")[:5000]

        if not report_content:
            continue

        # Dados brutos da API (para F3)
        tool_log   = data.get("tool_calls_log", [])
        http_calls = [t for t in tool_log if t.get("name") == "http_get"]
        api_data   = ""
        if http_calls:
            lines = []
            for t in http_calls[:5]:
                url = t.get("args", {}).get("url", "?")
                res = t.get("result", "")[:200]
                lines.append(f"  {url} → {res}")
            api_data = "\n".join(lines)

        reports.append({
            "model":         model,
            "slug":          slug,
            "result_path":   result_file,
            "report":        report_content,
            "api_data":      api_data,
            "auto_score":    data.get("auto_pct", 0),
            "auto_raw":      f"{data.get('auto_score')}/{data.get('auto_max')} ({data.get('auto_pct')}%)",
        })

    return reports


def build_prompt(scenario: str, reports: list[dict]) -> str:
    scenario_path = SCENARIOS / f"{scenario}.json"
    scenario_data = json.loads(scenario_path.read_text())
    task_name     = scenario_data.get("name", scenario)
    # Extrai o prompt sem variáveis de template
    task_prompt   = scenario_data.get("prompt", "")[:600]

    lines = [
        f"CENÁRIO: {scenario} — {task_name}",
        f"TAREFA (resumo): {task_prompt}",
        f"\nTotal de modelos a comparar: {len(reports)}",
        "\n" + "="*60,
    ]

    for i, r in enumerate(reports, 1):
        lines.append(f"\n### MODELO {i}: {r['model']} (auto_score: {r['auto_raw']})")
        if r["api_data"]:
            lines.append(f"[DADOS REAIS DA API]\n{r['api_data'][:400]}")
        lines.append(r["report"][:2500])
        lines.append("---")

    lines.append("\nRanqueie todos os modelos acima do melhor ao pior. Responda em JSON.")
    return "\n".join(lines)


def save_ranking_to_results(ranking: dict, reports: list[dict], scenario: str):
    """Salva o ranking comparativo em cada result JSON individual."""
    rank_by_model = {
        r["modelo"]: r for r in ranking.get("ranking", [])
    }

    for rep in reports:
        model = rep["model"]
        rank_entry = rank_by_model.get(model)
        if not rank_entry:
            # tenta pelo slug
            slug = rep["slug"]
            rank_entry = next(
                (v for k, v in rank_by_model.items()
                 if slug in k.replace(":", "-") or k in model),
                None
            )
        if not rank_entry:
            print(f"  [ranking] modelo não encontrado no ranking: {model}")
            continue

        data = json.loads(rep["result_path"].read_text())
        data["comparative_judge"] = {
            "scenario":          scenario,
            "judge_model":       JUDGE_MODEL,
            "posicao":           rank_entry.get("posicao"),
            "nota":              rank_entry.get("nota"),
            "pontos_fortes":     rank_entry.get("pontos_fortes"),
            "pontos_fracos":     rank_entry.get("pontos_fracos"),
            "resumo":            rank_entry.get("resumo"),
            "criterio_decisivo": ranking.get("criterio_decisivo"),
        }
        rep["result_path"].write_text(
            json.dumps(data, indent=2, ensure_ascii=False)
        )
        print(f"  #{rank_entry.get('posicao'):2d} nota={rank_entry.get('nota'):4.1f}  {model}")
        print(f"      + {rank_entry.get('pontos_fortes','')[:80]}")
        print(f"      - {rank_entry.get('pontos_fracos','')[:80]}")

    # Salva ranking geral em arquivo separado
    out = RESULTS_DIR / scenario / f"comparative_judge_{scenario}.json"
    out.write_text(json.dumps({
        "scenario":              scenario,
        "judge_model":           JUDGE_MODEL,
        "n_modelos":             len(reports),
        "ranking":               ranking.get("ranking", []),
        "criterio_decisivo":     ranking.get("criterio_decisivo"),
        "observacoes_gerais":    ranking.get("observacoes_gerais"),
    }, indent=2, ensure_ascii=False))
    print(f"\n  Ranking salvo: {out}")


def run_comparative_judge(scenario: str, model: str = JUDGE_MODEL):
    print(f"\nFORGE Comparative Judge — {scenario} com {model}")
    print("="*60)

    print(f"Coletando relatórios...")
    reports = collect_reports(scenario)
    print(f"Modelos elegíveis: {len(reports)}")
    for r in reports:
        print(f"  {r['model']} — auto: {r['auto_raw']}")

    if len(reports) < 2:
        print("Menos de 2 modelos — comparativo não faz sentido.")
        return

    print(f"\nConstruindo prompt comparativo...")
    prompt = build_prompt(scenario, reports)
    print(f"Prompt: {len(prompt)} chars | {len(reports)} modelos")

    print(f"\nChamando {model}...")
    if model.startswith("claude-"):
        raw = _call_claude(prompt, model)
    else:
        raw = _call_gemini(prompt, model)

    print(f"Resposta: {len(raw)} chars")
    ranking = _parse_json(raw)

    if not ranking:
        print("ERRO: não foi possível parsear o JSON da resposta")
        print("Raw:", raw[:500])
        return

    print(f"\nRanking recebido — {len(ranking.get('ranking',[]))} posições")
    print(f"Critério decisivo: {ranking.get('criterio_decisivo','?')}")
    print(f"Observações: {ranking.get('observacoes_gerais','?')[:120]}")
    print()

    save_ranking_to_results(ranking, reports, scenario)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("scenario", help="ID do cenário (ex: F2)")
    parser.add_argument("--model", default=JUDGE_MODEL)
    args = parser.parse_args()

    run_comparative_judge(args.scenario, args.model)


if __name__ == "__main__":
    main()
