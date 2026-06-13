# Plano de Correções — FORGE Scripts

## Prioridade: Alta (Implementar Agora)

### forge_runner.py
1.  **Proteção de Arquivos (Bypass de Regex):** Alterar `exec_run_bash` para validar o caminho absoluto final de qualquer operação de escrita/redirecionamento contra a lista de arquivos protegidos, em vez de apenas usar regex no comando bruto.
2.  **Segurança do Bash (Blocklist):** Reforçar a regex da blocklist e adicionar uma verificação de "sanitização" básica para evitar injeção de comandos via variáveis ou concatenação simples.

### forge_claude_runner.py
1.  **Loop Infinito/Crash:** Adicionar validação de conteúdo na resposta do Claude para garantir que, se a API retornar algo inesperado (sem tool calls e sem texto), o loop seja interrompido com erro.
2.  **Path Traversal via Tool Call:** Implementar uma camada de sanitização no `dispatch_tool` (ou envolver as ferramentas) que valide se os caminhos fornecidos pelo Claude estão contidos dentro do `workdir`.

### forge_telegram_runner.py
1.  **Estabilidade Prematura:** Melhorar a lógica de `wait_for_workdir` para garantir que o tempo de estabilidade seja maior ou que haja uma verificação de integridade mínima.
2.  **Contaminação de Workdir:** Garantir que o `workdir` seja limpo/resetado antes da cópia das fixtures no início do run, evitando que arquivos de runs anteriores interfiram no cenário atual.

## Prioridade: Média (Planejar)

### forge_runner.py
1.  **HTTP Overflow (Memory):** Implementar leitura via stream para `exec_http_get` para evitar carregar arquivos gigantes na memória antes do truncamento.

### forge_mock_server.py
1.  **Path Traversal no Mock:** Validar que os endpoints de arquivo não permitam acesso fora da pasta `FIXTURES`.

### forge_telegram_runner.py
1.  **Interatividade em CI/CD:** Substituir a leitura de `/dev/tty` por uma verificação de `sys.stdin.isatty()` para evitar crashes em ambientes automatizados.

## Prioridade: Baixa (Registrar)

### forge_claude_runner.py
1.  **Limpeza de Modelos:** Unificar o dicionário de modelos para remover duplicatas e inconsistências de nomes.

### forge_mock_server.py
1.  **Segurança do PID File:** Mover o `PID_FILE` de `/tmp/` para um local mais seguro ou dentro do diretório do projeto.
2.  **Logging de Erro no JSON:** Adicionar log de erro caso o carregamento do snapshot de mercado falhe.

### forge_runner.py
1.  **Melhoria na Regex da Blocklist:** Tornar a lista de comandos proibidos mais abrangente e menos dependente de padrões simples.
