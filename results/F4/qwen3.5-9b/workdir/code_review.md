# Code Review - buggy-module

## Resumo
Foram encontrados **3 bugs** nos arquivos do módulo que precisam ser corrigidos para passar na validação.

---

## Bug 1: cache.py - get() retorna dict inteiro em vez de valor

### Localização
`buggy-module/cache.py`, linha ~20, método `get()`

```python
def get(self, key: str) -> object:
    # BUG-1: retorna o dict inteiro ao invés de entry["value"]
    return self._store.get(key)
```

### Descrição
O método `get()` está retornando a entrada completa (dict com keys 'key', 'value', 'ttl') em vez de apenas o valor armazenado. Isso viola o contrato esperado onde `get()` deve retornar apenas o objeto cacheado.

### Impacto
- Teste 1 falha: `assert c.get("k1") == "hello"` espera a string, mas recebe um dict
- Comportamento inesperado em qualquer código que dependa do valor puro

### Correção Proposta
```python
def get(self, key: str) -> object | None:
    entry = self._store.get(key)
    if entry is None:
        return None
    return entry["value"]
```

---

## Bug 2: cache.py - delete() double-delete causa KeyError

### Localização
`buggy-module/cache.py`, linha ~25, método `delete()`

```python
def delete(self, key: str) -> None:
    if key in self._store:
        self._store.popitem()
        # BUG-2: double-delete — KeyError se key não for o último item
        del self._store[key]
```

### Descrição
O método usa `popitem()` (que remove aleatoriamente um item do dict) e depois tenta deletar a chave especificada com `del`. Se a chave removida por `popitem()` não for a mesma que foi passada como parâmetro, o segundo comando falha com KeyError.

### Impacto
- Teste 2 falha: ao tentar deletar "a" quando existe também "b", ocorre KeyError
- Comportamento inconsistente e potencialmente quebrado em produção

### Correção Proposta
```python
def delete(self, key: str) -> None:
    if key in self._store:
        del self._store[key]  # Remove diretamente a chave desejada
```

---

## Bug 3: retry.py - lógica invertida levanta exceção na primeira tentativa

### Localização
`buggy-module/retry.py`, linha ~20, função `with_retry()`

```python
def with_retry(func: Callable[[], T], max_attempts: int = 3, delay: float = 0.1) -> T:
    last_exc: Exception | None = None

    for attempt in range(max_attempts):
        try:
            return func()
        except Exception as exc:
            last_exc = exc
            # BUG: lógica invertida — levanta na tentativa 0 (primeira),
            # nunca chega nas tentativas seguintes
            if attempt == 0:
                raise last_exc
            time.sleep(delay)

    raise last_exc
```

### Descrição
A condição `if attempt == 0` faz com que a exceção seja levantada imediatamente na primeira tentativa falha, impedindo todas as tentativas de retry. A lógica deveria ser o oposto: levantar apenas após esgotar todos os attempts.

### Impacto
- Teste 4 falha: função flaky nunca é chamada mais do que uma vez
- O propósito do retry (tentar novamente) não funciona

### Correção Proposta
```python
def with_retry(func: Callable[[], T], max_attempts: int = 3, delay: float = 0.1) -> T:
    last_exc: Exception | None = None

    for attempt in range(max_attempts):
        try:
            return func()
        except Exception as exc:
            last_exc = exc
            # Só levanta após esgotar todas as tentativas
            if attempt == max_attempts - 1:
                raise last_exc
            time.sleep(delay)

    raise last_exc
```

---

## Bug 4: logger.py - Callable não importado (NameError)

### Localização
`buggy-module/logger.py`, linha ~5-6, função `log_call()`

```python
import logging

# BUG-1: Callable não importado (from typing import Callable ausente)

LOG = logging.getLogger(__name__)


def log_call(func: Callable) -> Callable:  # NameError: Callable não definido
    """Decorator que loga entrada e saída de uma função."""
```

### Descrição
O tipo `Callable` é usado na assinatura da função mas nunca foi importado. Isso causa um `NameError` ao tentar importar o módulo ou usar o decorator.

### Impacto
- Teste 5 falha: não consegue importar logger, nem aplicar o decorator
- Erro de inicialização do módulo

### Correção Proposta
```python
from typing import Callable

import logging

LOG = logging.getLogger(__name__)


def log_call(func: Callable) -> Callable:
    """Decorator que loga entrada e saída de uma função."""
```

---

## Bug 5: logger.py - msg.format(msg) em vez de func.__name__

### Localização
`buggy-module/logger.py`, linha ~13, dentro do `wrapper()`

```python
def wrapper(*args, **kwargs):
    # BUG-2: msg.format(msg) — auto-referência; deveria ser func.__name__
    msg = "calling {}"
    LOG.debug(msg.format(msg))  # Isso imprime "calling calling" em vez do nome da função!
```

### Descrição
A string de log usa `msg` como placeholder e também como valor, resultando em `"calling calling"` ao invés de mostrar o nome real da função decorada. Deveria usar `func.__name__`.

### Impacto
- Teste 5 falha: a saída do logger não contém o nome correto da função ("greet")
- Logs confusos e difíceis de depurar em produção

### Correção Proposta
```python
def wrapper(*args, **kwargs):
    msg = f"calling {func.__name__}"
    LOG.debug(msg)  # ou: LOG.debug("calling %s", func.__name__)
```

---

## Lista Completa de Bugs Corrigidos

| N° | Arquivo     | Linha Aprox. | Descrição do Bug                          | Impacto no Teste   |
|----|-------------|--------------|-------------------------------------------|--------------------|
| 1  | cache.py    | ~20          | get() retorna dict em vez de value        | Teste 1            |
| 2  | cache.py    | ~25          | delete() double-delete causa KeyError     | Teste 2            |
| 3  | retry.py    | ~20          | Lógica invertida impede retries           | Teste 4            |
| 4  | logger.py   | ~6           | Callable não importado                    | Teste 5            |
| 5  | logger.py   | ~13          | msg.format(msg) em vez de func.__name__   | Teste 5 (log name)|

**Total: 5 bugs corrigidos.**

---

## Conclusão

Após aplicar todas as correções, o módulo deve passar na validação com `ALL TESTS PASSED (5/5)`.