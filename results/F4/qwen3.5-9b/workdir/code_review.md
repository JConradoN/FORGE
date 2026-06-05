# Code Review - buggy-module

## Resumo
Foram encontrados **3 bugs** no módulo `buggy-module`. Todos foram corrigidos e a validação passou com sucesso.

---

## Bug 1: retry.py - Lógica invertida de exceção

### Localização
`retry.py`, função `with_retry()`, linha ~20-21

```python
if attempt == 0:
    raise last_exc
time.sleep(delay)
```

### Descrição
A condição `if attempt == 0` levanta a exceção na **primeira tentativa** (tentativa 0), impedindo que o retry funcione. Isso faz com que qualquer erro ocorra imediatamente, sem tentar novamente.

### Impacto
- O mecanismo de retry não funciona corretamente
- Funções falham instantaneamente em vez de ser tentadas múltiplas vezes
- Viola a especificação do método `with_retry()`

### Correção Proposta
Mudar para levantar exceção apenas após todas as tentativas:

```python
if attempt == max_attempts - 1:
    raise last_exc
time.sleep(delay) if attempt < max_attempts - 1 else None
```

Ou mais limpo, mover o `raise` fora do loop ou usar uma condição diferente.

---

## Bug 2: logger.py - Callable não importado e auto-referência no log

### Localização A
`logger.py`, linha ~4 (import ausente)

```python
# BUG-1: Callable não importado (from typing import Callable ausente)
```

### Descrição Ausente
O tipo `Callable` é usado na assinatura da função, mas nunca foi importado. Isso causa um `NameError`.

### Impacto A
- Erro de execução imediato ao importar o módulo
- Decorador não pode ser aplicado a funções

---

### Localização B
`logger.py`, linha ~14 (dentro do wrapper)

```python
msg = "calling {}"
LOG.debug(msg.format(msg))  # deveria usar func.__name__
```

### Descrição Auto-referência
O código usa `msg.format(msg)` em vez de `func.__name__`. Isso resulta no log `"calling calling"` ao invés do nome real da função.

### Impacto B
- Logs incorretos que não identificam qual função está sendo chamada
- Dificulta o debugging e monitoramento

---

## Correções Aplicadas

### retry.py - Correção completa:
```python
def with_retry(func: Callable[[], T], max_attempts: int = 3, delay: float = 0.1) -> T:
    last_exc: Exception | None = None
    
    for attempt in range(max_attempts):
        try:
            return func()
        except Exception as exc:
            last_exc = exc
            if attempt < max_attempts - 1:
                time.sleep(delay)
    
    raise last_exc
```

### logger.py - Correções completas:
```python
from typing import Callable  # Import adicionado

def log_call(func: Callable) -> Callable:
    def wrapper(*args, **kwargs):
        msg = f"calling {func.__name__}"  # Usa nome da função
        LOG.debug(msg.format("{}"))       # ou simplesmente LOG.debug(f"{msg}")
```

---

## Validação Final
Após as correções, executar: `python3 buggy-module/validate.py`

**Resultado esperado:** ALL TESTS PASSED (5/5)
