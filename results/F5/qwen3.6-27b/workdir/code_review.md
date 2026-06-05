# Code Review — FORGE Scripts

## Sumário

| Arquivo | Linhas ~ | Problemas encontrados | Alta | Média | Baixa |
|---------|----------|----------------------|------|-------|-------|
| `forge_runner.py` | 520 | 6 | 3 | 2 | 1 |
| `forge_claude_runner.py` | 280 | 4 | 2 | 1 | 1 |
| `forge_mock_server.py` | 170 | 4 | 2 | 1 | 1 |
| `forge_telegram_runner.py` | 230 | 4 | 2 | 1 | 1 |

**Total: 18 problemas — 9 Alta, 5 Média, 4 Baixa**

---

## forge_runner.py

### Problema 1 — `_PROTECTED_FILES` referenciado antes da definição
- **Categoria:** Robustez / Bug
- **Localização:** linha ~170 (`exec_run_bash`) referencia `_PROTECTED_FILES`, definido na linha ~195
- **Descrição:** A função `exec_run_bash` itera sobre `_PROTECTED_FILES` antes de esta variável ser definida no módulo. Em Python, isso funciona porque a definição é em nível de módulo e o código só executa quando a função é chamada (não quando é definida). Porém, se alguém tentar importar `exec_run_bash` isoladamente ou executar o módulo parcialmente, falhará com `NameError`.
- **Impacto:** Funciona no fluxo normal, mas quebra em testes unitários isolados ou importações parciais. Fragilidade de ordem de definição.
- **Prioridade:** Alta
- **Correção proposta:** Mover a definição de `_PROTECTED_FILES` para antes da função `exec_run_bash`, junto com as outras constantes do módulo (após `_BASH_BLOCKLIST`).

### Problema 2 — `run_command_ok` executa shell sem sanitização adicional
- **Categoria:** Segurança
- **Localização:** linha ~410, check type `"run_command_ok"` em `auto_evaluate()`
- **Descrição:** O check `run_command_ok` executa comandos do cenário via `subprocess.run(cmd, shell=True)` sem nenhuma validação de segurança. Se um arquivo de cenário malicioso contiver `cmd: "rm -rf /"`, ele será executado. A blocklist `_BASH_BLOCKLIST` existe mas não é aplicada aqui — apenas em `exec_run_bash`.
- **Impacto:** Um cenário JSON comprometido pode executar comandos destrutivos no host durante a avaliação automática.
- **Prioridade:** Alta
- **Correção proposta:** Aplicar `_check_bash_safety(cmd)` antes de executar o comando no check `run_command_ok`, reutilizando a mesma blocklist já existente.

### Problema 3 — Divisão por zero em `tok_per_s`
- **Categoria:** Robustez / Bug
- **Localização:** linha ~460, função `save_run_result()`
- **Descrição:** O cálculo `agent_result["tok_total"] / (agent_result["duration_ms"] / 1000)` pode dividir por zero se `duration_ms` for 0. A verificação `if agent_result["duration_ms"] else None` está presente, mas o código usa uma expressão ternária inline que pode ser difícil de ler e é propenso a erros se alguém modificar.
- **Impacto:** Se um run completar instantaneamente (teoricamente possível com mocks rápidos), gera `ZeroDivisionError`.
- **Prioridade:** Alta
- **Correção proposta:** Extrair o cálculo para uma função auxiliar `_safe_tok_per_s(tok_total, duration_ms)` que retorna `None` se `duration_ms <= 0`, tornando a intenção explícita.

### Problema 4 — `import socket` e `import hashlib` dentro do loop
- **Categoria:** Performance
- **Localização:** linhas ~370 e ~395, dentro de `auto_evaluate()` no loop `for check in checks`
- **Descrição:** `import socket` (check `port_open`) e `import hashlib` (check `file_unchanged`) são executados dentro do loop de checks. Embora Python cache imports, isso é anti-padrão e pode causar overhead se os checks forem chamados múltiplas vezes.
- **Impacto:** Baixo impacto prático (imports são cached), mas viola convenções PEP 8 e indica má organização.
- **Prioridade:** Média
- **Correção proposta:** Mover `import socket` e `import hashlib` para o topo do arquivo junto com os demais imports.

### Problema 5 — `_resolve` definido dentro do loop de checks (closure desnecessário)
- **Categoria:** Qualidade / Performance
- **Localização:** linha ~310, função `_resolve` definida dentro do `for check in checks` em `auto_evaluate()`
- **Descrição:** A função `_resolve` é redefinida a cada iteração do loop. Ela captura `fmt_vars` via closure, mas `fmt_vars` não muda durante o loop. Isso gera overhead desnecessário de criação de funções.
- **Impacto:** Performance marginalmente degradada em cenários com muitos checks. Código menos legível.
- **Prioridade:** Média
- **Correção proposta:** Mover `_resolve` para fora do loop, como função auxiliar que recebe `s` e `fmt_vars` como parâmetros, ou definir antes do loop.

### Problema 6 — Docstring menciona "Fixes v0.2" sem changelog formal
- **Categoria:** Documentação / Baixa
- **Localização:** linhas 1-15 (docstring do módulo)
- **Descrição:** A docstring lista "Fixes v0.2" inline, mas não há versão no código nem changelog estruturado. Isso dificulta rastrear o que foi corrigido em cada versão.
- **Impacto:** Dificuldade de manutenção a longo prazo.
- **Prioridade:** Baixa
- **Correção proposta:** Adicionar `__version__ = "0.2"` no módulo e mover as notas de fix para um arquivo `CHANGELOG.md` separado.

---

## forge_claude_runner.py

### Problema 1 — API Key lida a cada turn do loop
- **Categoria:** Performance / Robustez
- **Localização:** linha ~95, dentro do `while turns < MAX_TURNS` em `run_claude_agent()`
- **Descrição:** A leitura de `os.environ.get("ANTHROPIC_API_KEY")` e a criação do `anthropic.Anthropic(api_key=api_key)` estão fora do loop (correto), mas a verificação `if not api_key: raise RuntimeError(...)` deveria estar antes da criação do client, não dentro. Na verdade, o código atual está correto nisso — porém, se a API key mudar entre turns (improvável mas possível em ambientes dinâmicos), o client não seria recriado.
- **Impacto:** Baixo na prática, mas a estrutura pode confundir leitores do código.
- **Prioridade:** Média
- **Correção proposta:** Validar a API key antes de criar o client e levantar erro imediatamente se ausente.

### Problema 2 — `max_tokens=4096` insuficiente para respostas longas com tool calls
- **Categoria:** Robustez / Bug
- **Localização:** linha ~105, `client.messages.create(max_tokens=4096, ...)`
- **Descrição:** O limite de 4096 tokens de saída pode ser insuficiente quando o modelo precisa gerar múltiplos tool calls com argumentos grandes (ex: conteúdo de arquivo). Claude pode truncar a resposta no meio de um JSON de tool call, causando erro de parsing.
- **Impacto:** Respostas truncadas em cenários complexos, falhas silenciosas onde o modelo não consegue completar todas as ferramentas necessárias.
- **Prioridade:** Alta
- **Correção proposta:** Aumentar `max_tokens` para 16384 (ou usar um valor configurável via CLI), compatível com os limites atuais da API Anthropic.

### Problema 3 — Custo estimado usa pricing hardcoded de Sonnet
- **Categoria:** Qualidade / Bug
- **Localização:** linha ~205, cálculo `cost_est = (tok_input * 3 + tok_output * 15) / 1_000_000`
- **Descrição:** O cálculo de custo usa preços hardcoded de Claude Sonnet ($3/M input, $15/M output), mas o runner suporta Opus e Haiku com preços muito diferentes. O comentário diz "Sonnet pricing" mas o valor é aplicado a qualquer modelo.
- **Impacto:** Estimativa de custo incorreta para Opus (~$15/M in, ~$75/M out) e Haiku (~$0.25/M in, ~$1.25/M out). Pode levar a decisões financeiras erradas.
- **Prioridade:** Alta
- **Correção proposta:** Criar um dicionário de preços por modelo e usar o preço correto baseado no `model_id` selecionado.

### Problema 4 — Importação via `sys.path.insert` em vez de import relativo
- **Categoria:** Qualidade / Convenção
- **Localização:** linhas 25-30, `sys.path.insert(0, ...)` + import absoluto
- **Descrição:** O código usa `sys.path.insert()` para importar de `forge_runner`. Isso é frágil e pode causar problemas se o pacote for instalado ou movido. Importações relativas (`from .forge_runner import ...`) seriam mais robustas.
- **Impacto:** Funciona no uso atual, mas quebra se a estrutura de diretórios mudar ou se os arquivos forem importados como parte de um pacote.
- **Prioridade:** Baixa
- **Correção proposta:** Usar `importlib` para carregar o módulo dinamicamente baseado no caminho do arquivo, ou converter em pacote com `__init__.py`.

---

## forge_mock_server.py

### Problema 1 — `import os` no final do arquivo (após uso)
- **Categoria:** Robustez / Bug
- **Localização:** linha ~105 (`import os`) vs linha ~93 (`os.getpid()` em `start()`)
- **Descrição:** O módulo `os` é importado na linha ~105, mas a função `start()` (linha ~93) usa `os.getpid()`. Isso funciona porque `start()` só é chamada no `__main__`, após todos os imports. Porém, se alguém importar `start` diretamente, receberá `NameError: name 'os' is not defined`.
- **Impacto:** Quebra em importações parciais ou testes unitários que chamam `start()` isoladamente.
- **Prioridade:** Alta
- **Correção proposta:** Mover `import os` para o topo do arquivo junto com os demais imports padrão.

### Problema 2 — Falta tratamento de erro em `_load_market` quando JSON é inválido
- **Categoria:** Robustez
- **Localização:** linha ~78, método `_load_market()`
- **Descrição:** Se o arquivo `market-snapshot.json` existir mas conter JSON malformado, `json.loads()` lança `json.JSONDecodeError` não tratado. O servidor retornará 500 (erro interno) para todos os endpoints de mercado.
- **Impacto:** Servidor inteiro quebra se a fixture de mercado estiver corrompida, afetando F3.
- **Prioridade:** Alta
- **Correção proposta:** Envolver `json.loads()` em try/except e retornar `{}` com um log de aviso se o JSON for inválido.

### Problema 3 — PID file pode ficar stale se processo morrer inesperadamente
- **Categoria:** Robustez
- **Localização:** função `stop()` e `status()`, linhas ~108-125
- **Descrição:** Se o servidor morrer por SIGKILL ou crash, o PID file permanece. A função `stop()` tenta matar o PID mas só lida com `ProcessLookupError`. Não verifica se o processo realmente existe antes de tentar matar (exceto via exceção). A função `status()` faz health check HTTP, mas `stop()` não.
- **Impacto:** Usuário pode achar que o servidor está rodando quando não está, ou tentar parar um processo inexistente sem feedback claro.
- **Prioridade:** Média
- **Correção proposta:** Adicionar verificação de existência do processo em `stop()` antes de enviar SIGTERM, e limpar PID file stale automaticamente.

### Problema 4 — `log_message` silenciado impede debug
- **Categoria:** Debuggabilidade / Baixa
- **Localização:** linha ~42, `MockHandler.log_message`
- **Descrição:** Todos os logs HTTP são silenciados com `pass`. Isso é bom para não poluir o output do runner, mas impede completamente o debug de problemas de requisição.
- **Impacto:** Dificulta troubleshooting quando algo dá errado no mock server.
- **Prioridade:** Baixa
- **Correção proposta:** Adicionar flag `--verbose` que habilita logs, ou logar apenas erros (status >= 400).

---

## forge_telegram_runner.py

### Problema 1 — Limpeza de workdir entre runs apaga fixtures copiadas
- **Categoria:** Robustez / Bug
- **Localização:** linha ~205, loop `for f in workdir.glob("*")` antes de cada run
- **Descrição:** Entre runs múltiplos, o código faz `f.unlink()` para todos arquivos que não são "TASK.md". Porém, fixtures copiadas via `fixture_dirs` (ex: `buggy-module/`) também são apagadas. O `shutil.copytree` só roda uma vez no início de `run_telegram_agent`, mas a limpeza entre runs remove esses arquivos. No segundo run, as fixtures não existem mais.
- **Impacto:** Runs subsequentes falham porque arquivos de fixture foram deletados. Cenários com `fixture_dirs` quebram em `--runs > 1`.
- **Prioridade:** Alta
- **Correção proposta:** Preservar arquivos que estão em `seed_files` durante a limpeza entre runs, ou re-copiar fixtures antes de cada run.

### Problema 2 — `wait_for_workdir` não detecta modificações em arquivos existentes
- **Categoria:** Robustez / Bug
- **Localização:** função `wait_for_workdir()`, linhas ~50-80
- **Descrição:** A comparação `if snap != last_snap` compara dicionários de `{path: mtime}`. Se um arquivo existente for modificado, o mtime muda e a detecção funciona. Porém, se o agente modificar um arquivo rapidamente múltiplas vezes dentro do mesmo intervalo de 5s (POLL_INTERVAL_S), mudanças podem ser perdidas porque o snapshot só é tirado a cada 5s. O stable timer pode disparar prematuramente.
- **Impacto:** Em cenários onde o Claude envia respostas rápidas e modifica arquivos em sequência, o runner pode considerar o workdir "estável" antes do agente terminar.
- **Prioridade:** Alta
- **Correção proposta:** Aumentar `stable_s` padrão para 60s (já é 60 no default) e adicionar um mínimo absoluto de tempo de monitoramento (ex: sempre esperar pelo menos 30s após o primeiro arquivo aparecer).

### Problema 3 — `response_override` não documentado como necessário para checks de texto
- **Categoria:** Qualidade / Documentação
- **Localização:** parâmetro `response_override` em `run_telegram_agent()` e flag `--response` no CLI
- **Descrição:** O parâmetro `response_override` é usado para preencher `final_response`, que é necessário para checks do tipo `response_contains`. Porém, sem este parâmetro, todos os checks de texto na resposta final falham silenciosamente. Não há aviso quando `--response` não é fornecido mas o cenário tem tais checks.
- **Impacto:** Usuário pode obter scores artificialmente baixos sem entender por quê.
- **Prioridade:** Média
- **Correção proposta:** Adicionar warning no início do run se o cenário contém checks `response_contains` e `--response` não foi fornecido.

### Problema 4 — Importação via `sys.path.insert` (mesmo problema de claude_runner)
- **Categoria:** Qualidade / Convenção
- **Localização:** linhas 17-19, `sys.path.insert(0, ...)` + import absoluto
- **Descrição:** Mesmo padrão frágil de importação usado em `forge_claude_runner.py`.
- **Impacto:** Fragilidade se a estrutura mudar.
- **Prioridade:** Baixa
- **Correção proposta:** Mesma correção sugerida para `forge_claude_runner.py`.
