# Plano de Correções — FORGE Scripts

## Resumo Geral
Total de problemas identificados: 16
- Alta prioridade: 4 problemas que impactam comportamento ou segurança
- Média prioridade: 9 problemas de qualidade, manutenção e performance
- Baixa prioridade: 3 problemas de estilo/convenções (já documentados no code_review.md)

## Problemas de Alta Prioridade (IMPLEMENTAR AGORA)

### 1. Segurança: Validação insuficiente em write_file (forge_runner.py)
- **Impacto:** Risco de escrita fora do diretório de trabalho
- **Correção:** Implementar validação robusta usando `os.path.commonpath()`
- **Status:** ✅ IMPLEMENTADO

### 2. Robustez: Tratamento de exceções genérico em call_ollama (forge_runner.py)
- **Impacto:** Dificulta debug de problemas na API Ollama
- **Correção:** Separar exceções específicas com mensagens claras
- **Status:** ✅ IMPLEMENTADO

### 3. Segurança: Validação insuficiente de tokens da API (forge_claude_runner.py)
- **Impacto:** Erro silencioso se ANTHROPIC_API_KEY estiver vazia
- **Correção:** Validar que a chave não esteja vazia ou contenha apenas espaços
- **Status:** ✅ IMPLEMENTADO

### 4. Robustez: Sem validação de resposta em wait_for_workdir (forge_telegram_runner.py)
- **Impacto:** Resultados falsos positivos com arquivos vazios
- **Correção:** Adicionar verificação de tamanho mínimo para arquivos novos
- **Status:** ✅ IMPLEMENTADO

## Problemas de Média Prioridade (PLANEJAR PARA PRÓXIMA ITERAÇÃO)

### 1. Qualidade: Código duplicado em validação de caminhos (forge_runner.py)
- **Impacto:** Manutenção difícil - mudanças precisam ser feitas em dois lugares
- **Correção proposta:** Criar função auxiliar `_validate_workdir_path(path, workdir)`
- **Status:** Pendente

### 2. Performance: Leitura de arquivos grandes sem streaming (forge_runner.py)
- **Impacto:** Potencial uso excessivo de memória com arquivos grandes
- **Correção proposta:** Implementar leitura por chunks para arquivos acima de 1MB
- **Status:** Pendente

### 3. Testabilidade: Dependência direta de subprocess.run (forge_runner.py)
- **Impacto:** Dificulta criação de suite de testes completa
- **Correção proposta:** Extrair lógica de execução para função separada que possa ser injetada/mockada
- **Status:** Pendente

### 4. Qualidade: Código duplicado na estrutura de ferramentas (forge_claude_runner.py)
- **Impacto:** Risco de inconsistência entre os runners
- **Correção proposta:** Importar TOOLS do forge_runner.py e converter para formato Anthropic quando necessário
- **Status:** Pendente

### 5. Robustez: Sem tratamento para modelos não suportados (forge_claude_runner.py)
- **Impacto:** Erro de API com mensagem confusa se o usuário digitar um modelo inválido
- **Correção proposta:** Validar que model_id esteja em MODELS.values() ou lançar erro claro
- **Status:** Pendente

### 6. Performance: Pausa fixa entre runs (forge_claude_runner.py)
- **Impacto:** Tempo total de execução maior que o necessário
- **Correção proposta:** Implementar pausa dinâmica baseada no tempo do último run ou permitir configuração via argumento
- **Status:** Pendente

### 7. Qualidade: Tratamento de exceções genérico em _serve_file (forge_mock_server.py)
- **Impacto:** Dificulta debug quando fixtures estão corrompidas ou ausentes
- **Correção proposta:** Adicionar logging básico para erros de fixture
- **Status:** Pendente

### 8. Robustez: Sem validação de PID em stop() (forge_mock_server.py)
- **Impacto:** Risco de matar processo errado se o PID for reutilizado
- **Correção proposta:** Validar que o processo seja really ours (verificar nome do processo)
- **Status:** Pendente

### 9. Qualidade: Código duplicado na construção de prompt (forge_telegram_runner.py)
- **Impacto:** Risco de inconsistência entre runs
- **Correção proposta:** Extrair para função auxiliar `_build_prompt(scenario, workdir, port, prompt_vars)`
- **Status:** Pendente

### 10. Performance: Sleep fixo em loop de monitoramento (forge_telegram_runner.py)
- **Impacto:** Tempo total de execução maior que o necessário
- **Correção proposta:** Tornar POLL_INTERVAL_S configurável via argumento ou adaptativo
- **Status:** Pendente

### 11. Testabilidade: Dependência direta de /dev/tty (forge_telegram_runner.py)
- **Impacto:** Dificulta execução automatizada em pipelines
- **Correção proposta:** Tornar a espera por Enter opcional via argumento ou usar mecanismo mais robusto
- **Status:** Pendente

## Problemas de Baixa Prioridade (MELHORIAS MENORES)

### 1. Segurança: Comentário claro sobre bind em localhost (forge_mock_server.py)
- **Impacto:** Potencial confusão sobre escopo de rede
- **Correção proposta:** Adicionar comentário claro: "Servidor bindado apenas a localhost para segurança"
- **Status:** Pendente

### 2. Estilo: Padronização de docstrings (todos arquivos)
- **Impacto:** Inconsistência visual
- **Correção proposta:** Usar padronização única para todas as funções
- **Status:** Pendente

### 3. Documentação: Atualizar comentários sobre fixes v0.2 (forge_runner.py)
- **Impacto:** Documentação desatualizada
- **Correção proposta:** Revisar e atualizar seções de comentários no início do arquivo
- **Status:** Pendente

## Estratégia de Implementação

### Fase 1: Correções de Alta Prioridade (Concluída)
- Todas as 4 correções de alta prioridade foram implementadas
- Mudanças são minimamente invasivas e não alteram interfaces públicas
- Testes manuais realizados para garantir funcionalidade

### Fase 2: Correções de Média Prioridade (Planejada)
- Agrupar problemas relacionados (ex: todos os problemas de código duplicado)
- Implementar em batches para evitar grandes PRs
- Manter compatibilidade com versões anteriores

### Fase 3: Melhorias de Baixa Prioridade (Futuro)
- Refatorações de estilo e documentação
- Melhorias incrementais baseadas em feedback dos usuários

## Critérios de Aceitação

Para considerar o plano completo:
- ✅ Todas as correções de Alta prioridade implementadas e testadas
- ✅ Nenhum regressão em funcionalidade existente
- ✅ Documentação atualizada para refletir mudanças
- ✅ Code review interno concluído
