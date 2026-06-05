# Plano de Correções — FORGE Scripts

## Prioridade ALTA (implementar agora)

| # | Arquivo | Problema | Categoria | Esforço |
|---|---------|----------|-----------|---------|
| 1 | `forge_runner.py` | `_PROTECTED_FILES` referenciado antes da definição | Robustez/Bug | Trivial |
| 2 | `forge_runner.py` | `run_command_ok` executa shell sem sanitização | Segurança | Baixo |
| 9 | `forge_claude_runner.py` | API Key lida sem validação de formato | Segurança | Trivial |
| 13 | `forge_mock_server.py` | `import os` no meio do arquivo | Qualidade/Bug | Trivial |
| 16 | `forge_telegram_runner.py` | Limpeza de workdir entre runs incompleta | Robustez/Bug | Baixo |

## Prioridade MÉDIA (backlog)

| # | Arquivo | Problema | Categoria | Esforço |
|---|---------|----------|-----------|---------|
| 3 | `forge_runner.py` | Imports dentro do loop em `auto_evaluate` | Performance | Baixo |
| 4 | `forge_runner.py` | `call_ollama` sem validação de URL base | Robustez | Médio |
| 5 | `forge_runner.py` | `aggregate_runs` crash com lista vazia | Robustez | Trivial |
| 10 | `forge_claude_runner.py` | Custo estimado hardcoded para Sonnet | Qualidade | Médio |
| 12 | `forge_claude_runner.py` | Descrições de tools duplicadas | Manutenção | Médio |
| 14 | `forge_mock_server.py` | PID_FILE pode ficar stale | Robustez | Baixo |
| 17 | `forge_telegram_runner.py` | Fallback 20s insuficiente sem TTY | Robustez | Baixo |
| 18 | `forge_telegram_runner.py` | Snapshots com caminhos absolutos | Qualidade | Baixo |

## Prioridade BAIXA (nice-to-have)

| # | Arquivo | Problema | Categoria | Esforço |
|---|---------|----------|-----------|---------|
| 6 | `forge_runner.py` | Divisão por zero em `tok_per_s` | Robustez | Trivial |
| 7 | `forge_runner.py` | `_HTMLTextExtractor` tags auto-fechadas | Qualidade | Baixo |
| 8 | `forge_runner.py` | Docstring mistura changelog com API docs | Qualidade | Baixo |
| 11 | `forge_claude_runner.py` | `sys.path.insert` com string | Estilo | Trivial |
| 15 | `forge_mock_server.py` | `_load_market` retorna {} silenciosamente | Robustez | Baixo |
| 19 | `forge_telegram_runner.py` | Chave `aurelia_auto_checks` hardcoded | Qualidade | Baixo |
| 20 | `forge_telegram_runner.py` | `response_override` vazio sem warning | Robustez | Baixo |

---

## Ordem de Implementação (Alta Prioridade)

1. **Problema 13** — Mover `import os` para o topo em `forge_mock_server.py`
2. **Problema 1** — Mover `_PROTECTED_FILES` antes de `exec_run_bash` em `forge_runner.py`
3. **Problema 9** — Validar API Key em `forge_claude_runner.py`
4. **Problema 2** — Sanitizar comandos em `run_command_ok` em `forge_runner.py`
5. **Problema 16** — Corrigir limpeza de workdir em `forge_telegram_runner.py`
