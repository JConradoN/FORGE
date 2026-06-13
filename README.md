# FORGE — Framework for Open Real-world Generic Evaluation

**Stage 3 of 4** in a progressive benchmark methodology for evaluating local LLMs on agentic tasks.

> `ABS` → `LOP` → **`FORGE`** → `REAL`

---

## What is FORGE?

FORGE evaluates LLM agents on **chained real-world tasks** — not isolated questions, but full agentic loops with tool use, artifact creation, and measurable delivery.

Each scenario requires the model to:
1. Receive a goal
2. Plan and call tools autonomously
3. Produce concrete artifacts (files, HTTP responses, reports, code fixes)
4. Be scored on the quality of what it delivered

This moves beyond "can it answer a question?" toward "can it do the job?"

---

## The Benchmark Hierarchy

| Stage | Repo | Focus | What it tests |
|-------|------|-------|---------------|
| **ABS** | `agent-benchmark-suite` | Capability baseline | Tool use, reasoning, structured output on isolated tasks |
| **LOP** | `LOP` | Local-only pressure | Same tasks, no internet, local-only tools |
| **FORGE** ← *this repo* | `FORGE` | Real-world chained tasks | Multi-step agentic loops with measurable deliverables |
| **REAL** | `REAL` | Production simulation | Browser automation, real test suites, SPA interaction |
| *(applied)* | `agent-FORGE` | Framework | Production multi-agent runtime built from benchmark learnings |

Each stage filters and refines the candidate set. FORGE accepted 7 models from LOP; REAL accepted 4 from FORGE. The progression reveals which models hold up under realistic workloads — and the accumulated findings across all 4 stages shaped the design of **agent-FORGE**.

---

## Scenarios (F1–F5)

| ID | Name | Difficulty | What it measures |
|----|------|------------|-----------------|
| **F1** | Real Estate Web App | High | Full-stack frontend — HTML/CSS/JS, fetch API, JSON filtering, responsive design |
| **F2** | Web Analysis + Report + Telegram | Medium | HTTP scraping, structured analysis, report writing, Telegram notification |
| **F3** | Market Intelligence — FX/Crypto | Medium | Multi-API orchestration, financial analysis, formatted delivery |
| **F4** | Code Review + Bug Fix | High | Code reading, bug identification, automated test validation |
| **F5** | Code Review at 60 KB context | Very High | Long-context coherence, multi-deliverable output without collapse |

---

## Scoring System

Each scenario is scored across four dimensions:

| Dimension | Weight | Evaluator | What it measures |
|-----------|--------|-----------|-----------------|
| **AUTO** | 30% | `forge_runner.py` | Objective criteria: file exists, server responds, function called, test passes |
| **LLM-JUDGE** | 30% | `gemma4:26b` via `forge_judge.py` | Output quality against a scenario-specific rubric |
| **CLAUDE** | 20% | Claude Code | Technical completeness, correctness, edge cases |
| **HUMAN** | 20% | Author | Aesthetics, usability, "would I use this in production?" |

**Composite score:**
```
composite = (auto_norm×0.30 + llm_judge×0.30 + claude×0.20 + human×0.20)
```

Scale: 0–4 (consistent with ABS and LOP for longitudinal comparison).

---

## Results

Benchmarked on **fox-server**: Xeon E5-2696v3 (18c/36t) · 128 GB ECC RAM · 2× RTX 3060 12 GB (24 GB VRAM total). No cloud. No external GPU.

| # | Model | Harness | F1 | F2 | F3 | F4 | F5 | Total |
|---|-------|---------|----|----|----|----|-----|-------|
| 🥇 | **claude-sonnet-4-6** | Claude API | 81% | 100% | 100% | 100% | 83% | **91%** |
| 🥈 | **gemma4:26b** | Aurelia/Telegram | 92% | 100% | 100% | 100% | 67% | **89%**† |
| 🥉 | **qwen3.5:9b** | FORGE direct | 77% | 100% | 100% | 89% | 83% | **87%** |
| 4 | qwen3.6:27b | FORGE direct | — | — | — | — | 78% | 78%† |
| 5 | gemma4:26b | FORGE direct | 100% | — | — | — | 56% | 71%† |

†Partial coverage — evaluated only on completed scenarios.

**Key findings:**

- `claude-sonnet-4-6` achieved 91% with a validated equivalent harness. F4 (Code Review) completed in 5 turns with parallel file reads — a standout result.
- `gemma4:26b` reached 89% via the Aurelia/Telegram harness. Best absolute scores on tested scenarios.
- `qwen3.5:9b` (fully local, 9B parameters) reached 87% — comparable to 26B models on this task set.
- F5 (60 KB context) was the discriminating scenario: models that degraded here showed long-context collapse under realistic pressure.

---

## Repository Structure

```
forge/
├── scenarios/          # Scenario definitions (F1.json – F5.json)
│   ├── fixtures/       # Static test fixtures
│   └── prds/           # Product requirements docs used in F1/F4/F5
├── docs/
│   ├── SCORING.md      # Scoring rubric by dimension and scenario
│   ├── FORGE-CRITIQUE-v0.1.md
│   └── RELATORIO-FORGE-v1.md  # Full results report
├── results/            # Run outputs by scenario (F1/ – F5/)
├── scripts/            # Utilities
├── forge_pipeline.py   # Core evaluation pipeline
├── run_f*.sh           # Batch runners per scenario
└── logs/               # Execution logs
```

---

## What Came After FORGE

FORGE's findings fed directly into **REAL** (Stage 4) — a stricter evaluation using browser automation, real test suites, and SPA interaction, eliminating another round of models.

After REAL, the accumulated learnings from all 4 stages shaped the design of **[agent-FORGE](https://github.com/JConradoN/agent-FORGE)** — a production multi-agent framework. Its core architectural choices trace directly to benchmark observations:

1. **The runtime matters as much as the model.** Prompt construction, tool schemas, loop control, and reflection rounds explained more score variance than model size. → agent-FORGE implements spec-first YAML agents with active guardrails and autonomous reflection.
2. **Local models are viable for production.** `qwen3.5:9b` at 87% on tasks requiring web scraping, code review, multi-API orchestration, and report writing — entirely on consumer hardware. → agent-FORGE defaults to local-first Ollama with no cloud dependency.
3. **Memory is the missing layer.** Agents that couldn't refer back to prior context degraded across multi-step tasks. → agent-FORGE ships a 3-tier memory system (SQLite · Qdrant/mem0 · Kuzu graph).

---

## Related

- **[agent-FORGE](https://github.com/JConradoN/agent-FORGE)** — the framework that emerged from this research
- **KDMILE 2026** — paper submitted to the Brazilian Symposium on Knowledge Discovery and Intelligent Systems
- **[Conrado Nogueira](https://github.com/JConradoN/Conrado-Nogueira)** — full profile and project index

---

*Benchmarked 2026-06-05. Hardware: fox-server (second-hand Xeon + dual RTX 3060). All inference local, no cloud.*
