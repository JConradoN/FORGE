# TASK — Code Review + Implementação: FORGE Scripts

## Entregáveis obrigatórios (TODOS são exigidos)

| # | Arquivo | Conteúdo mínimo |
|---|---------|-----------------|
| 1 | `code_review.md` | ≥ 3 problemas por arquivo, com localização, impacto e correção |
| 2 | `plano_correcoes.md` | Todos os problemas priorizados em Alta / Média / Baixa |
| 3 | `quality_report.md` | Tabela antes/depois + métricas + checklist de pendências |

**Crie os 3 arquivos. A tarefa não está concluída enquanto qualquer um deles estiver faltando.**

---

## Contexto

O diretório `forge-scripts/` contém o código-fonte do framework FORGE
(Framework for Open Real-world Generic Evaluation), um benchmark de agentes LLM.
São 4 arquivos Python (~1600 linhas) em estado funcional mas sem revisão formal.

---

## Etapa 1 — Code Review → `code_review.md`

Leia todos os 4 arquivos:
- `forge-scripts/forge_runner.py`          — runner principal, avaliação automática, ferramentas
- `forge-scripts/forge_claude_runner.py`   — provider Claude (API Anthropic)
- `forge-scripts/forge_mock_server.py`     — servidor HTTP de fixtures
- `forge-scripts/forge_telegram_runner.py` — provider Telegram semi-manual

Para cada arquivo, identifique **no mínimo 3 problemas reais**. Documente em `code_review.md`:

```
# Code Review — FORGE Scripts

## Sumário
<quantos problemas por arquivo, visão geral por categoria>

## forge_runner.py
### Problema 1
- **Categoria:** Qualidade / Robustez / Segurança / Performance / Testabilidade
- **Localização:** linha X, função Y
- **Descrição:** <o que está errado>
- **Impacto:** <o que pode quebrar>
- **Prioridade:** Alta / Média / Baixa
- **Correção proposta:** <como corrigir, específico e implementável>

(mínimo 3 problemas por arquivo)

## forge_claude_runner.py
...
## forge_mock_server.py
...
## forge_telegram_runner.py
...
```

---

## Etapa 2 — Plano de Correções → `plano_correcoes.md`

Gere `plano_correcoes.md` consolidando todos os problemas por prioridade:

- **Alta:** impacta comportamento ou pode causar bugs em produção → implementar agora
- **Média:** degradação de qualidade, manutenção difícil → planejar
- **Baixa:** estilo, convenções, melhorias menores → registrar

---

## Etapa 3 — Implementação

Implemente as correções de **Alta** prioridade nos arquivos dentro de `forge-scripts/`.

Regras:
- Não altere a interface pública (nomes de funções exportadas, parâmetros)
- Não adicione dependências externas além das já importadas
- Cada correção deve ser minimamente invasiva

---

## Etapa 4 — Relatório de Qualidade → `quality_report.md`

**Este arquivo é obrigatório.** Gere `quality_report.md` com:

```
# Quality Report — FORGE Scripts

## Resumo
- Total de problemas encontrados: N
- Problemas de Alta prioridade: X (Y corrigidos)
- Problemas de Média prioridade: X
- Problemas de Baixa prioridade: X

## Status por arquivo

| Arquivo | Problemas | Alta | Corrigidos | Linhas alteradas |
|---------|-----------|------|------------|-----------------|
| forge_runner.py | N | X | Y | Z |
| forge_claude_runner.py | N | X | Y | Z |
| forge_mock_server.py | N | X | Y | Z |
| forge_telegram_runner.py | N | X | Y | Z |

## Checklist de pendências (Média e Baixa)
- [ ] <item não implementado>
- [ ] <item não implementado>

## Conclusão
<avaliação geral do estado do código antes e depois>
```

---

## Conclusão

Ao finalizar **todas as 4 etapas** e confirmar que os 3 arquivos existem no diretório, responda:

```
REVISÃO CONCLUÍDA
```
