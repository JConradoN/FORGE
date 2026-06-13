# Code Review — FORGE Scripts

## Sumário
Foram identificados problemas em todos os 4 arquivos do framework FORGE. A revisão abrangeu qualidade, robustez, segurança, performance e testabilidade.

- forge_runner.py: 5 problemas (2 Alta, 3 Média)
- forge_claude_runner.py: 4 problemas (1 Alta, 3 Média)
- forge_mock_server.py: 3 problemas (0 Alta, 3 Média)
- forge_telegram_runner.py: 4 problemas (1 Alta, 3 Média)

Total: 16 problemas identificados

## forge_runner.py

### Problema 1 - Segurança: Validação insuficiente em write_file
- **Categoria:** Segurança
- **Localização:** linha ~250, função `exec_write_file`
- **Descrição:** A validação de caminho usa `startswith()` que é vulnerável a ataques com caminhos relativos como `../../../etc/passwd`. O método atual não impede completamente a escalada de diretório.
- **Impacto:** Risco de escrita fora do diretório de trabalho, potencial exposição de arquivos sensíveis
- **Prioridade:** Alta
- **Correção proposta:** Usar `os.path.commonpath()` para validação mais robusta ou implementar verificação recursiva que garanta o caminho esteja contido no workdir.

### Problema 2 - Robustez: Tratamento de exceções genérico em call_ollama
- **Categoria:** Robustez
- **Localização:** linha ~350, função `call_ollama`
- **Descrição:** O bloco except captura todas as exceções com `except Exception as e`, o que pode mascarar erros específicos como problemas de conexão ou tempo limite.
- **Impacto:** Dificulta debug de problemas na API Ollama, erros genéricos sem contexto
- **Prioridade:** Alta
- **Correção proposta:** Separar exceções específicas (urllib.error.URLError, urllib.error.HTTPError, socket.timeout) com mensagens claras.

### Problema 3 - Qualidade: Código duplicado em validação de caminhos
- **Categoria:** Qualidade
- **Localização:** funções `exec_write_file` e `exec_read_file`
- **Descrição:** Ambas funções têm lógica idêntica para validar se o caminho está dentro do workdir. Isso viola DRY (Don't Repeat Yourself).
- **Impacto:** Manutenção difícil - mudanças na validação precisam ser feitas em dois lugares
- **Prioridade:** Média
- **Correção proposta:** Criar função auxiliar `_validate_workdir_path(path, workdir)` e reutilizá-la.

### Problema 4 - Performance: Leitura de arquivos grandes sem streaming
- **Categoria:** Performance
- **Localização:** linha ~260, função `exec_read_file`
- **Descrição:** Arquivos maiores que 8000 bytes são truncados, mas a leitura é feita toda de uma vez em memória. Para arquivos muito grandes isso pode consumir muita RAM.
- **Impacto:** Potencial uso excessivo de memória com arquivos grandes
- **Prioridade:** Média
- **Correção proposta:** Implementar leitura por chunks para arquivos acima de um limite (ex: 1MB).

### Problema 5 - Testabilidade: Dependência direta de subprocess.run sem mock
- **Categoria:** Testabilidade
- **Localização:** função `exec_run_bash`
- **Descrição:** A chamada a `subprocess.run` não é easily mockable para testes unitários, dificultando testes automatizados.
- **Impacto:** Dificulta criação de suite de testes completa
- **Prioridade:** Média
- **Correção proposta:** Extrair lógica de execução para função separada que possa ser injetada/mockada.

## forge_claude_runner.py

### Problema 1 - Segurança: Validação insuficiente de tokens da API
- **Categoria:** Segurança
- **Localização:** linha ~50, função `run_claude_agent`
- **Descrição:** A validação de chave API é feita apenas verificando se a variável existe, mas não valida se ela está vazia ou contém apenas espaços.
- **Impacto:** Erro silencioso se ANTHROPIC_API_KEY estiver definida como string vazia
- **Prioridade:** Alta
- **Correção proposta:** Adicionar validação: `if not api_key or not api_key.strip()`

### Problema 2 - Qualidade: Código duplicado na estrutura de ferramentas
- **Categoria:** Qualidade
- **Localização:** CLAUDE_TOOLS vs TOOLS em forge_runner.py
- **Descrição:** A definição das ferramentas é duplicada entre os dois arquivos. Mudanças nas descrições ou parâmetros precisam ser feitas em ambos.
- **Impacto:** Risco de inconsistência entre os runners
- **Prioridade:** Média
- **Correção proposta:** Importar TOOLS do forge_runner.py e converter para formato Anthropic quando necessário.

### Problema 3 - Robustez: Sem tratamento para modelos não suportados
- **Categoria:** Robustez
- **Localização:** linha ~200, função `main`
- **Descrição:** Se um modelo não estiver no dicionário MODELS, ele é usado diretamente sem validação. Isso pode causar erros na API Anthropic.
- **Impacto:** Erro de API com mensagem confusa se o usuário digitar um modelo inválido
- **Prioridade:** Média
- **Correção proposta:** Validar que model_id esteja em MODELS.values() ou lançar erro claro.

### Problema 4 - Performance: Pausa fixa entre runs
- **Categoria:** Performance
- **Localização:** linha ~250, função `main`
- **Descrição:** A pausa de 5 segundos entre runs é fixa e não considera o tempo real necessário. Para modelos rápidos isso é ineficiência.
- **Impacto:** Tempo total de execução maior que o necessário
- **Prioridade:** Média
- **Correção proposta:** Implementar pausa dinâmica baseada no tempo do último run ou permitir configuração via argumento.

## forge_mock_server.py

### Problema 1 - Qualidade: Tratamento de exceções genérico em _serve_file
- **Categoria:** Qualidade
- **Localização:** linha ~40, função `_serve_file`
- **Descrição:** Se o arquivo não existir, a função retorna 404, mas não registra o erro ou faz log. Isso pode esconder problemas com fixtures ausentes.
- **Impacto:** Dificulta debug quando fixtures estão corrompidas ou ausentes
- **Prioridade:** Média
- **Correção proposta:** Adicionar logging básico para erros de fixture (usando print ou logging simples).

### Problema 2 - Robustez: Sem validação de PID em stop()
- **Categoria:** Robustez
- **Localização:** função `stop()`
- **Descrição:** A função tenta matar o processo usando o PID do arquivo, mas não verifica se o PID pertence realmente ao forge_mock_server.
- **Impacto:** Risco de matar processo errado se o PID for reutilizado
- **Prioridade:** Média
- **Correção proposta:** Validar que o processo seja really ours (verificar nome do processo).

### Problema 3 - Segurança: Servidor escuta em todas as interfaces
- **Categoria:** Segurança
- **Localização:** linha ~80, função `start()`
- **Descrição:** O servidor é iniciado com HTTPServer(("127.0.0.1", MOCK_PORT)), mas o código mostra ("127.0.0.1", ...) que é seguro. No entanto, comentários ou documentação poderiam ser mais claros.
- **Impacto:** Potencial confusão sobre escopo de rede
- **Prioridade:** Média
- **Correção proposta:** Adicionar comentário claro: "Servidor bindado apenas a localhost para segurança".

## forge_telegram_runner.py

### Problema 1 - Robustez: Sem validação de resposta em wait_for_workdir
- **Categoria:** Robustez
- **Localização:** função `wait_for_workdir`
- **Descrição:** A função monitora arquivos, mas não verifica se os arquivos criados são válidos (ex: não vazios). Um arquivo vazio poderia passar como "completo".
- **Impacto:** Resultados falsos positivos em cenários onde o agente deve criar conteúdo
- **Prioridade:** Alta
- **Correção proposta:** Adicionar verificação de tamanho mínimo para arquivos novos (ex: >10 bytes).

### Problema 2 - Qualidade: Código duplicado na construção de prompt
- **Categoria:** Qualidade
- **Localização:** funções `run_telegram_agent` e `main`
- **Descrição:** A lógica para construir o prompt com variáveis é duplicada. Mudanças nas variáveis precisam ser feitas em dois lugares.
- **Impacto:** Risco de inconsistência entre runs
- **Prioridade:** Média
- **Correção proposta:** Extrair para função auxiliar `_build_prompt(scenario, workdir, port, prompt_vars)`.

### Problema 3 - Performance: Sleep fixo em loop de monitoramento
- **Categoria:** Performance
- **Localização:** linha ~20, constante POLL_INTERVAL_S
- **Descrição:** O intervalo de poling é fixado em 5 segundos, o que pode ser lento para detectar mudanças rápidas ou muito frequente para operações lentas.
- **Impacto:** Tempo total de execução maior que o necessário
- **Prioridade:** Média
- **Correção proposta:** Tornar POLL_INTERVAL_S configurável via argumento ou adaptativo (começar rápido, aumentar progressivamente).

### Problema 4 - Testabilidade: Dependência direta de /dev/tty
- **Categoria:** Testabilidade
- **Localização:** função `_await_enter`
- **Descrição:** A função tenta abrir /dev/tty diretamente, o que falha em ambientes sem terminal (ex: CI/CD). O fallback é sleep(20s) que não é ideal.
- **Impacto:** Dificulta execução automatizada em pipelines
- **Prioridade:** Média
- **Correção proposta:** Tornar a espera por Enter opcional via argumento ou usar mecanismo mais robusto (ex: input() com try/except).
