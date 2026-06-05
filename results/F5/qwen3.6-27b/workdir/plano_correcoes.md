# Plano de Correções — FORGE Scripts

## Priorização Geral

| Prioridade | Critério | Ação |
|------------|----------|------|
| **Alta** | Impacta comportamento, causa bugs ou risco de segurança | Implementar agora |
| **Média** | Degradação de qualidade, manutenção difícil, estimativas incorretas | Planejar para próximo sprint |
| **Baixa** | Estilo, convenções, melhorias menores, documentação | Registrar como backlog |

---

## 🔴 Alta Prioridade (9 problemas — implementar agora)

### 1. `forge_runner.py` — `_PROTECTED_FILES` referenciado antes da definição
- **ID:** FR-01
- **Arquivo:** `forge-scripts/forge_runner.py`
- **Descrição:** Mover definição de `_PROTECTED_FILES` para antes de `exec_run_bash()`
- **Esforço:** ~5 min
- **Risco:** Baixo — apenas reordenação de código

### 2. `forge_runner.py` — `run_command_ok` sem sanitização de segurança
- **ID:** FR-02
- **Arquivo:** `forge-scripts/forge_runner.py`
- **Descrição:** Aplicar `_check_bash_safety()` no check `run_command_ok` dentro de `auto_evaluate()`
- **Esforço:** ~10 min
- **Risco:** Baixo — adiciona proteção existente a um caminho não protegido

### 3. `forge_runner.py` — Divisão por zero em `tok_per_s`
- **ID:** FR-03
- **Arquivo:** `forge-scripts/forge_runner.py`
- **Descrição:** Extrair cálculo para função `_safe_tok_per_s()` com proteção explícita contra zero
- **Esforço:** ~10 min
- **Risco:** Baixo — adiciona guard clause

### 4. `forge_claude_runner.py` — `max_tokens=4096` insuficiente
- **ID:** FC-02
- **Arquivo:** `forge-scripts/forge_claude_runner.py`
- **Descrição:** Aumentar para 16384 tokens de saída
- **Esforço:** ~5 min
- **Risco:** Baixo — apenas aumenta limite; custo marginal

### 5. `forge_claude_runner.py` — Pricing hardcoded incorreto para Opus/Haiku
- **ID:** FC-03
- **Arquivo:** `forge-scripts/forge_claude_runner.py`
- **Descrição:** Dicionário de preços por modelo; usar preço correto baseado no model_id
- **Esforço:** ~15 min
- **Risco:** Baixo — cálculo isolado, não afeta funcionalidade

### 6. `forge_mock_server.py` — `import os` após uso em `start()`
- **ID:** FM-01
- **Arquivo:** `forge-scripts/forge_mock_server.py`
- **Descrição:** Mover `import os` para o topo do arquivo
- **Esforço:** ~2 min
- **Risco:** Nulo — apenas reordenação

### 7. `forge_mock_server.py` — `_load_market` sem tratamento de JSON inválido
- **ID:** FM-02
- **Arquivo:** `forge-scripts/forge_mock_server.py`
- **Descrição:** Envolver `json.loads()` em try/except, retornar `{}` com aviso
- **Esforço:** ~5 min
- **Risco:** Baixo — adiciona resiliência

### 8. `forge_telegram_runner.py` — Limpeza entre runs apaga fixtures
- **ID:** FT-01
- **Arquivo:** `forge-scripts/forge_telegram_runner.py`
- **Descrição:** Preservar seed_files durante limpeza entre runs, ou re-copiar fixtures
- **Esforço:** ~15 min
- **Risco:** Médio — alterar lógica de limpeza requer cuidado

### 9. `forge_telegram_runner.py` — `wait_for_workdir` pode estabilizar prematuramente
- **ID:** FT-02
- **Arquivo:** `forge-scripts/forge_telegram_runner.py`
- **Descrição:** Adicionar tempo mínimo absoluto de monitoramento após primeiro arquivo
- **Esforço:** ~10 min
- **Risco:** Baixo — adiciona constraint adicional

---

## 🟡 Média Prioridade (5 problemas — planejar)

### 10. `forge_runner.py` — Imports dentro do loop (`socket`, `hashlib`)
- **ID:** FR-04
- **Descrição:** Mover para topo do arquivo

### 11. `forge_runner.py` — `_resolve` definido dentro do loop de checks
- **ID:** FR-05
- **Descrição:** Extrair para função auxiliar fora do loop

### 12. `forge_claude_runner.py` — Validação de API key antes de criar client
- **ID:** FC-01
- **Descrição:** Validar e levantar erro imediatamente se ausente

### 13. `forge_mock_server.py` — PID file stale sem verificação proativa
- **ID:** FM-03
- **Descrição:** Verificar existência do processo antes de enviar SIGTERM

### 14. `forge_telegram_runner.py` — Warning quando `--response` ausente mas checks de texto existem
- **ID:** FT-03
- **Descrição:** Adicionar aviso no início do run

---

## 🟢 Baixa Prioridade (4 problemas — backlog)

### 15. `forge_runner.py` — Docstring com changelog inline sem versão formal
- **ID:** FR-06
- **Descrição:** Adicionar `__version__` e mover para CHANGELOG.md

### 16. `forge_claude_runner.py` — Importação via `sys.path.insert` frágil
- **ID:** FC-04
- **Descrição:** Converter para import relativo ou usar `importlib`

### 17. `forge_mock_server.py` — Logs HTTP completamente silenciados
- **ID:** FM-04
- **Descrição:** Adicionar flag `--verbose` para debug

### 18. `forge_telegram_runner.py` — Importação via `sys.path.insert` frágil
- **ID:** FT-04
- **Descrição:** Mesma correção de FC-04
