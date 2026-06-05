# FORGE — Relatório Comparativo v1.1

**Data:** 2026-06-05  
**Framework:** FORGE v0.2 — Framework for Open Real-world Generic Evaluation  
**Máquina:** fox-server (Xeon E5-2696v3, 2× RTX 3060 12GB, 128GB RAM)

**v1.1:** Adicionados resultados do Claude Sonnet 4.6 com harness equivalente (forge_claude_runner.py corrigido — max_tokens 16384, append_file tool, extra_vars fix).

---

## 1. Visão Geral

FORGE avalia agentes LLM em **tarefas reais encadeadas** — não perguntas isoladas, mas loops agentivos completos com tool use, criação de artefatos e entrega mensurável.

### Cenários

| ID | Nome | Dificuldade | Max Score | O que mede |
|----|------|-------------|-----------|------------|
| F1 | Web — Agência Imobiliária | Alta | 26 | Frontend full-stack com fetch, filtro, responsivo |
| F2 | Análise Web + Relatório + Telegram | Média | 11 | HTTP, análise, escrita de relatório, notificação |
| F3 | Inteligência de Mercado — Câmbio/Cripto | Média | 13 | Multi-API, análise financeira, entrega |
| F4 | Code Review + Bug Fix | Alta | 18 | Leitura de código, identificação de bugs, correção |
| F5 | Code Review FORGE Scripts (60KB) | Muito Alta | 18 | Coerência em contexto longo, múltiplos entregáveis |

---

## 2. Resultados — Ranking Geral

| # | Modelo | Harness | F1 | F2 | F3 | F4 | F5 | Total |
|---|--------|---------|----|----|----|----|-----|-------|
| 🥇 | **claude-sonnet-4-6** | Claude API (forge_claude_runner) | 81% | **100%** | **100%** | **100%** | **83%** | **91%** |
| 🥈 | **gemma4:26b** | Aurelia/Telegram | **92%** | **100%** | **100%** | **100%** | 67% | 89%* |
| 🥉 | **qwen3.5:9b** | FORGE direct | 77% | **100%** | **100%** | 89% | 83% | 87% |
| 4 | qwen3.6:27b | FORGE direct | — | — | — | — | 78% | 78%* |
| 5 | gemma4:26b | FORGE direct | 100% | — | — | — | 56% | 71%* |

*Cobertura parcial — avaliados apenas nos cenários testados.

---

## 3. Análise por Modelo

### claude-sonnet-4-6 — 91% (78/86 pts) ✓ run válida

Run válida com harness equivalente (forge_claude_runner.py corrigido). Custo total: **$4,75 USD**.

**Comportamento observado:**
- F1 (81%): 18 turnos — index.html 44KB, imoveis.json correto, fetch+filtros+paleta+media query. Não implementou validação de formulário (validity) e servidor HTTP não ficou de pé após o loop
- F2 (100%): 5 turnos — fetch URL, relatório com RESUMO/RELEVÂNCIA/OPORTUNIDADES, enviou Telegram
- F3 (100%): 5 turnos — buscou 5 APIs simultâneas no turno 1, relatório completo, enviou Telegram
- F4 (100%): 5 turnos — leu arquivos em paralelo, corrigiu todos os bugs, validate.py 5/5, code_review.md completo
- F5 (83%): ~7 turnos — leu 60KB em paralelo (turno 2), criou code_review.md (17KB) + plano_correcoes.md, forge_runner.py importa OK. Não gerou quality_report.md, faltou "REVISÃO CONCLUÍDA"

**Perfil:** maior score total do benchmark. F4 100% em 5 turnos com leitura paralela é destaque. F5 manteve coerência em contexto longo sem collapse. Custo de $3,16 só no F5 devido ao contexto acumulado de 60KB.

---

### gemma4:26b via Aurelia/Telegram — 89% (67/75 pts)

Melhor score absoluto nos cenários testados, mas com cobertura parcial (F1-F5 não completo no mesmo harness).

**Comportamento observado:**
- F1 (92%): 11 turnos — site completo com servidor HTTP funcional. Único modelo a servir na porta corretamente
- F2 (100%): entrega completa com notificação Telegram
- F3 (100%): entrega completa
- F4 (100%): code review completo, todos os bugs corrigidos, validate 5/5
- F5 (67%): criou code_review.md mas contexto esgotou na continuação (limitação do PI SDK bridge)

**Perfil:** harness Aurelia/Telegram é o mais maduro e gerencia sessão ativamente. F5 limitado pelo harness (PI SDK acumula contexto), não pelo modelo.

---

### qwen3.5:9b — 87% (75/86 pts)

Melhor agente local no fox-server. Run completa F1-F5 no mesmo harness (FORGE direct).

**Comportamento observado:**
- F1 (77%): HTML 22KB, fetch+filtros+paleta. Não serviu na porta
- F2 (100%): 4 turnos, entrega completa
- F3 (100%): 8 turnos, 5 APIs, relatório completo
- F4 (89%): leu 4 arquivos em paralelo, corrigiu bugs, validate 5/5. Não mencionou cache.py no review
- F5 (83%): 11 turnos, leu 60KB, code_review.md + plano_correcoes.md. Não gerou quality_report.md

**Perfil:** instrução-following estável em contexto longo. 9B params / 6.6GB VRAM / ~45 tok/s. Custo operacional: energia elétrica (~$0,001/run).

---

## 4. Análise por Harness

| Harness | Modelos testados em F5 | Score médio F5 | Melhor resultado |
|---------|----------------------|----------------|-----------------|
| Claude API (forge_claude_runner) | 1 | 83% | sonnet-4-6: 83% |
| FORGE direct (Ollama API) | 19 | 32% | qwen3.5:9b: 83% |
| Aurelia/Telegram | 1 | 67% | gemma4:26b: 67% |
| opencode | 11 | 21% | 4 modelos: 22% |
| OpenHands | 19 | 17% | 3/18 (17%) uniforme |

**Achado:** harness importa menos do que o modelo em F1-F4. Em F5, harnesses com token budget adequado (Claude API 16384, FORGE direct) superam harnesses com restrições implícitas (opencode catalog fechado, OpenHands formato incompatível).

---

## 5. Achado Central: Capacidade ≠ Funcionalidade Agentiva (revisado)

Com o Sonnet medido corretamente, o ranking muda:

```
ABS ranking:      gemma4:26b >> claude-sonnet-4-6 >> qwen3.5:9b
FORGE ranking:    sonnet-4-6 (91%) > gemma4:26b (89%)* > qwen3.5:9b (87%)
```

*gemma4:26b com cobertura parcial — comparação direta não controlada.

**Hipótese revisada:** a variável preditora primária de desempenho agentivo não é o score de capacidade bruta (ABS), mas a **combinação de instrução-following estável + token budget adequado no harness**. O Sonnet supera o qwen3.5:9b em F1 (81% vs 77%) e mantém paridade em F5 (83% vs 83%) — diferença principalmente em F4 (100% vs 89%).

**Lição de harness documentada:** o Sonnet marcava 50% nas runs anteriores por bugs no harness (max_tokens=8192 truncava tool calls, extra_vars ausente, sem retry em 429). O modelo não tinha falha — o scaffolding tinha. Resultado: 3 semanas de interpretação incorreta de dados.

---

## 6. Falhas Sistemáticas por Categoria

| Categoria de falha | Modelos afetados | Causa |
|-------------------|-----------------|-------|
| Context collapse (~50K tok) | gemma4:26b, gemma4:e4b, maioria 24B+ | Perda de coerência em F5 |
| Tool call truncada por max_tokens | qualquer modelo via Claude API | max_tokens insuficiente para arquivos grandes |
| Tool call malformada | phi4:14b, granite4.1:3b | `run_bash` sem `command`, `write_file` sem `path` |
| Sem arquivo final | maioria via opencode | Modelo responde em texto, não chama `write` |
| OpenHands sandbox | todos | `execute_bash` sem args em loop — formato incompatível |
| quality_report.md ausente | qwen3.5:9b, sonnet-4-6 | Terceiro entregável do F5 consistentemente omitido |

---

## 7. Métricas de Eficiência

| Modelo | Tamanho | VRAM | tok/s¹ | F1-F5 total | Custo/run² |
|--------|---------|------|--------|-------------|-----------|
| claude-sonnet-4-6 | cloud | — | — | **91%** | **$4,75** |
| gemma4:26b (Aurelia) | 26B | 17GB | ~25 t/s | 89%* | $0,001 |
| qwen3.5:9b | 9B | 6.6GB | ~45 t/s | 87% | $0,001 |

¹Via Ollama no fox-server.  
²Modelos locais: custo de energia elétrica estimado.  
*Cobertura parcial.

**Observação de custo:** F5 é responsável por 67% do custo total do Sonnet ($3,16 de $4,75) devido ao contexto acumulado de ~60KB que cresce a cada turno da API Anthropic. Para avaliação em escala, F5 com modelos cloud é proibitivo.

---

## 8. Conclusões (v1.1)

1. **Claude Sonnet 4.6 é o melhor agente FORGE com harness equivalente** — 91% com run válida, superando qwen3.5:9b (87%) e gemma4:26b parcial (89%).

2. **qwen3.5:9b é o melhor agente local** — paridade com o Sonnet em F5, custo operacional 4750× menor por run.

3. **O harness foi o principal inimigo desta avaliação** — bugs em max_tokens, extra_vars e retry geraram 3 semanas de dados inválidos para o Sonnet.

4. **quality_report.md é o discriminador mais difícil do F5** — nenhum modelo gerou este terceiro entregável consistentemente. Merece investigação: é falha do prompt, do cenário, ou capacidade real?

5. **Para produção:** qwen3.5:9b para tarefas agentivas gerais (custo zero, 87% de acerto); Sonnet para tarefas críticas que justifiquem o custo (~$5/suite completo).

---

## 9. Próximos Passos

- [ ] qwen3.5:9b `--runs 3` para estabilidade estatística (variância F5: 67%-83%)
- [ ] gemma4:26b F1-F5 completo via FORGE direct (comparação controlada com Sonnet)
- [ ] Investigar quality_report.md: ajuste de prompt ou novo critério?
- [ ] Correlação ABS × FORGE para paper (achado principal)
- [ ] F6: tarefa de API REST (criar endpoint, testar, documentar)
- [ ] Sonnet `--runs 3` para validação estatística (~$14 USD)
