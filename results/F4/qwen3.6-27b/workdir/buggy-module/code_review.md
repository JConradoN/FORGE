# Code Review — buggy-module

## cache.py

### Bug 1 — `Cache.get()` retorna dict inteiro ao invés do valor
- **Localização:** linha 20, método `get()`
- **Descrição:** `self._store.get(key)` retorna o objeto `CacheEntry` (um dict com `key`, `value`, `ttl`) ao invés de apenas o campo `value`.
- **Impacto:** O consumidor do cache recebe um dict em vez do valor armazenado, quebrando contratos e causando erros de tipo.
- **Correção proposta:** Retornar `self._store.get(key, {}).get("value")` para devolver apenas o valor ou `None` se a chave não existir.

### Bug 2 — `Cache.delete()` faz double-delete
- **Localização:** linhas 23–25, método `delete()`
- **Descrição:** O método chama `self._store.popitem()` (remove o último item inserido, independente da chave) e depois `del self._store[key]`. Se a chave não for o último item, `popitem()` remove outro elemento e `del` levanta `KeyError`. Se for o último, o item é removido duas vezes.
- **Impacto:** Dados incorretos são removidos do cache; `KeyError` é levantado em casos comuns.
- **Correção proposta:** Substituir por `self._store.pop(key, None)` — remove apenas a chave desejada sem levantar exceção se não existir.

---

## retry.py

### Bug 3 — Lógica de retry invertida: levanta na primeira tentativa
- **Localização:** linha 24, condição `if attempt == 0: raise last_exc`
- **Descrição:** A condição verifica `attempt == 0`, ou seja, na **primeira** tentativa (índice 0) já levanta a exceção. Isso impede que qualquer retry aconteça — a função falha imediatamente na primeira exceção.
- **Impacto:** O mecanismo de retry é completamente inútil; nenhuma segunda tentativa ocorre.
- **Correção proposta:** Remover o bloco `if attempt == 0: raise last_exc` e deixar apenas `time.sleep(delay)` antes da próxima iteração. A exceção final já é levantada após o loop (`raise last_exc`).

---

## logger.py

### Bug 4 — `Callable` não importado
- **Localização:** linha 12, assinatura `def log_call(func: Callable) -> Callable`
- **Descrição:** O nome `Callable` é usado como anotação de tipo mas nunca foi importado (`from typing import Callable` está ausente).
- **Impacto:** `NameError` ao importar o módulo — o decorador não pode ser usado.
- **Correção proposta:** Adicionar `from typing import Callable` no topo do arquivo.

### Bug 5 — `msg.format(msg)` usa string format como argumento
- **Localização:** linha 18, dentro de `wrapper()`
- **Descrição:** `msg = "calling {}"` e depois `LOG.debug(msg.format(msg))` passa a própria string `"calling {}"` como argumento, resultando no log `"calling calling {}"`. O nome da função nunca é registrado.
- **Impacto:** Logs inúteis que não identificam qual função está sendo chamada.
- **Correção proposta:** Usar `msg.format(func.__name__)` para inserir o nome real da função decorada.
