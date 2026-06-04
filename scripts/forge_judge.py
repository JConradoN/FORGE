"""
FORGE Judge — avalia resultados com gemma4:26b (LLM-judge) e gera placeholder para Claude.

Uso:
    python3 forge_judge.py results/F1/gemma4-26b/F1-gemma4-26b-2026-06-04.json
    python3 forge_judge.py results/F1/          # avalia todos no diretório
"""

import argparse
import json
import urllib.request
import urllib.error
from pathlib import Path

OLLAMA_URL   = "http://localhost:11434/api/chat"
JUDGE_MODEL  = "gemma4:26b"

JUDGE_SYSTEM = """Você é um avaliador técnico rigoroso de agentes de IA.
Avalie a qualidade do trabalho realizado pelo agente seguindo a rubrica fornecida.
Para cada critério, atribua uma nota de 0 a 4:
  0 = não realizou / completamente errado
  1 = tentou mas falhou na maior parte
  2 = parcialmente correto, falhas significativas
  3 = bom, falhas menores
  4 = excelente, completo e correto

Seja objetivo e específico. Baseie sua avaliação apenas no que está presente no output do agente.
Responda APENAS com um JSON válido no formato:
{
  "scores": {"criterio1": nota, "criterio2": nota, ...},
  "avg": media_calculada,
  "justificativas": {"criterio1": "texto curto", ...}
}"""


def call_judge(content: str, rubric: dict) -> dict | None:
    rubric_text = "\n".join(f"- {k}: {v}" for k, v in rubric.items())
    prompt = f"""Avalie o seguinte output de um agente de IA.

RUBRICA DE AVALIAÇÃO:
{rubric_text}

OUTPUT DO AGENTE (resposta final):
{content[:3000]}

Atribua notas 0-4 para cada critério da rubrica e calcule a média."""

    payload = {
        "model":   JUDGE_MODEL,
        "messages": [
            {"role": "system",  "content": JUDGE_SYSTEM},
            {"role": "user",    "content": prompt}
        ],
        "stream":  False,
        "think":   False,
        "options": {"temperature": 0}
    }
    try:
        data = json.dumps(payload).encode()
        req  = urllib.request.Request(OLLAMA_URL, data=data,
                                       headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=120) as r:
            resp    = json.loads(r.read())
            content = resp.get("message", {}).get("content", "")
            # Extrair JSON da resposta
            start = content.find("{")
            end   = content.rfind("}") + 1
            if start >= 0 and end > start:
                return json.loads(content[start:end])
    except Exception as e:
        print(f"  [judge] ERRO: {e}")
    return None


def evaluate_file(path: Path):
    data = json.loads(path.read_text())

    if data.get("llm_judge_score") is not None:
        print(f"  já avaliado: {path.name}")
        return

    scenario_id = data.get("scenario", "")
    scenario_path = Path(__file__).parent.parent / "scenarios" / f"{scenario_id}.json"
    if not scenario_path.exists():
        print(f"  cenário não encontrado: {scenario_id}")
        return

    scenario = json.loads(scenario_path.read_text())
    rubric   = scenario.get("judge_rubric", {})

    if not rubric:
        print(f"  sem rubrica definida para {scenario_id}")
        return

    print(f"  avaliando {path.name} com {JUDGE_MODEL}...")
    content = data.get("final_response", "") + "\n\n" + str(data.get("tool_calls_log", ""))
    result  = call_judge(content, rubric)

    if result:
        scores = result.get("scores", {})
        avg    = result.get("avg") or (sum(scores.values()) / len(scores) if scores else None)
        data["llm_judge_score"]       = round(avg, 2) if avg else None
        data["llm_judge_scores"]      = scores
        data["llm_judge_justificativas"] = result.get("justificativas", {})
        data["llm_judge_model"]       = JUDGE_MODEL
        print(f"  LLM-judge score: {data['llm_judge_score']} | {scores}")
    else:
        print(f"  LLM-judge falhou — score não atribuído")

    # Placeholder Claude score (para preenchimento manual ou via Claude)
    if data.get("claude_score") is None:
        data["claude_score"] = None
        data["claude_notes"] = "(pendente — executar forge_claude_eval.py)"

    # Calcular composite se tiver todos os scores
    scores_avail = [
        v for v in [
            data.get("llm_judge_score"),
            data.get("claude_score"),
            data.get("human_score")
        ] if v is not None
    ]
    if scores_avail:
        # Pesos: auto=30%, llm_judge=30%, claude=20%, human=20%
        auto_pct = data.get("auto_pct", 0) / 100 * 4  # converter % para 0-4
        weights  = []
        vals     = []
        vals.append(auto_pct);                      weights.append(0.30)
        if data.get("llm_judge_score") is not None:
            vals.append(data["llm_judge_score"]);   weights.append(0.30)
        if data.get("claude_score") is not None:
            vals.append(data["claude_score"]);      weights.append(0.20)
        if data.get("human_score") is not None:
            vals.append(data["human_score"]);       weights.append(0.20)
        total_w = sum(weights)
        composite = sum(v * w for v, w in zip(vals, weights)) / total_w
        data["composite_score"] = round(composite, 2)

    path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    print(f"  salvo: {path}")


def main():
    parser = argparse.ArgumentParser(description="FORGE LLM-judge evaluator")
    parser.add_argument("target", help="Arquivo .json ou diretório de resultados")
    args = parser.parse_args()

    target = Path(args.target)
    if target.is_dir():
        files = sorted(target.rglob("*.json"))
    else:
        files = [target]

    for f in files:
        evaluate_file(f)


if __name__ == "__main__":
    main()
