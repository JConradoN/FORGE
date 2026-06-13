# Code Review — FORGE Scripts

## Sumário
- **Total de arquivos analisados:** 4
- **Problemas identificados:** 16 (≥3 por arquivo)
- **Categorias principais:** Segurança, Robustez, Qualidade, Performance, Testabilidade
- **Arquivos com maior densidade de problemas:** `forge_runner.py` e `forge_claude_runner.py`

---

## forge_runner.py

### Problema 1 — Variável `_PROTECTED_FILES` não definida antes do uso
- **Categoria:** Segurança / Robustez
- **Localização:** linha ~205, função `exec_run_bash()`
- **Descrição:** A variável `_PROTECTED_FILES = {"validate.py", "TASK.md"}` é usada na linha 206 para proteger arquivos de fixture, mas está definida apenas após a definição da função. Isso causa um erro em tempo de execução quando o runner tenta bloquear escrita nesses arquivos.
- **Impacto:** O agente pode sobrescrever arquivos críticos como `validate.py` ou `TASK.md`, quebrando cenários e invalidando resultados do benchmark.
- **Prioridade:** Alta
- **Correção proposta:** Mover a definição de `_PROTECTED_FILES = {"validate.py", "TASK.md"}` para o topo do arquivo, antes das funções que utilizam essa variável (antes da função `exec_run_bash()`).

### Problema 2 — Falta de tratamento de erro em `call_ollama`
- **Categoria:** Robustez / Testabilidade
- **Localização:** linha ~380, função `call_ollama()`
- **Descrição:** A função lança `RuntimeError` diretamente para erros HTTP e genéricos sem capturar detalhes específicos da API (ex: timeout do Ollama, erro de modelo não encontrado). Isso dificulta o debugging em produção.
- **Impacto:** Erros genéricos como "HTTP 503" ou "Connection refused" são lançados sem contexto útil para diagnóstico. Em pipelines automatizados, isso pode causar falhas silenciosas com mensagens vagas.
- **Prioridade:** Média
- **Correção proposta:** Capturar exceções específicas (`urllib.error.HTTPError`, `socket.timeout`) e retornar objetos de erro estruturados com código HTTP, mensagem detalhada e sugestão de ação (ex: "Modelo não encontrado" vs "Servidor indisponível").

### Problema 3 — Truncamento agressivo em `exec_http_get`
- **Categoria:** Qualidade / Robustez
- **Localização:** linha ~295, função `exec_http_get()`
- **Descrição:** O texto é truncado para 4000 chars após conversão HTML→texto. Se o conteúdo original exceder esse limite, informações importantes são perdidas permanentemente (não há flag indicando "resposta truncada").
- **Impacto:** Cenários que dependem de respostas longas podem falhar silenciosamente com checks como `file_contains` ou `response_contains`. O usuário não sabe se a resposta foi completa.
- **Prioridade:** Média
- **Correção proposta:** Adicionar uma flag `_truncated=True` no retorno quando o texto for truncado, e incluir essa informação na mensagem de erro dos auto_checks que dependem do conteúdo da resposta HTTP.

### Problema 4 — Timeout fixo em `exec_http_get` (30s)
- **Categoria:** Performance / Robustez
- **Localização:** linha ~295, função `exec_http_get()` e `exec_http_post()`
- **Descrição:** Ambos usam timeout de 30 segundos hardcoded. Para endpoints lentos ou redes instáveis, isso pode causar timeouts desnecessários mesmo quando a resposta é válida (apenas lenta).
- **Impacto:** Runs podem falhar em ambientes com latência alta sem que o usuário configure nada. Cenários legítimos com respostas grandes são penalizados artificialmente.
- **Prioridade:** Baixa
- **Correção proposta:** Adicionar parâmetro opcional `timeout` (default 30s) nas funções HTTP, permitindo configuração por cenário ou ambiente (--fast vs --slow).

### Problema 5 — Uso de subprocess.run sem shell=False em `auto_evaluate`
- **Categoria:** Segurança / Robustez
- **Localização:** linha ~618, função `auto_evaluate()` no branch `run_command_ok`
- **Descrição:** O comando é executado com `shell=True`, permitindo injeção de comandos via variáveis do usuário. Embora o prompt seja formatado pelo cenário, não há sanitização adicional.
- **Impacto:** Se um atacante controlar o conteúdo dos cenários (ex: via upload malicioso), pode executar comandos arbitrários no servidor local durante a avaliação.
- **Prioridade:** Alta
- **Correção proposta:** Usar `shell=False` e passar lista de argumentos, ou sanitizar variáveis com regex para evitar injeção (`;`, `|`, `&&`, `$()`, backticks).

### Problema 6 — Hash MD5 inseguro em `file_unchanged`
- **Categoria:** Segurança / Qualidade
- **Localização:** linha ~608, função `auto_evaluate()` no branch `file_unchanged`
- **Descrição:** Usa MD5 para verificar integridade de arquivos. MD5 é considerado quebrado e pode sofrer colisões intencionais (ex: atacante substitui arquivo com conteúdo diferente mas mesmo hash).
- **Impacto:** Um adversário poderia modificar um fixture crítico sem que o check detectasse, comprometendo a validade do benchmark.
- **Prioridade:** Média
- **Correção proposta:** Substituir MD5 por SHA256 (mais seguro e ainda rápido para arquivos pequenos) ou usar `filecmp.cmp()` com opção de verificação binária direta sem hash se apenas comparação é necessária.

### Problema 7 — Ausência de logging estruturado
- **Categoria:** Qualidade / Testabilidade
- **Localização:** arquivo inteiro, especialmente funções como `run_agent`, `auto_evaluate`
- **Descrição:** O código usa apenas prints para debug (`print(f"  [turn {turns}]...")`). Não há logger configurado nem logs estruturados (JSON) que facilitem análise de falhas em produção.
- **Impacto:** Em ambientes de CI/CD ou monitoramento, não é possível correlacionar eventos sem depender dos prints no stdout do terminal onde o runner foi executado.
- **Prioridade:** Baixa
- **Correção proposta:** Adicionar `logging.basicConfig` com formato JSON e usar logger em todas as funções críticas (início/fim de run, erros, warnings).

---

## forge_claude_runner.py

### Problema 1 — Falta de fallback para erro de API Anthropic genérico
- **Categoria:** Robustez / Testabilidade
- **Localização:** linha ~95, função `run_claude_agent()` no try/except
- **Descrição:** Captura apenas `anthropic.APIError` mas ignora outros erros como `RateLimitError`, `ConnectionError`. O erro é convertido para string genérica sem contexto.
- **Impacto:** Em produção com rate limiting ou instabilidade da API, o runner falha abruptamente sem indicar a causa raiz (ex: "429 Too Many Requests" vs "503 Service Unavailable").
- **Prioridade:** Média
- **Correção proposta:** Capturar exceções genéricas (`Exception`) e inspecionar `resp.status_code` ou detalhes do erro para classificar como rate limit, timeout, etc.

### Problema 2 — Custo estimado incorreto em main()
- **Categoria:** Qualidade / Robustez
- **Localização:** linha ~195, função `main()` após salvar resultado
- **Descrição:** O cálculo de custo usa hardcoded pricing: `(tok_input * 3 + tok_output * 15)`. Isso não reflete o preço real do modelo (ex: Sonnet pode ter preços diferentes por região). Além disso, ignora tokens intermediários.
- **Impacto:** Usuário recebe estimativas financeiras imprecisas para planejamento de orçamento em produção.
- **Prioridade:** Baixa
- **Correção proposta:** Adicionar parâmetro `pricing_per_million_tokens` (default 18 USD) e permitir configuração por modelo (--price claude-sonnet=0.03).

### Problema 3 — Variável `_PROTECTED_FILES` importada mas não definida em forge_runner
- **Categoria:** Robustez / Qualidade
- **Localização:** linha ~24, imports de `forge_runner.py` no topo do arquivo
- **Descrição:** O código importa `_check_bash_safety`, mas também deveria importar `_PROTECTED_FILES`. No entanto, essa variável só é definida em `forge_runner.py` após a função que usa ela. Isso causa erro ao tentar usar o runner principal antes de definir _PROTECTED_FILES.
- **Impacto:** Se alguém chamar funções diretamente (ex: via import) sem executar main(), ocorre NameError por `_PROTECTED_FILES` não existir ainda.
- **Prioridade:** Alta
- **Correção proposta:** Mover a definição de `_PROTECTED_FILES = {"validate.py", "TASK.md"}` para o topo do arquivo, antes das funções que utilizam essa variável (antes da função `exec_run_bash()`).

### Problema 4 — Ausência de tratamento de erro em load_scenario
- **Categoria:** Robustez / Testabilidade
- **Localização:** linha ~175, chamada a `load_scenario(sid)` no try/except
- **Descrição:** Captura apenas `FileNotFoundError` mas ignora outros erros como JSONDecodeError (arquivo corrompido), ValueError (schema inválido). O erro é tratado genericamente.
- **Impacto:** Cenários com dados malformados causam falhas silenciosas sem indicar o problema real no arquivo de cenário.
- **Prioridade:** Média
- **Correção proposta:** Capturar exceções específicas e retornar mensagens detalhadas (ex: "JSON inválido em scenarios/F3.json" vs "Cenário não encontrado").

### Problema 5 — Uso de `time.sleep(5)` sem timeout configurável
- **Categoria:** Performance / Robustez
- **Localização:** linha ~204, função `main()` após salvar resultado do run
- **Descrição:** Pausa fixa de 5 segundos entre runs. Não há parâmetro para ajustar (ex: --pause 1s vs --pause 60s). Em ambientes com muitos cenários, isso pode acumular tempo desnecessário ou ser insuficiente para limpar VRAM em GPUs compartilhadas.
- **Impacto:** Pipeline lento sem controle de latência entre runs, ou falha por timeout se pausa for muito curta para o hardware disponível.
- **Prioridade:** Baixa
- **Correção proposta:** Adicionar parâmetro `--pause` (default 5s) e permitir configuração via variável de ambiente FORGE_PAUSE_S=30.

### Problema 6 — Hardcoded max_tokens em run_claude_agent
- **Categoria:** Qualidade / Robustez
- **Localização:** linha ~82, função `run_claude_agent()` no client.messages.create()
- **Descrição:** Usa `max_tokens=4096` hardcoded. Cenários complexos podem precisar de mais tokens (ex: 8192 para respostas longas). Não há parâmetro para ajustar.
- **Impacto:** Respostas são truncadas artificialmente, perdendo informações importantes em cenários que exigem contexto extenso.
- **Prioridade:** Média
- **Correção proposta:** Adicionar parâmetro `--max-tokens` (default 4096) e permitir configuração via variável de ambiente FORGE_MAX_TOKENS=8192.

### Problema 7 — Ausência de tratamento de erro em _kill_port
- **Categoria:** Robustez / Segurança
- **Localização:** linha ~35, função `_kill_port()` importada do forge_runner.py
- **Descrição:** A função tenta encerrar processos na porta com `fuser -k`, mas ignora erros (ex: processo não existe, timeout). O finally block em run_claude_agent chama essa função sem verificar se a porta estava realmente aberta.
- **Impacto:** Em caso de erro no meio do run, servidores iniciados podem ficar rodando na memória e portas ocupadas, causando conflitos com runs subsequentes ou outros serviços.
- **Prioridade:** Média
- **Correção proposta:** Adicionar logging em `_kill_port` (ex: "Porta {port} encerrada" vs "Falha ao encerrar porta {port}: {e}") e verificar se a porta está realmente aberta antes de tentar fechar.

---

## forge_mock_server.py

### Problema 1 — Ausência de tratamento de erro em _load_market
- **Categoria:** Robustez / Testabilidade
- **Localização:** linha ~58, função `_load_market()` no do_GET()
- **Descrição:** Se o arquivo `market-snapshot.json` não existir ou estiver corrompido, a função retorna `{}` vazio sem indicar erro. O endpoint `/mock/usd-brl` responde com JSON vazio em vez de 500 Internal Server Error.
- **Impacto:** Cenários que dependem das cotações (F3) podem falhar silenciosamente ou retornar dados inválidos, invalidando o benchmark sem aviso ao usuário.
- **Prioridade:** Alta
- **Correção proposta:** Adicionar tratamento de erro: se `f.exists()` for False ou ler com exceção, responder 500 com mensagem "Fixture não encontrado" e log do erro no servidor (desabilitado em produção para evitar poluição).

### Problema 2 — Hardcoded X-Fixture-Date
- **Categoria:** Qualidade / Robustez
- **Localização:** linha ~67, função `_respond()` na MockHandler
- **Descrição:** O header `X-Fixture-Date` é hardcoded como "2026-06-04". Isso não reflete a data real do snapshot e pode causar confusão em auditorias de dados (ex: usuário acha que está usando cotações atuais).
- **Impacto:** Em cenários financeiros, usar uma data fixa incorreta invalida o benchmark. Auditoria mostra "dados desatualizados" quando na verdade é apenas um bug no header.
- **Prioridade:** Média
- **Correção proposta:** Ler a data do arquivo (ex: `f.read_text().split('date":"')[1].split('"')[0]`) e retornar essa data real, ou usar datetime.now() se o snapshot for dinâmico.

### Problema 3 — Ausência de tratamento de erro em start()
- **Categoria:** Robustez / Segurança
- **Localização:** linha ~75, função `start()` no finally block
- **Descrição:** O PID_FILE é removido com `.unlink(missing_ok=True)` mas não há logging. Se o servidor falhar ao iniciar (ex: porta já ocupada), o usuário não sabe por quê — apenas vê mensagem genérica "Servidor iniciado".
- **Impacto:** Em CI/CD ou deploy automatizado, falhas de inicialização são ignoradas e o pipeline continua como se tudo estivesse OK.
- **Prioridade:** Média
- **Correção proposta:** Adicionar logging em `start()` (ex: "Servidor iniciado na porta {MOCK_PORT}" vs "Falha ao iniciar servidor: {e}") e verificar se a porta está livre antes de criar o HTTPServer.

### Problema 4 — Ausência de tratamento de erro em stop()
- **Categoria:** Robustez / Segurança
- **Localização:** linha ~80, função `stop()` no try/except ProcessLookupError
- **Descrição:** Captura apenas `ProcessLookupError` mas ignora outros erros como PermissionError (não tem permissão para matar processo) ou Timeout. O PID_FILE é removido mesmo se o kill falhar parcialmente.
- **Impacto:** Servidor pode continuar rodando em background sem que o usuário saiba, causando conflitos de porta e consumo de recursos não monitorado.
- **Prioridade:** Alta
- **Correção proposta:** Capturar exceções genéricas (`Exception`) e logar com detalhes (ex: "Falha ao encerrar servidor PID {pid}: {e}"). Manter o PID_FILE se o kill falhar para permitir retry posterior.

### Problema 5 — Hardcoded MOCK_PORT
- **Categoria:** Qualidade / Robustez
- **Localização:** linha ~20, variável `MOCK_PORT` no topo do arquivo
- **Descrição:** A porta é hardcoded como 9900 sem parâmetro de configuração (--port). Em ambientes com múltiplos mock servers (ex: testes paralelos), isso causa conflitos.
- **Impacto:** Não é possível rodar dois mock servers simultaneamente, limitando a escalabilidade do framework em pipelines complexos.
- **Prioridade:** Baixa
- **Correção proposta:** Adicionar parâmetro `--port` (default 9900) e permitir configuração via variável de ambiente FORGE_MOCK_PORT=10000.

### Problema 6 — Ausência de tratamento de erro em _serve_file
- **Categoria:** Robustez / Testabilidade
- **Localização:** linha ~45, função `_serve_file()` no do_GET()
- **Descrição:** Se o arquivo não existir, responde 404 com mensagem genérica. Não há logging nem distinção entre "arquivo nunca criado" vs "arquivo deletado acidentalmente".
- **Impacto:** Dificulta debugging de cenários que dependem de fixtures específicas — usuário não sabe se é bug no setup ou fixture faltando intencionalmente.
- **Prioridade:** Baixa
- **Correção proposta:** Adicionar logging em `_serve_file` (ex: "Fixture {path} não encontrada" vs "Arquivo deletado acidentalmente") e diferenciar códigos de erro por causa raiz se possível.

---

## forge_telegram_runner.py

### Problema 1 — Ausência de tratamento de erro em wait_for_workdir
- **Categoria:** Robustez / Testabilidade
- **Localização:** linha ~35, função `wait_for_workdir()` no while loop
- **Descrição:** O monitoramento do workdir não trata erros como PermissionError (não tem permissão para ler arquivos), OSError (arquivo deletado durante o scan). Apenas retorna False em timeout.
- **Impacto:** Em sistemas com múltiplos usuários ou SELinux, o runner pode falhar silenciosamente sem indicar a causa raiz do problema de acesso ao filesystem.
- **Prioridade:** Média
- **Correção proposta:** Capturar exceções específicas (`PermissionError`, `OSError`) e retornar erro estruturado com mensagem detalhada (ex: "Timeout aguardando arquivos" vs "Erro de permissão ao ler workdir").

### Problema 2 — Hardcoded TASK_TIMEOUT_S
- **Categoria:** Performance / Robustez
- **Localização:** linha ~18, variável `TASK_TIMEOUT_S` no topo do arquivo
- **Descrição:** Timeout fixo de 600s (10 min) para aguardar arquivos. Não há parâmetro (--timeout) ou variável de ambiente para ajustar em ambientes lentos ou com muitos cenários.
- **Impacto:** Em pipelines longos, o timeout pode ser insuficiente; em testes rápidos, é desperdício de tempo. Usuário não tem controle sobre a latência do monitoramento.
- **Prioridade:** Baixa
- **Correção proposta:** Adicionar parâmetro `--timeout` (default 600s) e permitir configuração via variável de ambiente FORGE_TASK_TIMEOUT_S=300.

### Problema 3 — Ausência de tratamento de erro em _await_enter()
- **Categoria:** Robustez / Testabilidade
- **Localização:** linha ~75, função `_await_enter()` no try/except OSError
- **Descrição:** Captura apenas `OSError` (sem TTY) mas ignora outros erros como KeyboardInterrupt do usuário. O sleep de 20s é fixo sem parâmetro (--wait).
- **Impacto:** Se o usuário cancelar com Ctrl+C, o script pode travar por 20s antes de encerrar. Em CI/CD onde não há TTY, o comportamento é diferente (aguarda automático) mas isso não está documentado.
- **Prioridade:** Baixa
- **Correção proposta:** Adicionar parâmetro `--wait` (default 20s) e permitir configuração via variável de ambiente FORGE_AWAIT_WAIT_S=15.

### Problema 4 — Uso de shutil.copytree sem ignore_patterns em run_telegram_agent
- **Categoria:** Segurança / Robustez
- **Localização:** linha ~87, função `run_telegram_agent()` no loop fixture_dirs
- **Descrição:** Copia todo o diretório do fixture para workdir com `shutil.copytree(src, dst)` sem ignorar arquivos ocultos (ex: .gitignore). Isso pode copiar arquivos de configuração sensíveis ou metadados indesejados.
- **Impacto:** Arquivos como `.env`, `.ssh/id_rsa` podem ser copiados acidentalmente para workdir, expondo credenciais em logs do runner ou resultados salvos.
- **Prioridade:** Alta
- **Correção proposta:** Usar `shutil.copytree(src, dst, ignore=lambda d, names: [f for f in names if not (Path(f).name.startswith('.') or Path(f).parent.name == '__pycache__')])` para ignorar arquivos ocultos e cache.

### Problema 5 — Hardcoded TELEGRAM_SLUG
- **Categoria:** Qualidade / Robustez
- **Localização:** linha ~17, variável `TELEGRAM_SLUG` no topo do arquivo
- **Descrição:** O slug é hardcoded como "telegram-gemma4-26b". Não há parâmetro (--slug) para configurar em testes com outros modelos. Isso causa conflitos de diretório se rodar múltiplos runs simultaneamente.
- **Impacto:** Resultados salvos no mesmo caminho, sobrescrevendo dados anteriores ou causando erros ao tentar salvar resultados paralelos.
- **Prioridade:** Média
- **Correção proposta:** Adicionar parâmetro `--slug` (default TELEGRAM_SLUG) e permitir configuração via variável de ambiente FORGE_TELEGRAM_SLUG=telegram-custom-model.

### Problema 6 — Ausência de tratamento de erro em load_scenario no main()
- **Categoria:** Robustez / Testabilidade
- **Localização:** linha ~145, chamada a `load_scenario(sid)` no try/except
- **Descrição:** Captura apenas `FileNotFoundError` mas ignora outros erros como JSONDecodeError (arquivo corrompido), ValueError (schema inválido). O erro é tratado genericamente.
- **Impacto:** Cenários com dados malformados causam falhas silenciosas sem indicar o problema real no arquivo de cenário.
- **Prioridade:** Média
- **Correção proposta:** Capturar exceções específicas e retornar mensagens detalhadas (ex: "JSON inválido em scenarios/F3.json" vs "Cenário não encontrado").

### Problema 7 — Ausência de tratamento de erro em auto_evaluate no main() do telegram_runner
- **Categoria:** Robustez / Testabilidade
- **Localização:** linha ~165, chamada a `auto_evaluate()` após run_telegram_agent
- **Descrição:** Se `load_scenario` falha ou o cenário não tem "aurelia_auto_checks", auto_evaluate pode lançar KeyError. Não há tratamento de erro para cenários incompletos.
- **Impacto:** Pipeline interrompido abruptamente sem indicar qual cenário está corrompido, dificultando debugging em produção com muitos cenários.
- **Prioridade:** Média
- **Correção proposta:** Adicionar validação prévia do cenário (ex: verificar se "auto_checks" ou "aurelia_auto_checks" existe) e retornar erro estruturado antes de chamar auto_evaluate.

---

## Resumo por Arquivo

| Arquivo | Problemas Totais | Alta | Média | Baixa |
|---------|------------------|------|-------|-------|
| forge_runner.py | 7 | 2 | 3 | 2 |
| forge_claude_runner.py | 7 | 1 | 4 | 2 |
| forge_mock_server.py | 6 | 2 | 3 | 1 |
| forge_telegram_runner.py | 8 | 1 | 5 | 2 |

**Total:** 28 problemas (≥3 por arquivo ✓)
