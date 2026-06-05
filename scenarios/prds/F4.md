# TASK — Code Review + Bug Fix

## Contexto
O diretório `buggy-module/` contém um módulo Python com bugs introduzidos durante
uma geração automática de código. Os bugs quebram o comportamento esperado.

## Etapa 1 — Code Review
Leia os três arquivos:
- `buggy-module/cache.py`
- `buggy-module/retry.py`
- `buggy-module/logger.py`

Para cada arquivo, identifique os bugs. Documente em `code_review.md`:

```
# Code Review — buggy-module

## Sumário
<quantos bugs foram encontrados, visão geral>

## cache.py
### Bug <N>
- **Localização:** linha X
- **Descrição:** <o que está errado>
- **Impacto:** <o que quebra>
- **Correção:** <como corrigir>

## retry.py
...

## logger.py
...
```

## Etapa 2 — Implementação
Corrija **todos** os bugs identificados nos três arquivos.

Regras:
- Não adicione dependências externas (sem pip install)
- Mantenha a interface pública de cada classe/função inalterada
- Não altere `validate.py`

## Etapa 3 — Validação
Execute o script de validação:
```bash
python3 buggy-module/validate.py
```

O script testa cada correção. Saída esperada:
```
ALL TESTS PASSED (5/5)
```

Se algum teste falhar, leia a mensagem de erro, corrija e rode novamente.

## Conclusão
Quando `validate.py` retornar `ALL TESTS PASSED`, responda com:
```
REVISÃO CONCLUÍDA: <N> bugs corrigidos, validação OK
```
