# Plano de Correções — FORGE Scripts

Este documento detalha o plano de ação para mitigar as vulnerabilidades e melhorias identificadas durante o Code Review. A priorização foca em Segurança, Robustez e Estabilidade do ambiente.

## Prioridade ALTA (Correção Imediata)
*Impacto: Risco de segurança ou quebra de execução em ambientes automatizados.*

### 1. Fortalecimento da Blocklist no `run_bash` (`forge_runner.py`)
- **Problema:** A verificação atual por strings simples pode ser burlada via encodings ou subcomandos complexos.
- **Proposta:** Implementar uma validação mais rigorosa que verifique a presença de caracteres proibidos ou use um parser de comandos (se possível) para identificar intenções destrutivas antes da execução.
- **Objetivo:** Impedir execuções não autorizadas mesmo em cenários de jailbreak de prompt.

### 2. Eliminação de Redundância no `MODELS` (`forge_claude_runner.py`)
- **Problema:** Entradas duplicadas para modelos Haiku podem causar confusão na configuração do experimento.
- **Proposta:** Limpar o dicionário `MODELS`, mantendo apenas uma chave única por modelo real da Anthropic.
- **Objetpor:** Melhorar a manutenibilidade.

### 3. Gestão de PID Segura no Mock Server (`forge_mock_server.py`)
- **Problema:** Uso de `/tmp/forge_mock_server.pid` é vulnerável a colisões e ataques de symlink em ambientes multi-usuário.
- **Proposta:** Utilizar o diretório `workdir` do cenário atual ou um caminho específico dentro da home do usuário (`~/.forge_mock_server.pid`) para armazenar o PID.
- **Objetivo:** Garantir isolamento entre runs de diferentes cenários.

### 4. Robustez no Telegram Runner em Ambientes sem TTY (`forge_telegram_runner.py`)
- **Problema:** A dependência de `/dev/tty` pode travar execuções via SSH ou CI.
- **Proposta:** Melhorar o fallback para garantir que, se o TTY não for detectado, o runner aguarde um tempo determinado sem bloquear a thread principal de forma ineficiente.

---

## Prioridade MÉDIA (Melhoria de Qualidade)
*Impacto: Dificuldade de manutenção ou risco de efeitos colaterais.*

### 1. Refinamento do `_kill_port` (`forge_runner.py`)
- **Problema:** Risco de encerrar processos que não pertencem ao runner ao tentar limpar portas.
- **Proposta:** Validar se o processo encontrado na porta possui o comando original do runner no seu `cmdline`.

### 2. Desacoplamento de Fixtures no Mock Server (`forge_mock_server.py`)
- **Problema:** O servidor é dependente de uma estrutura rígida fora da árvore do projeto.
- **Proposta:** Adicionar um parâmetro `--fixture-dir` para permitir que o runner aponte onde os assets estão localizados.

### 3. Tratamento de Erros na API Anthropic (`forge_claude_runner.py`)
- **Problema:** O erro da API interrompe o loop, mas não fornece telemetria detalhada no log do run.
- **Proposta:** Capturar a exceção e registrar um objeto estruturado de erro no `agent_result` para facilitar o debug via dashboard/logs.

---

## Prioridade BAIXA (Otimização e Estilo)
*Impacto: Performance e legibilidade.*

### 1. Otimização do Polling em `wait_for_workdir` (`forge_telegram_runner.py`)
- **Problema:** Delay de até 5 segundos desnecessários após a criação de arquivos.
- **Proposta:** Reduzir o intervalo de polling para 1 segundo ou utilizar uma estratégia de backoff exponencial.

### 2. Padronização de Logs e Docstrings
- **Problema:** Inconsistência no nível de detalhamento dos logs entre os providers.
- **Proposta:** Aplicar um padrão de log estruturado (JSON) para facilitar a ingestão por ferramentas como n8n ou ELK futuramente.
