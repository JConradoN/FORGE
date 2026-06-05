# Plano de Correções — FORGE Scripts

## Prioridade Alta (Implementação Imediata)

1.  **`forge_runner.py` - Proteção de Arquivos:** Refatorar `exec_run_bash` e `exec_write_file` para usar caminhos resolvidos (`.resolve()`) ao verificar a lista `_PROTECTED_FILES`, impedindo bypass via `./` ou `../`.
2.  **`forge_telegram_runner.py` - Limpeza de Workdir:** Alterar a lógica de limpeza no início do run para não deletar arquivos que não foram criados pelo próprio framework (preservar o que o usuário colocou lá).

## Prioridade Média

1.  **`forge_runner.py` - Timeout em `run_command_ok`:** Adicionar parâmetro `timeout` ao `subprocess.run` dentro da função de avaliação automática para evitar hangs.
2.  **`forge_mock_server.py` - Robustez de Fixtures:** Implementar tratamento de erro no carregamento do `market-snapshot.json`, retornando HTTP 500 caso o arquivo esteja ausente ou corrompido.
3.  **`forge_claude_runner.py` - Validação de Resposta:** Adicionar verificação de segurança para garantir que `resp.content` é iterável antes do processamento de tool uses.

## Prioridade Baixa

1.  **`forge_runner.py` - Divisão por Zero:** Adicionar guarda na métrica `tok_per_s` para evitar erro caso a duração seja zero.
2.  **`forge_claude_runner.py` - Precisão de Custo:** (Opcional) Atualizar o log de custo para refletir o modelo selecionado.
