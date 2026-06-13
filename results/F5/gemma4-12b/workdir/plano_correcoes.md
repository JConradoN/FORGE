# Plano de Correções — FORGE Scripts

## Prioridade Alta
- [ ] **Segurança em `run_bash`**: Reforçar a validação de comandos e caminhos para evitar que o agente acesse ou modifique arquivos fora do diretório de trabalho (forge_runner.py).
- [ ] **Robustez no Loop Claude**: Garantir que o histórico de mensagens não seja corrompido quando apenas `tool_use` for retornado pela API Anthropic (forge_claude_runner.py).

## Prioridade Média
- [ ] **Concorrência do Mock Server**: Implementar multi-threading no servidor mock para evitar bloqueios em requisições simultâneas (forge_mock_server.py).
- [ ] **Robustez no `kill_port`**: Melhorar a lógica de encerramento de processos que ocupam portas, garantindo limpeza mesmo se o comando `fuser` falhar (forge_runner.py).
- [ ] **Persistência do Mock Server**: Garantir que o processo do mock server seja encerrado corretamente e o arquivo PID removido em caso de erro ou sinal de interrupção (forge_mock_server.py).

## Prioridade Baixa
- [ ] **Melhoria na Experiência do Usuário (UX)**: Adicionar tratamento detalhado para erros de rede no `http_get` e `http_post`.
- [ ] **Precisão de Custos**: Implementar tabela de preços real para o cálculo de custo no provedor Claude.
- [ ] **Refatoração de Configurações**: Unificar as variáveis de ambiente e constantes entre os arquivos de runner.
