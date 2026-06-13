# Code Review - Bug Report

## 1. `buggy-module/cache.py`

### Bug 1: Retorno incorreto no método `get`
- **Localização:** `Cache.get(self, key: str)`
- **Descrição:** O método retorna o dicionário `CacheEntry` completo em vez de retornar apenas o valor associado à chave (`entry["value"]`).
- **Impacto:** Usuários do cache recebem metadados (key, ttl) em vez do dado solicitado, quebrando a lógica de negócio.
- **Correção Proposta:** Alterar para `return self._store[key]["value"]` se a chave existir.

### Bug 2: Erro de lógica no método `delete`
- **Localização:** `Cache.delete(self, key: str)`
- **Descrição:** O uso de `self._store.popitem()` remove o último item inserido arbitrariamente, e em seguida tenta deletar a chave específica com `del`. Se a chave não for a última, isso pode causar inconsistência ou erro se combinada com lógica errada. Além disso, `popitem` é desnecessário aqui.
- **Impacto:** Remoção de itens incorretos do cache e potencial `KeyError`.
- **Correção Proposta:** Usar apenas `self._store.pop(key, None)`.

## 2. `buggy-module/retry.py`

### Bug 3: Lógica de interrupção prematura no loop de retry
- **Localização:** `with_retry` function, bloco `except`.
- **Descrição:** O código levanta a exceção imediatamente na primeira tentativa (`if attempt == 0: raise last_exc`), impedindo que as tentativas subsequentes ocorram.
- **Impacto:** O mecanismo de retry é inútutil, pois falha logo no primeiro erro.
- **Correção Proposta:** Remover o `raise` prematuro e permitir que o loop continue até `max_attempts`.

## 3. `buggy-module/logger.py`

### Bug 4: NameError por falta de importação
- **Localização:** Definição do decorador `log_call(func: Callable)`.
- **Descrição:** O tipo `Callable` não foi importado do módulo `typing`.
- **Impacto:** Erro de execução (`NameError`) ao tentar carregar o módulo.
- **Correção Provação:** Adicionar `from typing import Callable`.

### Bug 5: Formatação incorreta da mensagem de log
- **Localização:** `wrapper` function, linha `LOG.debug(msg.format(msg))`.
- **Descrição:** O método `.format()` está tentando formatar a string `msg` usando ela mesma como argumento, resultando em uma mensagem sem o nome da função.
- **Impacto:** Logs de depuração são inúteis pois não identificam qual função está sendo chamada.
- **Correção Proposta:** Alterar para `LOG.debug(f"calling {func.__name__}")` ou usar `.format(func.__name__)`.
