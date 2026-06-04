# FORGE — Sistema de Scoring

## Escala: 0–4 (igual ao ABS e LOP)

## 4 dimensões de avaliação

| Dimensão       | Peso | Quem avalia               | O que mede                                         |
|----------------|------|---------------------------|---------------------------------------------------|
| AUTO           | 30%  | forge_runner.py           | Critérios objetivos: arquivo existe, servidor responde, ferramenta chamada, etc. |
| LLM-JUDGE      | 30%  | gemma4:26b via forge_judge.py | Qualidade do output segundo rubrica por cenário |
| CLAUDE         | 20%  | Claude Code (manual/script)   | Completude técnica, corretude, edge cases         |
| HUMAN          | 20%  | Conrado                   | Estética, usabilidade, "faz sentido usar isso?"    |

## Score composto

```
composite = (auto_norm×0.30 + llm_judge×0.30 + claude×0.20 + human×0.20)
           / total_pesos_disponíveis
```

`auto_norm` = auto_pct / 100 × 4 (converte % para escala 0–4)

## Rubrica por dimensão LLM-JUDGE

### F1 — Web Imobiliária
- **completeness** (0-4): A página tem todas as seções pedidas?
- **html_quality** (0-4): HTML é semântico e bem estruturado?
- **css_quality** (0-4): CSS é limpo, responsivo, tem design intencional?
- **aesthetic** (0-4): **AVALIAÇÃO HUMANA** — design parece profissional?

### F2 — Análise Web + Relatório + Claudio
- **content_extraction** (0-4): Extraiu informações relevantes da página?
- **analysis_depth** (0-4): Análise é profunda e específica ou genérica?
- **relevance_accuracy** (0-4): Classificação de relevância para o stack está correta?
- **report_structure** (0-4): Relatório tem todas as seções e é bem escrito?

### F3 — Inteligência de Mercado
- **data_accuracy** (0-4): Dados são reais e recentes (timestamp atual)?
- **trend_analysis** (0-4): Análise de tendência é baseada nos dados ou genérica?
- **recommendation** (0-4): Recomendações são específicas, coerentes e úteis?
- **completeness** (0-4): Todos os 4 ativos foram analisados com dados reais?

## Como pontuar manualmente (HUMAN)

| Nota | Critério                                                                  |
|------|---------------------------------------------------------------------------|
| 4    | Excelente — usaria em produção sem modificações                           |
| 3    | Bom — funciona, pequenos ajustes necessários                              |
| 2    | Razoável — funciona parcialmente, precisa de retrabalho significativo      |
| 1    | Tentou mas falhou na maior parte                                          |
| 0    | Não realizou ou resultado completamente incorreto                         |
