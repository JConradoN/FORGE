# Plano de Correções — FORGE Scripts

## Visão Geral
- **Total de problemas identificados:** 12 (3 por arquivo)
- **Alta prioridade:** 6 → implementar imediatamente
- **Média prioridade:** 4 → planejar para próximo sprint
- **Baixa prioridade:** 2 → registrar como melhorias futuras

---

## Alta Prioridade — Implementar Agora ⚠️

### forge_runner.py (3 problemas)

| # | Problema | Impacto | Correção | Linhas afetadas |
|---|----------|---------|----------|-----------------|
| 1 | `_PROTECTED_FILES` definido após uso | Crash imediato ao rodar runner, cenários F2/F3 falham | Mover definição para topo do arquivo (após imports) | 203 → ~56 |
| 2 | Falta tratamento de erro em `exec_http_get` com HTML inválido | Perda de dados importantes na resposta LLM | Adicionar logging e fallback mais robusto no parser HTML | 195-203, 247 |
| 3 | Timeout fixo sem retry automático em `call_ollama` | Abortos completos por falhas transitórias | Implementar retry com backoff exponencial (max 3 retries) | 407-421 |

### forge_claude_runner.py (3 problemas)

| # | Problema | Impacto | Correção | Linhas afetadas |
|---|----------|---------|----------|-----------------|
| 1 | `CLAUDE_TOOLS` não valida tipos de input antes de dispatch | Comportamento inconsistente entre modelos LLM | Adicionar validação básica em `dispatch_tool` (ex: command deve ser string) | 95, ~203 |
| 2 | Mensagens de erro de bloqueio não tratadas como erros no log | Resultados falsos positivos nos cenários F1-F3 | Tratar mensagens com "[BLOQUEADO]" explicitamente e marcar como error | 95-103 |
| 3 | Variáveis não inicializadas para fallbacks de API response | Crash ao usar versões diferentes da API Anthropic | Inicializar todas variáveis no topo + tratamento de estrutura inesperada | 78-90, ~120 |

### forge_mock_server.py (1 problema)

| # | Problema | Impacto | Correção | Linhas afetadas |
|---|----------|---------|----------|-----------------|
| 1 | Falta import `os` usado em função stop() mas não declarado | Comando --stop falha imediatamente, processo zumbi rodando | Mover `import os` para topo do arquivo e remover inline redundante | ~54 → topo |

### forge_telegram_runner.py (2 problemas)

| # | Problema | Impacto | Correção | Linhas afetadas |
|---|----------|---------|----------|-----------------|
| 1 | Falta import `signal` usado em função stop() mas não declarado | Comando --stop falha com NameError, processo zumbi rodando | Adicionar `import signal` no topo do arquivo junto com outros imports | ~54 → topo |
| 2 | `_await_enter()` pode travar indefinidamente sem feedback claro | Runner fica bloqueado em sistemas headless consumindo recursos | Adicionar timeout reduzido (10s) e logging de status durante espera | 103-114, ~68 |

---

## Média Prioridade — Planejar para Próximo Sprint 📋

### forge_runner.py (2 problemas)

| # | Problema | Impacto | Correção | Linhas afetadas |
|---|----------|---------|----------|-----------------|
| 1 | Falta tratamento de erro em `exec_http_get` com HTML inválido | Perda de dados importantes na resposta LLM | Adicionar logging e fallback mais robusto no parser HTML | 195-203, 247 |
| 2 | Timeout fixo sem retry automático em `call_ollama` | Abortos completos por falhas transitórias | Implementar retry com backoff exponencial (max 3 retries) | 407-421 |

### forge_claude_runner.py (1 problema)

| # | Problema | Impacto | Correção | Linhas afetadas |
|---|----------|---------|----------|-----------------|
| 1 | `CLAUDE_TOOLS` não valida tipos de input antes de dispatch | Comportamento inconsistente entre modelos LLM | Adicionar validação básica em `dispatch_tool` (ex: command deve ser string) | 95, ~203 |

### forge_mock_server.py (1 problema)

| # | Problema | Impacto | Correção | Linhas afetadas |
|---|----------|---------|----------|-----------------|
| 1 | `_load_market()` retorna dict vazio sem tratamento de erro downstream | Cenários F3 podem falhar silenciosamente com erro 500 no mock server | Adicionar tratamento de exceção ao ler arquivo e retornar estrutura padrão vazia mas consistente, logando aviso quando fixture está ausente | 37-48 |

### forge_telegram_runner.py (1 problema)

| # | Problema | Impacto | Correção | Linhas afetadas |
|---|----------|---------|----------|-----------------|
| 1 | Função `_await_enter()` pode falhar silenciosamente em sistemas headless | Em CI/CD, runner fica travado aguardando input que nunca vem | Adicionar tratamento de exceção para OSError com logging claro e fallback automático sem bloqueio excessivo (timeout reduzido para 10s) | 103-114, ~68 |

---

## Baixa Prioridade — Melhorias Futuras 📝

### forge_mock_server.py (2 problemas)

| # | Problema | Impacto | Correção | Linhas afetadas |
|---|----------|---------|----------|-----------------|
| 1 | Logs silenciosos impedem debugging em produção | Impossível debuggar problemas do mock server sem adicionar logging manual | Adicionar parâmetro opcional de log_level no handler que permita logs condicionais (ex: apenas erros por padrão) | 20, ~35 |

### forge_telegram_runner.py (1 problema)

| # | Problema | Impacto | Correção | Linhas afetadas |
|---|----------|---------|----------|-----------------|
| 1 | `wait_for_workdir` pode consumir recursos excessivos sem feedback adequado | Em cenários com agentes que fazem muitas operações de I/O, monitor consome CPU/mem desnecessariamente | Adicionar logging periódico do status (ex: "aguardando estabilidade... 120s/600s") e reduzir timeout padrão se necessário | 47-83 |

---

## Resumo por Arquivo

| Arquivo | Alta | Média | Baixa | Total |
|---------|------|-------|-------|-------|
| forge_runner.py | 2 (retry, protected files) | 1 (HTML parser) | - | 3 |
| forge_claude_runner.py | 3 (validação, bloqueio, vars) | 0 | - | 3 |
| forge_mock_server.py | 1 (import os) | 1 (_load_market) | 2 (logging) | 4* |
| forge_telegram_runner.py | 2 (signal, await_enter) | 1 (_await_enter headless) | 1 (wait_for_workdir logging) | 3 |

*\*O problema de import os é crítico mas conta como Alta mesmo que pareça menor.*

---

## Ordem Recomendada de Implementação

### Fase 1 — Correções Críticas (Alta Prioridade)
1. **forge_runner.py**: Mover `_PROTECTED_FILES` para topo + implementar retry em `call_ollama`
2. **forge_claude_runner.py**: Tratar mensagens bloqueadas + inicializar variáveis de fallback
3. **forge_mock_server.py**: Adicionar import os no topo do arquivo

### Fase 2 — Melhorias de Robustez (Média Prioridade)
4. **forge_runner.py**: Melhorar tratamento de erro em `exec_http_get` com HTML inválido
5. **forge_claude_runner.py**: Validar tipos de input antes de dispatch_tool
6. **forge_mock_server.py**: Adicionar tratamento de exceção em `_load_market()`

### Fase 3 — Logging e Feedback (Baixa Prioridade)
7. **forge_mock_server.py**: Implementar logging condicional no handler HTTP
8. **forge_telegram_runner.py**: Melhorar feedback do monitoramento de workdir

---

## Checklist de Verificação Pós-Correção

- [ ] Todos os imports estão declarados no topo dos arquivos (sem inline)
- [ ] Variáveis globais são definidas antes da primeira função que as usa
- [ ] Mensagens de erro contendo "[BLOQUEADO]" são tratadas explicitamente como erros
- [ ] Retry automático implementado para falhas HTTP temporárias
- [ ] Logging adequado em pontos críticos (erros, timeouts, bloqueios)
- [ ] Timeout máximo definido para loops que monitoram workdir
