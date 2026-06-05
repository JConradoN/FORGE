# Code Review — FORGE Scripts

## Sumário
O conjunto de scripts FORGE está funcional e bem estruturado para o propósito de benchmark. A separação entre runners (local, Claude, Telegram) é clara e reutiliza a lógica central do `forge_runner.py`. Foram identificados problemas menores relacionados a redundância de configuração, robustez na gestão de processos e dependência de ambiente interativo em scripts que deveriam ser automatizáveis.

## forge_runner.py
### Problema 1
- **Categoria:** Segurança / Robustez
- **Localização:** `run_bash` (via blocklist)
- **Detalhe:** Embora exista uma blocklist de comandos destrutivos, a segurança baseada em strings pode ser contornada com técnicas de encoding ou pipes complexos. Para um ambiente de benchmark controlado, é aceitável, mas não é "seguro" para uso em servidores expostos.

### Problema 2
- **Categoria:** Robustez
- **Localização:** `_kill_port`
- **Detalque:** A função encerra processos que estão ouvindo na porta, mas se houver outros serviços legítimos ou múltiplos subprocessos (ex: um proxy e o servidor alvo), pode haver um encerramento indevido de processos que não pertencem ao runner.

## forge_claude_runner.py
### Problema 1
- **Categoria:** Manutenibilidade
- **Localização:** `MODELS` dictionary
- **Detalhe:** Existem entradas duplicadas ou redundantes (ex: `claude-haiku-4-5` e `claude-haiku-4-5-20251001`). Isso pode causar confusão na configuração do runner.

### Problema 2
- **Categoria:** Robustness / Error Handling
- **Localização:** Loop de mensagens (`while turns < MAX_TURNS`)
- **Detalhe:** O erro da API é capturado e o loop quebra, mas o retorno não diferencia claramente se o fim do processo foi um sucesso natural (fim de turnos) ou uma falha crítica de infraestrutura/API para o usuário final.

## forge_monkey_server.py
### Problema 1
- **Categoria:** Robustez / Portabilidade
- **Localização:** `PID_FILE = Path("/tmp/forge_mock_server.pid")`
- **Detalhe:** O uso de `/tmp` com um nome fixo pode gerar colisões em ambientes multi-usuário ou se múltiplos experimentos FORGE forem rodados simultaneamente no mesmo host (embora o projeto seja focado em single-user local).

### Problema 2
- **Categoria:** Testabilidade
- **Localização:** `MockHandler.do_GET`
- **Detalhe:** O servidor é altamente dependente da estrutura de diretórios externa (`FIXTURES`). Se o runner for movido sem os assets, ele falha silenciosamente retornando 404 para todos os endpoints.

## forge_telegram_runner.py
### Problema 1
- **Categoria:** Robustez / Ambiente
- **Localização:** `_await_enter` (uso de `/dev/tty`)
- **Detalhe:** A tentativa de abrir `/dev/tty` falhará em ambientes de execução não interativos (como pipelines de CI ou execuções via SSH sem TTY alocado), cainindo para o fallback de 20s, o que pode atrasar automações pretendidas.

### Problema 2
- **Categoria:** Performance / Eficiência
- **Localização:** `wait_for_workdir`
- **Detalhe:** O mecanismo de polling (`time.sleep(POLL_INTERVAL_S)`) introduz um atraso artificial de até 5 segundos mesmo após o arquivo ter sido criado, o que pode ser otimizado com `inotify` ou reduzindo o intervalo em execuções rápidas.
