# TASK — Code Review + Implementação: FORGE Scripts

## Contexto
O diretório `forge-scripts/` contém o código-fonte do framework FORGE
(Framework for Open Real-world Generic Evaluation), um benchmark de agentes LLM.
São 4 arquivos Python (~1600 linhas) em estado funcional mas sem revisão formal.

## Etapa 1 — Code Review

Leia todos os arquivos:
- `forge-scripts/forge_runner.py`        — runner principal, avaliação automática, ferramentas
- `forge-scripts/forge_claude_runner.py` — provider Claude (API Anthropic)
- `forge-scripts/forge_mock_server.py`   — servidor HTTP de fixtures
- `forge-scripts/forge_telegram_runner.py` — provider Telegram semi-manual

Para cada arquivo, documente os problemas encontrados em `code_review.md`:

```markdown
# Code Review — FORGE Scripts

## Sumário
<quantos problemas, visão geral por categoria>

## forge_runner.py
### Problema <N>
- **Categoria:** Qualidade / Robustez / Segurança / Performance / Testabilidade
- **Localização:** linha X, função Y
- **Descrição:** <o que está errado ou pode melhorar>
- **Impacto:** <o que pode quebrar ou dificultar manutenção>
- **Prioridade:** Alta / Média / Baixa
- **Correção proposta:** <como corrigir>

## forge_claude_runner.py
...
## forge_mock_server.py
...
## forge_telegram_runner.py
...
```

## Etapa 2 — Plano de Correções

Gere `plano_correcoes.md` priorizando as correções:
- **Alta:** impacta comportamento ou pode causar bugs em produção
- **Média:** degradação de qualidade, manutenção difícil
- **Baixa:** estilo, convenções, melhorias menores

## Etapa 3 — Implementação

Implemente as correções de **Alta** prioridade nos arquivos originais.

Regras:
- Não altere a interface pública (nomes de funções exportadas, parâmetros)
- Não adicione dependências externas além das já importadas
- Cada correção deve ser minimamente invasiva

## Etapa 4 — Relatório de Qualidade

Gere `quality_report.md` com:
- Tabela de arquivos: status antes/depois, bugs corrigidos, linhas alteradas
- Métricas: total de problemas encontrados, % corrigidos
- Checklist de itens não implementados (Média e Baixa prioridade)

## Conclusão

Ao finalizar todas as etapas, responda com:
```
REVISÃO CONCLUÍDA: <N> problemas encontrados, <M> corrigidos, relatórios salvos
```
