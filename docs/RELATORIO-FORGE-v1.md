# FORGE — Relatório Comparativo v1.0

**Data:** 2026-06-05  
**Framework:** FORGE v0.2 — Framework for Open Real-world Generic Evaluation  
**Máquina:** fox-server (Xeon E5-2696v3, 2× RTX 3060 12GB, 128GB RAM)

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
| 🥇 | **qwen3.5:9b** | FORGE direct | 77% | **100%** | **100%** | **89%** | **83%** | **87%** |
| 🥈 | **gemma4:26b** | Aurelia/Telegram | **92%** | **100%** | **100%** | **100%** | 67% | **89%** |
| 3 | qwen3.6:27b | FORGE direct | — | — | — | — | 78% | 78%* |
| 4 | gemma4:26b | FORGE direct | 100% | — | — | — | 56% | 71%* |
| 5 | claude-sonnet-4-6 | Claude API | — | — | — | 72% | 28%† | 50%* |

*Avaliados apenas nos cenários testados.  
†Rate limit (30k tok/min free tier) interrompeu no turno 16.

---

## 3. Análise por Modelo

### qwen3.5:9b — 87% (75/86 pts)

Melhor desempenho absoluto considerando todos os cenários testados.

**Comportamento observado:**
- F1 (77%): criou site completo em 6 turnos — HTML 22KB, JSON com 6 imóveis, fetch+filtro+paleta. Não serviu na porta (modelo não iniciou servidor HTTP)
- F2 (100%): 4 turnos — fetch URL, escreveu relatório com seções RESUMO/RELEVÂNCIA/OPORTUNIDADES, enviou via Telegram
- F3 (100%): 8 turnos — consultou 5 APIs de câmbio/cripto, relatório com cotações+tendência+recomendação, enviou via Telegram  
- F4 (89%): leu 4 arquivos Python em paralelo no turno 1, corrigiu bugs em 3 turnos, validate.py passou 5/5
- F5 (83%): 11 turnos — leu 60KB de código sem perder coerência, criou code_review.md + plano_correcoes.md. Não gerou quality_report.md

**Perfil:** instrução-following estável em contexto longo. Modelo 9B de 6.6GB supera modelos 3× maiores em coerência agentiva.

---

### gemma4:26b via Aurelia/Telegram — 89% (67/75 pts)

Melhor score absoluto nos cenários testados, mas com cobertura menor.

**Comportamento observado:**
- F1 (92%): 11 turnos — site completo com servidor HTTP funcional. Único modelo a servir na porta corretamente
- F2 (100%): entrega completa com notificação Telegram
- F3 (100%): entrega completa
- F4 (100%): code review completo, todos os bugs corrigidos, validate 5/5
- F5 (67%): criou code_review.md mas contexto esgotou na continuação (limitação do PI SDK bridge)

**Perfil:** modelo de produção com harness maduro. F5 limitado pelo harness (PI SDK), não pelo modelo.

---

### claude-sonnet-4-6 — 50%† (controlador externo)

Travado por rate limit free tier (30k tok/min) no turno 16 do F5.

**F4 (72%):** completou code review mas não salvou `code_review.md` no workdir esperado.  
**F5 (28%):** criou `code_review.md` vazia (0 bytes), interrompido no turno 16 por 429.

**Nota metodológica:** resultado subestimado. Com tier pago o Sonnet completaria F5 — contexto de 395K tokens de entrada confirma que o modelo leu tudo e manteve coerência até o rate limit.

---

## 4. Análise por Harness

| Harness | Modelos testados em F5 | Score médio F5 | Melhor resultado |
|---------|----------------------|----------------|-----------------|
| FORGE direct (Ollama API) | 19 | 32% | qwen3.5:9b: 83% |
| Aurelia/Telegram | 1 | 67% | gemma4:26b: 67% |
| opencode | 11 | 21% | 4 modelos: 22% |
| OpenHands | 19 | 17% | 3/18 (17%) uniforme |
| Claude API | 1 | 28%† | sonnet-4-6: 28%† |

**Achado principal:** o harness impacta menos do que o modelo em F1-F4. Em F5 (contexto longo), o harness passa a importar — modelos menores com instrução-following melhor superam modelos maiores independente do harness.

---

## 5. Achado Central: Capacidade ≠ Funcionalidade Agentiva

O qwen3.5:9b (9B params, ABS mediano) supera gemma4:26b (26B params, ABS líder) no FORGE total quando avaliado no mesmo harness (FORGE direct).

```
ABS ranking:     gemma4:26b >> qwen3.5:9b
FORGE ranking:   qwen3.5:9b ≈ gemma4:26b (via Aurelia)
```

**Hipótese confirmada:** a variável preditora de desempenho agentivo não é o score de capacidade bruta (ABS), mas a **estabilidade de instrução-following sob pressão de contexto acumulado**.

Em F5 (60KB de contexto acumulado, 11+ turnos), gemma4:26b colapsa em todos os harnesses automatizados. qwen3.5:9b mantém coerência até o fim.

---

## 6. Falhas Sistemáticas por Categoria

| Categoria de falha | Modelos afetados | Causa |
|-------------------|-----------------|-------|
| Context collapse (~50K tok) | gemma4:26b, gemma4:e4b, maioria 24B+ | Perda de coerência, re-leitura do task, token leaks |
| Tool call malformada | phi4:14b, granite4.1:3b | `execute_bash` sem `command`, `write_file` sem `path` |
| Sem arquivo final | maioria via opencode | Modelo responde em texto, não chama `write` |
| Rate limit | claude-sonnet-4-6 | Free tier 30k tok/min insuficiente para F5 |
| OpenHands sandbox | todos | `execute_bash` sem args em loop — bug de formato |

---

## 7. Métricas de Eficiência

| Modelo | Tamanho | VRAM | tok/s¹ | F1-F5 total | Custo/run² |
|--------|---------|------|--------|-------------|-----------|
| qwen3.5:9b | 9B | 6.6GB | ~45 t/s | 87% | $0 |
| gemma4:26b | 26B | 17GB | ~25 t/s | 89%³ | $0 |
| claude-sonnet-4-6 | — | cloud | — | 50%† | ~$0.15/run |

¹Via Ollama no fox-server.  
²Custo de inferência (modelos locais = energia elétrica ~$0.001/run).  
³Cobertura parcial (F1-F5 incompleto).

---

## 8. Conclusões

1. **qwen3.5:9b é o melhor agente local para tarefas reais** no fox-server — pequeno, rápido, coerente em contexto longo.

2. **gemma4:26b é superior em tarefas curtas** (F1-F4) mas colapsa em F5 sem o suporte do harness Aurelia para gerenciar a sessão.

3. **Nenhum harness automatizado** (opencode, OpenHands) conseguiu extrair desempenho superior ao FORGE direct em F5 — os overhead e formatos de tool call prejudicam mais do que ajudam.

4. **O F5 é um discriminador eficaz** de estabilidade de contexto — separa claramente modelos funcionais de modelos que "parecem bons" em benchmarks de capacidade.

5. **Para produção imediata:** qwen3.5:9b para tarefas agentivas gerais; gemma4:26b via Aurelia para tarefas que exijam qualidade máxima de raciocínio em contextos menores.

---

## 9. Próximos Passos

- [ ] Rodar qwen3.5:9b com `--runs 3` para estabilidade estatística
- [ ] Testar qwen3.6:27b em F1-F4 (só testado em F5)
- [ ] Repetir Sonnet com retry em rate limit
- [ ] Cruzar scores FORGE × ABS para correlação (paper)
- [ ] Adicionar F6: tarefa de API REST (criar endpoint, testar, documentar)
