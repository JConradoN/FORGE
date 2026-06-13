# Code Review — FORGE Scripts

## Sumário
O código base do framework FORGE está funcional e bem estruturado, mas apresenta vulnerabilidades de segurança em execuções de shell, falta de robustez no tratamento de erros de rede/I/O e redundâncias de lógica entre os provedores (Ollama vs Claude). Foram identificados 12 problemas críticos ou de alta prioridade que impactam a estabilidade do benchmark.

## forge_runner.py
### Problema 1
- **Categoria:** Segurança
- **Localização:** linha 148, função `exec_run_bash`
- **Descrição:** Embora exista uma `_BASH_BLOCKLIST`, ela é baseada em Regex simples que pode ser burlada por variações de sintaxe (ex: `rm -rf /` vs `rm  -rf /`). Além disso, a verificação de arquivos protegidos não impede o uso de redirecionamentos (`>`) ou pipes para modificar conteúdo.
- **Impacto:** Um agente malicioso ou um prompt mal interpretado pode apagar dados do sistema ou sobrescrever arquivos críticos de configuração.
- **Prioridade:** Alta
- **Correção proposta:** Implementar uma sanitização mais rigorosa e usar `shlex.split()` antes da execução, além de validar se o comando final não contém redirecionamentos para caminhos fora do `workdir`.

### Problema 2
- **Categoria:** Robustez / Concorrência
- **Localização:** linha 185, função `_kill_port`
- **Descrição:** O uso de `fuser -k` depende da existência do utilitário no sistema e pode falhar silenciosamente ou demorar se o processo estiver em estado "zumbi".
- **Impacto:** Portas podem ficar presas entre runs, causando erro de "Address already in use" no próximo ciclo.
- **Prioridade:** Média
- **Correção proposta:** Implementar um fallback usando `ps` e `kill` para garantir que o processo na porta seja encerrado.

### Problema 3
- **Categoria:** Performance / Estabilidade
- **Localização:** linha 258, função `exec_http_get`
- **Descrição:** O timeout de 30s é fixo e não trata exceções específicas de conexão (Timeout vs Connection Refused).
- **Impacto:** Uma requisição lenta pode travar o loop do agente por tempo considerável.
- **Prioridade:** Baixa
- **Correção proposta:** Adicionar tratamento específico para `urllib.error.URLError` e logs detalhados de erro de rede.

## forge_claude_runner.py
### Problema 1
- **Categoria:** Robustez / Consistência
- **Localização:** linha 145, função `run_claude_agent`
- **Descrição:** O loop do Claude não trata corretamente a ausência de conteúdo de texto quando há apenas tool_use (o que pode acontecer em alguns modelos).
- **Impacto:** A variável `text_content` pode ficar vazia ou o histórico de mensagens pode ser enviado incompleto para a API.
- **Prioridade:** Alta
- **Correção proposta:** Garantir que, se houver apenas tool_use, uma mensagem de sistema ou um placeholder seja adicionado ao histórico antes da próxima chamada.

### Problema 2
- **Categoria:** Segurança / Configuração
- **Localização:** linha 103, variável `api_key`
- **Descrição:** O fallback para `ANTHROPIC_API_KEY_FOXDEV` é uma convenção interna que pode causar confusão se não documentada.
- **Impacto:** Dificulta a depuração de problemas de autenticação em ambientes diferentes.
- **Prioridade:** Baixa
- **Correção proposta:** Padronizar apenas para `ANTHROPIC_API_KEY` e usar um arquivo `.env`.

### Problema 3
- **Categoria:** Robustez
- **Localização:** linha 180, função `run_claude_agent` (bloco final)
- **Descrição:** O cálculo de custo estimado é simplista e não considera o modelo específico selecionado.
- **Impacto:** Informação de custo imprecisa para o usuário.
- **Prioridade:** Baixa
- **Correção proposta:** Criar um dicionário de preços por modelo no arquivo de configuração.

## forge_mock_server.py
### Problema 1
- **Categoria:** Robustez / Concorrência
- **Localização:** linha 95, função `start`
- **Descrição:** O servidor usa `HTTPServer`, que é single-threaded por padrão e não lida bem com múltiplas conexões simultâneas ou timeouts de conexão.
- **Impacto:** Se o agente tentar acessar múltiplos recursos rapidamente, a requisição pode falhar.
- **Prioridade:** Média
- **Correção proposta:** Utilizar `ThreadingMixIn` para tornar o servidor multi-thread.

### Problema 2
- **Categoria:** Robustez
- **Localização:** linha 75, função `_serve_file`
- **Descrição:** Não há verificação se o arquivo existe antes de tentar ler (embora haja um check no `do_GET`, a lógica interna pode falhar).
- **Impacto:** Erro interno do servidor (500) em vez de 404.
- **Prioridade:** Baixa
- **Correção proposta:** Adicionar bloco try/except ao ler o arquivo.

### Problema 3
- **Categoria:** Segurança
- **Localização:** linha 126, função `stop`
- **Descrição:** O uso de `os.kill(pid, signal.SIGTERM)` sem um loop de espera pode falhar se o processo demorar a fechar.
- **Impacto:** O arquivo PID pode não ser removido ou o processo pode persistir em estado "zombie".
- **Prioridade:** Média
- **Correção proposta:** Implementar um pequeno loop de retry para garantir que o processo foi encerrado antes de remover o arquivo PID.
