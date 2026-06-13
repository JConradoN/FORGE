# Correções nos Arquivos

## 1. `buggy-module/cache.py`

### BUG-1: `get` retorna o dicionário inteiro
Correção:
```python
entry = self._store.get(key)
if entry is not None:
    return entry["value"]
return None
```

### BUG-2: `delete` realiza remoção dupla
Correção:
```python
if key in self._store:
    del self._store[key]
```

## 2. `buggy-module/retry.py`

### BUG: Lógica invertida
Correção:
```python
if attempt == max_attempts - 1:
    raise last_exc
```

## 3. `buggy-module/logger.py`

### BUG-1: `Callable` não importado
Correção:
```python
from typing import Callable
```

### BUG-2: `msg.format(msg)`
Correção:
```python
msg = f"calling {func.__name__}"
```
