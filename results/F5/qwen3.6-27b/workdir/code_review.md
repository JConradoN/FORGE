# Code Review — FORGE Scripts

## Sumário

| Arquivo | Linhas | Problemas | Alta | Média | Baixa |
|---------|--------|-----------|------|-------|-------|
| `forge_runner.py` | ~560 | 8 | 3 | 3 | 2 |
| `forge_claude_runner.py` | ~240 | 4 | 1 | 2 | 1 |
| `forge_mock_server.py` | ~130 | 3 | 1 | 1 | 1 |
| `forge_telegram_runner.py` | ~270 | 5 | 2 | 2 | 1 |
| **Total** | **~1600** | **20** | **7** | **8** | **5** |

Categorias: Segurança (3), Robustez (6), Qualidade (5), Testabilidade (4), Performance (2)

---

## forge_runner.py

### Problema 1 — `_PROTECTED_FILES` referenciado antes da definição
- **Categoria:** Robustez / Bug
- **Localização:** linha ~190 (`exec_run_bash`) vs linha ~215 (definição de `_PROTECTED_FILES`)
- **Descrição:** A função `exec_run_bash` referencia `_PROTECTED_FILES` no loop `for protected in _PROTECTED_FILES`, mas a variável só é definida mais abaixo no módulo. Em Python, isso funciona porque o código não é executado até a chamada da função — mas se alguém tentar importar `exec_run_bash` e chamar antes que `_PROTECTED_FILES` seja definido (ex: importação parcial), vai falhar com `NameError`.
- **Impacto:** Funciona no fluxo normal, mas quebra em testes unitários ou importações isoladas.
- **Prioridade:** Alta
- **Correção proposta:** Mover a definição de `_PROTECTED_FILES` para antes de `exec_run_bash`, junto com as outras constantes de configuração.

### Problema 2 — `run_command_ok` executa shell sem sanitização adicional
- **Categoria:** Segurança
- **Localização:** linha ~430, check `run_command_ok` em `auto_evaluate()`
- **Descrição:** O check `run_command_ok` executa comandos do cenário via `subprocess.run(cmd, shell=True)`. Os cenários são JSONs de fixture controlados, mas não há validação de que o comando venha de uma fonte confiável. Se um cenário malicioso fosse injetado, permitiria execução arbitrária.
- **Impacto:** Risco de code execution se cenários forem comprometidos ou editados por usuários não-confiáveis.
- **Prioridade:** Alta
- **Correção proposta:** Adicionar validação de que o comando não contenha padrões perigosos (mesma blocklist `_BASH_BLOCKLIST` usada em `exec_run_bash`).

### Problema 3 — `auto_evaluate` importa módulos dentro do loop
- **Categoria:** Performance / Qualidade
- **Localização:** linhas ~405, ~420 (`import socket`, `import hashlib`, `import subprocess`)
- **Descrição:** `socket`, `hashlib` e `subprocess` são importados dentro dos branches `elif` do loop de checks. Embora Python cacheie imports, isso é anti-padrão e pode causar overhead em cenários com muitos checks repetidos.
- **Impacto:** Leve degradação de performance; código menos limpo.
- **Prioridade:** Média
- **Correção proposta:** Mover os imports para o topo do arquivo junto com os demais.

### Problema 4 — `call_ollama` não valida URL base
- **Categoria:** Robustez
- **Localização:** linha ~270, função `call_ollama()`
- **Descrição:** Se Ollama não estiver rodando, a exceção genérica `except Exception as e: raise RuntimeError(str(e))` engole detalhes importantes como timeouts de conexão. Não há retry nem mensagem amigável.
- **Impacto:** Erros difíceis de diagnosticar quando Ollama está offline.
- **Prioridade:** Média
- **Correção proposta:** Adicionar verificação prévia de conectividade ou mensagem mais específica para `urllib.error.URLError`.

### Problema 5 — `aggregate_runs` crash com `statistics.stdev` em lista unitária
- **Categoria:** Robustez
- **Localização:** linha ~490, função `aggregate_runs()`
- **Descrição:** O código já protege com `if len(pcts) > 1`, mas se `run_results` estiver vazio (lista vazia), `statistics.mean([])` vai lançar `StatisticsError`. Não há proteção contra lista vazia.
- **Impacto:** Crash se nenhum run for executado com sucesso.
- **Prioridade:** Média
- **Correção proposta:** Adicionar guard `if not run_results: return {}` no início da função.

### Problema 6 — `save_run_result` divide por zero em `tok_per_s`
- **Categoria:** Robustez
- **Localização:** linha ~475, cálculo de `tok_per_s`
- **Descrição:** O código tem `if agent_result["duration_ms"] else None`, mas se `duration_ms` for 0 (agente respondeu instantaneamente), a divisão ocorre. Na prática é raro, mas possível com respostas cacheadas.
- **Impacto:** `ZeroDivisionError` em edge case.
- **Prioridade:** Baixa
- **Correção proposta:** Usar `if agent_result["duration_ms"] > 0 else None`.

### Problema 7 — `_HTMLTextExtractor` não lida com tags auto-fechadas
- **Categoria:** Qualidade
- **Localização:** linha ~135, classe `_HTMLTextExtractor`
- **Descrição:** Tags como `<br/>`, `<img/>`, `<hr/>` são ignoradas silenciosamente. Não é um bug funcional mas o parser não chama `handle_startendtag`. Em HTML com tags auto-fechadas dentro de SKIP_TAGS (ex: raro, mas possível), poderia haver comportamento inesperado.
- **Impacto:** Mínimo — funciona na prática para os casos de uso do FORGE.
- **Prioridade:** Baixa
- **Correção proposta:** Adicionar `handle_startendtag` para cobrir tags auto-fechadas.

### Problema 8 — Docstring menciona "Fixes v0.2" mas não versiona o código
- **Categoria:** Qualidade
- **Localização:** linha ~1, docstring do módulo
- **Descrição:** A docstring lista "Fixes v0.2" como changelog embutido. Isso mistura documentação de versão com documentação de API. Não há constante `__version__` no módulo.
- **Impacto:** Dificulta rastreamento de versão programaticamente.
- **Prioridade:** Baixa
- **Correção proposta:** Adicionar `__version__ = "0.2"` e mover changelog para CHANGELOG.md separado.

---

## forge_claude_runner.py

### Problema 9 — API Key lida sem validação de formato
- **Categoria:** Segurança
- **Localização:** linha ~105, função `run_claude_agent()`
- **Descrição:** A chave API é lida de variáveis de ambiente mas não há verificação de que esteja vazia ou inválida antes de criar o cliente. Se a variável existir mas estiver vazia (`ANTHROPIC_API_KEY=""`), o SDK vai falhar na primeira chamada com erro genérico.
- **Impacto:** Erro confuso em vez de mensagem clara de configuração.
- **Prioridade:** Alta
- **Correção proposta:** Adicionar `if not api_key or not api_key.strip(): raise RuntimeError("...")` antes de criar o cliente.

### Problema 10 — Custo estimado usa pricing hardcoded de Sonnet
- **Categoria:** Qualidade
- **Localização:** linha ~230, cálculo `cost_est`
- **Descrição:** O custo é calculado com `$3/M input + $15/M output` (pricing Sonnet), mas o comentário diz "Sonnet pricing" enquanto o código pode ser usado com Opus ou Haiku que têm preços diferentes. O usuário recebe estimativa errada sem aviso.
- **Impacto:** Estimativa de custo incorreta para modelos não-Sonnet.
- **Prioridade:** Média
- **Correção proposta:** Adicionar tabela de pricing por modelo e selecionar dinamicamente, ou adicionar aviso quando o modelo não é Sonnet.

### Problema 11 — `sys.path.insert` com string em vez de Path
- **Categoria:** Qualidade
- **Localização:** linha ~25, `sys.path.insert(0, str(Path(__file__).parent))`
- **Descrição:** Converte Path para string desnecessariamente. `sys.path` aceita strings, mas o padrão do código usa Path em outros lugares. Inconsistência.
- **Impacto:** Nenhum funcional — apenas inconsistência de estilo.
- **Prioridade:** Baixa
- **Correção proposta:** Manter como está ou usar `Path(__file__).parent.as_posix()` para consistência.

### Problema 12 — Claude tools duplicam descrições do runner principal
- **Categoria:** Qualidade / Manutenção
- **Localização:** linhas ~50-130, definição de `CLAUDE_TOOLS`
- **Descrição:** As descrições das ferramentas são duplicadas entre `TOOLS` (forge_runner.py) e `CLAUDE_TOOLS`. Se uma descrição for atualizada em um lugar e não no outro, os agentes receberão instruções inconsistentes.
- **Impacto:** Divergência de comportamento entre providers ao longo do tempo.
- **Prioridade:** Média
- **Correção proposta:** Gerar `CLAUDE_TOOLS` a partir de `TOOLS` com transformação automática, ou manter descrições em um módulo compartilhado.

---

## forge_mock_server.py

### Problema 13 — `import os` no meio do arquivo (após funções)
- **Categoria:** Qualidade / Bug potencial
- **Localização:** linha ~105, `import os` após definição de `stop()` e `status()`
- **Descrição:** O `import os` está posicionado após as definições de função. A função `start()` usa `os.getpid()` e `stop()` usa `_os.kill`. Se o módulo for importado e `start()` chamado antes do interpretador chegar no `import os`, vai falhar. Na prática funciona porque Python executa imports na ordem, mas é anti-padrão grave.
- **Impacto:** Pode causar `NameError: name 'os' is not defined` em certas condições de importação.
- **Prioridade:** Alta
- **Correção proposta:** Mover `import os` para o topo do arquivo junto com os demais imports.

### Problema 14 — PID_FILE pode ficar stale se processo morrer inesperadamente
- **Categoria:** Robustez
- **Localização:** função `stop()` e `status()`
- **Descrição:** Se o servidor crashar sem limpar o PID file, `stop()` tentará matar um processo inexistente. O código lida com `ProcessLookupError`, mas `status()` vai reportar incorretamente que está rodando.
- **Impacto:** Estado inconsistente entre PID file e realidade.
- **Prioridade:** Média
- **Correção proposta:** Em `status()`, verificar se o processo existe antes de tentar conectar.

### Problema 15 — `_load_market` retorna dict vazio silenciosamente
- **Categoria:** Robustez
- **Localização:** linha ~80, método `_load_market()`
- **Descrição:** Se o arquivo de fixture não existir, retorna `{}` silenciosamente. Os endpoints `/mock/usd-brl` etc. vão retornar `{}` ou `[]`, fazendo os testes falharem sem indicar que a fixture está faltando.
- **Impacto:** Falhas difíceis de diagnosticar quando fixtures estão ausentes.
- **Prioridade:** Baixa
- **Correção proposta:** Logar um aviso ou retornar erro 500 com mensagem clara.

---

## forge_telegram_runner.py

### Problema 16 — Limpeza de workdir entre runs apaga arquivos do agente
- **Categoria:** Robustez / Bug
- **Localização:** linha ~210, loop `for f in workdir.glob("*")`
- **Descrição:** Entre runs, o código faz `f.unlink()` para todos arquivos que não são "TASK.md". Mas se um run anterior criou subdiretórios com outputs, esses NÃO são removidos (glob só pega arquivos diretos). O próximo run vai acumular arquivos antigos.
- **Impacto:** Contaminação entre runs — checks de file_exists podem passar incorretamente.
- **Prioridade:** Alta
- **Correção proposta:** Usar `rglob("*")` e remover também diretórios vazios, ou recriar o workdir do zero (preservando apenas fixtures).

### Problema 17 — `_await_enter` com fallback de 20s pode ser insuficiente
- **Categoria:** Robustez
- **Localização:** linha ~135, função `_await_enter()`
- **Descrição:** Quando não há TTY (ex: execução em CI/container), o fallback é `time.sleep(20)`. 20 segundos pode ser insuficiente para o usuário enviar mensagens no Telegram, especialmente em cenários complexos.
- **Impacto:** Runner começa a monitorar antes do agente terminar de trabalhar.
- **Prioridade:** Média
- **Correção proposta:** Aumentar fallback ou tornar configurável via `--no-tty-wait`.

### Problema 18 — `wait_for_workdir` compara snapshots por caminho absoluto
- **Categoria:** Qualidade
- **Localização:** linha ~60, função `wait_for_workdir()`
- **Descrição:** O snapshot usa caminhos absolutos (`str(f)`), mas a filtragem de seed_files usa nomes relativos. Se o workdir for um symlink ou se houver normalização diferente de caminho, a comparação pode falhar.
- **Impacto:** Falso positivo/negativo na detecção de estabilidade.
- **Prioridade:** Média
- **Correção proposta:** Usar caminhos relativos ao workdir no snapshot para consistência.

### Problema 19 — `checks_key = "aurelia_auto_checks"` hardcoded
- **Categoria:** Qualidade
- **Localização:** linha ~200, mapeamento de checks alternativos
- **Descrição:** O código faz mapping de `"aurelia_auto_checks"` para `"auto_checks"`, acoplando o runner a uma convenção específica. Se outro provider usar outra chave, não funcionará.
- **Impacto:** Baixa portabilidade entre providers.
- **Prioridade:** Baixa
- **Correção proposta:** Tornar a chave alternativa configurável ou documentar como convenção do framework.

### Problema 20 — `response_override` não é usado em checks de conteúdo quando vazio
- **Categoria:** Robustez
- **Localização:** função `run_telegram_agent()` e uso em `auto_evaluate`
- **Descrição:** Quando `response_override` é string vazia (default), checks do tipo `response_contains` vão falhar silenciosamente pois a resposta final será `""`. Não há aviso de que o usuário deveria ter fornecido `--response`.
- **Impacto:** Scores artificialmente baixos sem indicação clara do motivo.
- **Prioridade:** Baixa (comportamento esperado para uso semi-manual)
- **Correção proposta:** Adicionar warning se `response_override` está vazio e há checks de `response_contains`.
