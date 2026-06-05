# Plano de Correções — FORGE Scripts

## Visão Geral
- **Total de problemas identificados:** 15
- **Correções de Alta prioridade (impactam segurança/robustez):** 3
- **Correções de Média prioridade (qualidade/testabilidade):** 8  
- **Correções de Baixa prioridade (melhorias menores):** 4

---

## Priorização por Categoria e Impacto

### Alta — Crítico para produção ou pode causar falhas imediatas
1. `forge_runner.py`: Problema 1 & 2 — Variável `_PROTECTED_FILES` não definida antes do uso
   - **Impacto:** Runner falha ao tentar proteger arquivos de fixture importantes (`validate.py`, `TASK.md`)
   - **Correção necessária:** Mover declaração para topo do arquivo
   
2. `forge_runner.py`: Problema 3 — Falta de tratamento adequado em `_kill_port` e limpeza pós-run
   - **Impacto:** Servidores iniciados durante runs podem continuar rodando após interrupções, causando vazamento de recursos
   
### Média — Degradação significativa ou manutenção difícil
1. `forge_runner.py`: Problema 4 — Função `_resolve` definida dentro do loop (má prática)
   - **Impacto:** Código difícil de manter e testar; overhead desnecessário em cenários com muitos checks
   
2. `forge_claude_runner.py`: Problema 7 — Falta de tratamento ao carregar API key ausente
   - **Impacto:** Runner falha abruptamente sem mensagens claras sobre como configurar credenciais
   
3. `forge_mock_server.py`: Problema 11 — Falta de tratamento de erro ao carregar fixture JSON corrompido/ausente
   - **Impacto:** Cenários que dependem desses fixtures podem falhar silenciosamente com respostas incompletas

4. `forge_telegram_runner.py`: Problema 13 — `_workdir_snapshot` pode falhar silenciosamente com arquivos problemáticos
   - **Impacto:** Monitoramento do workdir para detectar mudanças de output pode parar abruptamente
   
5. `forge_claude_runner.py`: Problema 9 — Falta de verificação se porta foi liberada antes do próximo run
   - **Impacto:** Conflitos de porta entre runs consecutivos podem causar falhas silenciosas

6. `forge_telegram_runner.py`: Problema 14 — Limpeza inadequada do workdir (ignora subdiretórios)
   - **Impacto:** Acúmulo de lixo e conflitos em cenários complexos com estrutura de diretória profunda
   
7. `forge_claude_runner.py`: Problema 6 — Importação circular potencial entre módulos FORGE
   - **Impacto:** Refatorações futuras podem quebrar dependências mútuas não documentadas

8. `forge_mock_server.py`: Problema 12 — Falta de logging estruturado em operações críticas
   - **Impacto:** Dificuldade para troubleshooting e auditoria sem logs detalhados

### Baixa — Melhorias menores, estilo ou convenções
- Podem ser implementadas após as correções de Alta/Média serem concluídas.

---

## Ordem Recomendada de Implementação

1. **Passo 1 (Crítico):** Corrigir problemas de Alta prioridade em `forge_runner.py`
   - Mover `_PROTECTED_FILES` para topo do arquivo
   
2. **Passo 2:** Melhorar tratamento de erro no mock server (`forge_mock_server.py`)
   
3. **Passo 3:** Adicionar logging estruturado e melhorar limpeza entre runs

4. **Passo 4:** Refatorar funções definidas dentro de loops para melhor testabilidade
   
5. **Passo 5:** Implementar tratamento adequado ao carregar API keys ausentes

6. **Passo 6 (Opcional):** Melhorias de logging, documentação e convenções

---

## Checklist de Verificação Pós-Correção
- [ ] Todos os problemas de Alta prioridade corrigidos?
- [ ] Testes unitários passam com as novas correções?
- [ ] Logs estruturados estão funcionando corretamente?
- [ ] Limpeza entre runs funciona em cenários complexos?
- [ ] Tratamento de erro para fixtures ausentes/inválidos está presente?

---

## Notas Adicionais
- **Não alterar interface pública:** Manter nomes de funções exportadas e parâmetros existentes.
- **Sem novas dependências:** Usar apenas bibliotecas já importadas (ex: `logging` padrão do Python).
- **Correções minimamente invasivas:** Cada fix deve ser o menor possível para resolver o problema específico.
