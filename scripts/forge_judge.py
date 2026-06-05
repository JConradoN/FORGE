"""
FORGE Judge — avalia artefatos com LLM-judge e gera scores de qualidade.

Modos:
  Artefato específico (artifact_judge no cenário):
    Lê o arquivo do workdir + TASK.md, avalia por rubrica de qualidade.

  Resposta final (judge_rubric no cenário, legado):
    Avalia final_response + tool_calls_log.

Uso:
    python3 forge_judge.py results/F5/qwen3.5-9b/F5-qwen3.5-9b-2026-06-05-run1.json
    python3 forge_judge.py results/F5/           # avalia todos no diretório
    python3 forge_judge.py results/F5/ --model qwen3.5:9b
"""

import argparse
import json
import os
import urllib.request
from pathlib import Path

OLLAMA_URL  = "http://localhost:11434/api/chat"
JUDGE_MODEL = "gemma4:26b"   # modelo padrão do judge — fora da lista de modelos testados

JUDGE_SYSTEM = """Você é um avaliador técnico rigoroso de code reviews produzidos por agentes de IA.
Avalie objetivamente o artefato fornecido usando a rubrica dada.
Para cada critério, atribua uma nota inteira de 0 a 3:
  0 = ausente ou completamente inadequado
  1 = tentativa insatisfatória, lacunas sérias
  2 = satisfatório com falhas menores
  3 = excelente, critério plenamente atendido

Baseie a avaliação APENAS no conteúdo do artefato. Seja específico nas justificativas.
Responda APENAS com JSON válido, sem texto fora do JSON:
{
  "scores": {"criterio1": 0-3, "criterio2": 0-3, ...},
  "total": soma_dos_scores,
  "max": total_possivel,
  "pct": percentual_inteiro,
  "justificativas": {"criterio1": "uma frase objetiva", ...}
}"""


def _parse_judge_response(content: str, rubric: dict, max_score: int) -> dict | None:
    # Remove markdown code fences se presentes
    stripped = content.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        stripped = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    # Tenta parse direto primeiro, depois fallback por { }
    for candidate in [stripped, content]:
        start = candidate.find("{")
        end   = candidate.rfind("}") + 1
        if start >= 0 and end > start:
            try:
                result = json.loads(candidate[start:end])
                scores = result.get("scores", {})
                total  = sum(scores.values())
                result["total"] = total
                result["max"]   = max_score
                result["pct"]   = round(total / max_score * 100) if max_score else 0
                return result
            except json.JSONDecodeError:
                continue
    return None


def _call_judge_ollama(prompt: str, model: str) -> str:
    payload = {
        "model":    model,
        "messages": [
            {"role": "system", "content": JUDGE_SYSTEM},
            {"role": "user",   "content": prompt},
        ],
        "stream":  False,
        "think":   False,
        "options": {"temperature": 0},
    }
    data = json.dumps(payload).encode()
    req  = urllib.request.Request(
        OLLAMA_URL, data=data,
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=180) as r:
        raw = json.loads(r.read())
        return raw.get("message", {}).get("content", "")


def _call_judge_claude(prompt: str, model: str) -> str:
    try:
        import anthropic
    except ImportError:
        raise RuntimeError("anthropic SDK não instalado: pip install anthropic")
    api_key = os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_API_KEY_FOXDEV")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY não definida")
    client = anthropic.Anthropic(api_key=api_key)
    resp = client.messages.create(
        model=model,
        max_tokens=2048,
        system=JUDGE_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )
    return resp.content[0].text if resp.content else ""


def _call_judge_gemini(prompt: str, model: str) -> str:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY não definida")
    url     = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    payload = {
        "systemInstruction": {"parts": [{"text": JUDGE_SYSTEM}]},
        "contents":          [{"parts": [{"text": prompt}]}],
        "generationConfig":  {
            "temperature": 0,
            "maxOutputTokens": 2048,
            "thinkingConfig": {"thinkingBudget": 0},
        },
    }
    data = json.dumps(payload).encode()
    req  = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        raw = json.loads(r.read())
        return raw["candidates"][0]["content"]["parts"][0]["text"]


def call_judge(task_context: str, artifact_content: str,
               rubric: dict, model: str) -> dict | None:
    rubric_text = "\n".join(f"- {k} (0-3): {v}" for k, v in rubric.items())
    max_score   = len(rubric) * 3
    prompt = (
        f"CONTEXTO DA TAREFA (TASK.md):\n{task_context[:2000]}\n\n"
        f"ARTEFATO A AVALIAR:\n{artifact_content[:8000]}\n\n"
        f"RUBRICA (escala 0-3 por critério, total máximo {max_score}):\n"
        f"{rubric_text}\n\n"
        f"Avalie o artefato e responda em JSON."
    )
    try:
        if model.startswith("claude-"):
            content = _call_judge_claude(prompt, model)
        elif model.startswith("gemini-"):
            content = _call_judge_gemini(prompt, model)
        else:
            content = _call_judge_ollama(prompt, model)
        return _parse_judge_response(content, rubric, max_score)
    except Exception as e:
        print(f"  [judge] ERRO: {e}")
    return None


def evaluate_file(result_path: Path, model: str = JUDGE_MODEL):
    data = json.loads(result_path.read_text())

    scenario_id   = data.get("scenario", "")
    scenario_path = Path(__file__).parent.parent / "scenarios" / f"{scenario_id}.json"
    if not scenario_path.exists():
        print(f"  cenário não encontrado: {scenario_id}")
        return

    scenario = json.loads(scenario_path.read_text())

    # Determina workdir a partir do path do resultado
    workdir = result_path.parent / "workdir"

    # ── Avaliação de artefatos específicos ───────────────────────
    artifact_judge = scenario.get("artifact_judge", {})
    artifact_results = data.get("artifact_judge_scores", {})

    for artifact_name, spec in artifact_judge.items():
        if artifact_name in artifact_results:
            print(f"  [{artifact_name}] já avaliado — pulando")
            continue

        artifact_path = workdir / artifact_name
        if not artifact_path.exists():
            print(f"  [{artifact_name}] arquivo não encontrado no workdir — pulando")
            artifact_results[artifact_name] = {"error": "arquivo não encontrado"}
            continue

        # Contexto da tarefa (TASK.md se disponível)
        context_file = spec.get("context_file", "TASK.md")
        task_context = ""
        ctx_path = workdir / context_file
        if ctx_path.exists():
            task_context = ctx_path.read_text(encoding="utf-8")

        artifact_content = artifact_path.read_text(encoding="utf-8")
        rubric           = spec.get("rubric", {})

        print(f"  [{artifact_name}] avaliando com {model} "
              f"({len(artifact_content)} chars, {len(rubric)} critérios)...")

        result = call_judge(task_context, artifact_content, rubric, model)
        if result:
            artifact_results[artifact_name] = {
                "model":          model,
                "scores":         result["scores"],
                "total":          result["total"],
                "max":            result["max"],
                "pct":            result["pct"],
                "justificativas": result.get("justificativas", {}),
            }
            print(f"  [{artifact_name}] score: {result['total']}/{result['max']} "
                  f"({result['pct']}%) | {result['scores']}")
        else:
            artifact_results[artifact_name] = {"error": "judge falhou"}
            print(f"  [{artifact_name}] judge falhou")

    if artifact_results:
        data["artifact_judge_scores"] = artifact_results

    # ── Avaliação legada: final_response via judge_rubric ────────
    rubric_legacy = scenario.get("judge_rubric", {})
    if rubric_legacy and data.get("llm_judge_score") is None:
        print(f"  [legado] avaliando final_response com judge_rubric...")
        content = (data.get("final_response", "") + "\n\n"
                   + str(data.get("tool_calls_log", "")))
        result = call_judge("", content, rubric_legacy, model)
        if result:
            data["llm_judge_score"]          = result["pct"] / 100 * 4  # converter para 0-4
            data["llm_judge_scores"]         = result["scores"]
            data["llm_judge_justificativas"] = result.get("justificativas", {})
            data["llm_judge_model"]          = model

    result_path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    print(f"  salvo: {result_path.name}")


def main():
    parser = argparse.ArgumentParser(description="FORGE LLM-judge — avalia artefatos")
    parser.add_argument("target", help="Arquivo .json ou diretório de resultados")
    parser.add_argument("--model", default=JUDGE_MODEL,
                        help=f"Modelo Ollama para o judge (default: {JUDGE_MODEL})")
    args = parser.parse_args()

    target = Path(args.target)
    files  = sorted(target.rglob("*.json")) if target.is_dir() else [target]
    files  = [f for f in files if "workdir" not in str(f)]

    print(f"\nFORGE Judge — modelo: {args.model}")
    print(f"Arquivos: {len(files)}\n")

    for f in files:
        try:
            label = f.relative_to(Path(__file__).parent.parent)
        except ValueError:
            label = f
        print(f"→ {label}")
        evaluate_file(f, model=args.model)
        print()


if __name__ == "__main__":
    main()
