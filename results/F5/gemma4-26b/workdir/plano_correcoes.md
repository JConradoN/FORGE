# Plano de Correções — FORGE Scripts

## 1. Prioridade Alta (Implementação Imediata)

### [forge_runner.py] Proteção de Arquivos de Fixture
- **Problema:** A verificação atual de `_PROTECTED_FILES` no `exec_run_bash` é baseada em regex simples e pode ser burlada por caminhos relativos ou manipulações de string.
- **Correção:** Implementar uma validação que resolva o caminho do comando (se possível) ou, mais realisticamente para o contexto de ferramenta, validar se qualquer operação de escrita/redirecionamento no `command` aponta para um arquivo cujo nome está na blocklist, usando `pathlib` para normalização.

### [forge_mock_server.py] Prevenção de Path Traversal
- **Problema:** O endpoint `/mock/github-n8n` e outros podem ser vulneráveis se o path for manipulado (embora atualmente fixos, a lógica de `_serve_file` é perigosa).
- **Correção:** Garantir que todo arquivo servido via `_serve_file` seja validado para estar estritamente dentro do diretório `FIXTURES`.

## 2. Prioridade Média (Planejado)

### [forge_runner.py] Truncamento Seguro de HTTP POST
- **Problema:** O truncamento de `exec_http_post` pode quebrar JSONs válidos.
- **Correção:** Tentar realizar o parse do JSON antes de truncar, ou se truncar, garantir que o resultado seja uma string informativa e não um JSON malformado que quebrará o agente.

### [forge_claude_runner.py] Integridade de Mensagens Anthropic
- **Problema:** Risco de inconsistência no histórico de mensagens quando `tool_use` ocorre sem conteúdo de texto associado.
- **Correção:** Refinar a construção do objeto `messages` para garantir conformidade com o schema da API Anthropic (separando claramente blocos de texto e tool_use).

### [forge_runer.py] Leitura de Arquivos Grandes no Auto-Eval
- **Problema:** `file_contains` lê todo o arquivo na memória.
- **Correção:** Implementar leitura por buffer para verificar a presença da "needle".

## 3. Prioridade Baixa (Melhorias de Estilo/Manutenção)

### [forge_mock_server.py] Gestão de PID
- **Problema:** Risco de PID órfão.
- **Correção:** Melhorar o tratamento de exceções no `start()`.

### [forge_telegram_runner.py] Robustez do Monitoramento
- **Problema:** Detecção de estabilidade baseada apenas em tempo pode ser imprecisa.
- **Correção:** Adicionar uma verificação de "checksum" ou contagem de arquivos para confirmar a estabilidade.
