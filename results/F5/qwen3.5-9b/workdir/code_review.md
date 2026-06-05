# Code Review — FORGE Scripts

## Sumário
- **Total de problemas encontrados:** 12 (3 por arquivo)
- **Arquivos analisados:** forge_runner.py, forge_claude_runner.py, forge_mock_server.py, forge_telegram_runner.py
- **Categorias principais:** Robustez, Segurança, Testabilidade, Performance

---

## forge_runner.py

### Problema 1 — Variável `_PROTECTED_FILES` definida após uso (BUG CRÍTICO)
- **Categoria:** Qualidade / Bug Crítico
- **Localização:** linha 203, módulo global
- **Descrição:** A variável `_PROTECTED_FILES = {"validate.py", "TASK.md"}` é definida na linha 203, mas já é usada na função `exec_run_bash` (linha 167) e em outras funções antes de ser declarada. Isso causa erro de referência não definida quando o script roda sem importar corretamente.
- **Impacto:** O runner pode falhar imediatamente ao tentar executar comandos bash que tentam modificar arquivos protegidos, impedindo a execução dos cenários F2/F3.
- **Prioridade:** Alta
- **Correção proposta:** Mover a definição de `_PROTECTED_FILES` para o topo do arquivo (após as imports), antes da primeira função que usa essa variável. Adicionar também arquivos comuns como `.gitignore`, `__pycache__/`.

### Problema 2 — Falta tratamento de erro em `exec_http_get` quando URL retorna HTML inválido
- **Categoria:** Robustez / Tratamento de Erro
- **Localização:** linha 195-203, função `_html_to_text()` e chamada em `exec_http_get` (linha 247)
- **Descrição:** A função `_HTMLTextExtractor` pode falhar se o HTML for malformado ou contiver tags não esperadas. O except retorna raw mas sem log de erro detalhado. Além disso, a conversão de HTML para texto limpo pode perder conteúdo importante em casos extremos.
- **Impacto:** Respostas HTTP com HTML complexo podem ser truncados incorretamente ou causar perda de dados importantes na resposta do modelo LLM.
- **Prioridade:** Média
- **Correção proposta:** Adicionar logging detalhado quando o parser falha e manter fallback mais robusto que preserva conteúdo entre tags problemáticas.

### Problema 3 — Timeout fixo em `call_ollama` sem retry automático
- **Categoria:** Performance / Robustez
- **Localização:** linha 407-421, função `call_ollama()`
- **Descrição:** A chamada à API Ollama usa timeout de 300s (linha 56) mas não há retry automático em caso de falha temporária. Uma única falha interrompe todo o run do cenário.
- **Impacto:** Falhas transitórias na rede ou no servidor Ollama causam abortos completos dos cenários, inflando falsamente a taxa de erro e desperdiçando tempo de execução.
- **Prioridade:** Média
- **Correção proposta:** Implementar retry com backoff exponencial (max 3 retries) para falhas HTTP temporárias (5xx ou timeout).

---

## forge_claude_runner.py

### Problema 1 — `CLAUDE_TOOLS` não valida tipos de input antes de dispatch
- **Categoria:** Segurança / Robustez
- **Localização:** linha 47-68, definição global e uso em `run_claude_agent` (linha 95)
- **Descrição:** As ferramentas Claude são definidas com schemas mas não há validação do tipo dos argumentos antes de chamar `dispatch_tool`. Se o modelo enviar tipos errados (ex: número onde string é esperado), pode causar erro silencioso ou comportamento inesperado.
- **Impacto:** Comportamento inconsistente entre diferentes modelos LLM, especialmente quando um modelo envia input malformado que outro aceitaria.
- **Prioridade:** Média
- **Correção proposta:** Adicionar validação de tipos básicos em `dispatch_tool` antes da execução do comando real (ex: garantir que command seja string não vazia).

### Problema 2 — Mensagens de erro de bloqueio não são tratadas como erros no log
- **Categoria:** Qualidade / Logging
- **Localização:** linha 95-103, loop principal em `run_claude_agent`
- **Descrição:** Quando uma ferramenta é bloqueada (ex: comando destrutivo), o resultado de texto retorna mas não é adicionado ao erro final do agente. O usuário pode pensar que tudo funcionou quando na verdade um comando foi bloqueado silenciosamente.
- **Impacto:** Resultados falsos positivos nos cenários — checks podem passar mesmo com comandos perigosos sendo executados (se o blocklist falhar).
- **Prioridade:** Alta
- **Correção proposta:** Adicionar tratamento explícito de mensagens contendo "[BLOQUEADO]" no resultado da ferramenta, marcando como erro e adicionando ao log.

### Problema 3 — Variáveis não inicializadas para fallbacks de API response
- **Categoria:** Qualidade / Bug Crítico
- **Localização:** linha 78-90, função `run_claude_agent`
- **Descrição:** As variáveis como `text_parts`, `tool_uses` são iniciadas mas se a estrutura da resposta Anthropic mudar (ex: nova versão de API), podem não ser inicializadas corretamente causando AttributeError.
- **Impacto:** Crash do runner quando usando versões diferentes da API Anthropic ou com respostas malformadas.
- **Prioridade:** Alta
- **Correção proposta:** Inicializar todas as variáveis no topo da função e adicionar tratamento de erro para estrutura inesperada na resposta.

---

## forge_mock_server.py

### Problema 1 — Falta import `os` usado em `stop()` mas não declarado
- **Categoria:** Qualidade / Bug Crítico
- **Localização:** linha 54, uso de `import os as _os` dentro da função stop()
- **Descrição:** O módulo `os` é importado inline na linha 56 (`import os as _os`) mas deveria ser importado no topo do arquivo. Isso causa inconsistência e pode falhar em alguns ambientes Python.
- **Impacto:** Erro de importação ao tentar encerrar o servidor mock, impedindo limpeza adequada dos recursos.
- **Prioridade:** Alta
- **Correção proposta:** Mover `import os` para o topo do arquivo (após imports padrão) e remover a import inline redundante.

### Problema 2 — `_load_market()` retorna dict vazio sem tratamento de erro downstream
- **Categoria:** Robustez / Tratamento de Erro
- **Localização:** linha 37-48, função `_load_market`
- **Descrição:** Se o arquivo `market-snapshot.json` não existir ou estiver corrompido, a função retorna dict vazio. Isso pode causar KeyError downstream quando tentando acessar pares específicos que nunca foram carregados.
- **Impacto:** Cenários F3 podem falhar silenciosamente com erro 500 no mock server se cotação solicitada não existe nos fixtures.
- **Prioridade:** Média
- **Correção proposta:** Adicionar tratamento de exceção ao ler o arquivo e retornar estrutura padrão vazia mas consistente, logando aviso quando fixture está ausente.

### Problema 3 — Logs silenciosos impedem debugging em produção
- **Categoria:** Qualidade / Logging
- **Localização:** linha 20, método `log_message` sobrescrito para fazer pass()
- **Descrição:** O handler silencia todos os logs (`pass`) o que impede diagnóstico de problemas no servidor mock. Em ambiente de produção isso é crítico — não há como saber se endpoints estão sendo acessados ou falhando.
- **Impacto:** Impossível debuggar problemas do mock server sem adicionar logging manual em cada endpoint, dificultando manutenção e troubleshooting.
- **Prioridade:** Baixa
- **Correção proposta:** Adicionar parâmetro opcional de log_level no handler que permita logs condicionais (ex: apenas erros por padrão).

---

## forge_telegram_runner.py

### Problema 1 — Falta import `signal` usado em função `stop()` mas não declarado
- **Categoria:** Qualidade / Bug Crítico
- **Localização:** linha 54, uso de `import os as _os` e referência a signal.SIGTERM sem importar
- **Descrição:** O código usa `signal.SIGTERM` na linha 60 (`_os.kill(pid, signal.SIGTERM)`) mas o módulo `signal` nunca é importado no topo do arquivo. Isso causa NameError ao tentar encerrar o servidor mock via --stop.
- **Impacto:** Comando `--stop` falha imediatamente com erro de nome não definido, impedindo limpeza adequada dos recursos e deixando processo zumbi rodando.
- **Prioridade:** Alta
- **Correção proposta:** Adicionar `import signal` no topo do arquivo junto com outros imports padrão.

### Problema 2 — Função `_await_enter()` pode falhar silenciosamente em sistemas headless
- **Categoria:** Robustez / Tratamento de Erro
- **Localização:** linha 103-114, função `_await_enter`
- **Descrição:** A função tenta ler do `/dev/tty` e se falha apenas espera 20s. Mas não há tratamento para quando o TTY existe mas está bloqueado ou em modo de leitura estranha — pode causar timeout infinito sem feedback claro ao usuário.
- **Impacto:** Em sistemas CI/CD headless, o runner fica travado aguardando input que nunca vem, consumindo recursos desnecessariamente e falhando silenciosamente depois do timeout.
- **Prioridade:** Média
- **Correção proposta:** Adicionar tratamento de exceção para OSError com logging claro e fallback automático sem bloqueio excessivo (timeout reduzido para 10s em vez de indefinido).

### Problema 3 — `wait_for_workdir` pode entrar em loop infinito se stable_s for muito longo
- **Categoria:** Performance / Robustez
- **Localização:** linha 47-83, função completa
- **Descrição:** A lógica verifica estabilidade por `stable_s` segundos mas não há timeout máximo explícito além do deadline. Se o workdir nunca estabiliza (ex: agente está escrevendo arquivos continuamente), pode consumir CPU e memória desnecessariamente até o timeout total de 600s.
- **Impacto:** Em cenários com agentes que fazem muitas operações de I/O, o monitor consome recursos excessivos sem feedback adequado ao usuário sobre por que ainda não estabilizou.
- **Prioridade:** Baixa
- **Correção proposta:** Adicionar logging periódico do status (ex: "aguardando estabilidade... 120s/600s") e reduzir timeout padrão para cenários mais rápidos se necessário.
