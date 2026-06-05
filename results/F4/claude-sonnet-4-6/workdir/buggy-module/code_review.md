# Code Review — buggy-module

> Revisão estática + análise de contrato com `validate.py`.  
> Total de bugs encontrados: **7**

---

## cache.py

### Bug 1 — TTL calculado com operador errado (`+` em vez de `-`)

| Campo | Detalhe |
|-------|---------|
| **Localização** | `cache.py`, método `get()`, linha `if time.time() + ts > self._ttl` |
| **Descrição** | O tempo decorrido desde a inserção deve ser `time.time() - ts` (tempo atual menos timestamp de gravação). Usando `+`, a soma de dois timestamps Unix (≈ 3,4 × 10⁹) é sempre maior que qualquer TTL razoável, fazendo **todo item expirar imediatamente** na primeira leitura. |
| **Impacto** | `get()` nunca retorna um valor válido; o cache se comporta como um `/dev/null`. |
| **Correção** | `if time.time() - ts > self._ttl:` |

---

### Bug 2 — `set()` não aceita TTL por item

| Campo | Detalhe |
|-------|---------|
| **Localização** | `cache.py`, assinatura `def set(self, key, value)` |
| **Descrição** | O validador chama `c.set("k1", "hello", ttl=30)`, mas a assinatura não declara o parâmetro `ttl`, gerando `TypeError`. Cada entrada deve poder sobrescrever o TTL global do cache. |
| **Impacto** | `TypeError` em qualquer chamada com TTL explícito; os testes 1 e 2 falham completamente. |
| **Correção** | `def set(self, key, value, ttl=None)` — armazenar o TTL efetivo junto com o valor. |

---

### Bug 3 — `delete()` levanta `KeyError` para chaves inexistentes

| Campo | Detalhe |
|-------|---------|
| **Localização** | `cache.py`, método `delete()`, instrução `del self._store[key]` |
| **Descrição** | `dict.__delitem__` lança `KeyError` quando a chave não está presente. A operação de remoção deve ser idempotente — remover uma chave que não existe é uma no-op válida. |
| **Impacto** | Qualquer código que chame `delete()` em chave ausente (por exemplo após TTL expirado) quebra com exceção não tratada. |
| **Correção** | `self._store.pop(key, None)` |

---

### Bug 4 — `size()` retorna o dicionário inteiro em vez de um `int`

| Campo | Detalhe |
|-------|---------|
| **Localização** | `cache.py`, método `size()`, instrução `return self._store` |
| **Descrição** | O método deve devolver o número de entradas vivas no cache, mas retorna o objeto `dict`. Qualquer asserção `== 2` passaria acidentalmente em Python apenas se o dict fosse avaliado como booleano, mas comparações `== int` falham. |
| **Impacto** | `assert c.size() == 2` sempre falha; tipagem errada pode mascarar outros erros. |
| **Correção** | `return len(self._store)` |

---

## retry.py

### Bug 5 — Interface pública ausente: `with_retry` não existe

| Campo | Detalhe |
|-------|---------|
| **Localização** | `retry.py` — ausência da função `with_retry` |
| **Descrição** | O validador importa e usa `with_retry(fn, max_attempts, delay)` — uma função de ordem superior que recebe a função-alvo como argumento. O módulo só expõe um decorator `@retry`, que é uma interface diferente e incompatível. |
| **Impacto** | `ImportError` / `NameError`; testes 3 e 4 falham completamente. |
| **Correção** | Implementar `def with_retry(fn, max_attempts=3, delay=0.1, exceptions=(Exception,))` com loop de tentativas. |

---

### Bug 6 — Sintaxe inválida: atribuição (`=`) no `while` em vez de comparação (`<`)

| Campo | Detalhe |
|-------|---------|
| **Localização** | `retry.py`, `wrapper()`, linha `while attempt = max_attempts:` |
| **Descrição** | `=` é atribuição e é ilegal como condição de `while` em Python (ao contrário de C). Deveria ser `while attempt < max_attempts:`. O arquivo sequer importa com esse erro — `SyntaxError` em tempo de carga. |
| **Impacto** | O módulo inteiro falha ao importar; todos os testes que dependem de `retry.py` quebram. |
| **Correção** | `while attempt < max_attempts:` |

---

## logger.py

### Bug 7 — `log_call` não existe; módulo usa classe em vez de decorator funcional

| Campo | Detalhe |
|-------|---------|
| **Localização** | `logger.py` — ausência da função `log_call` |
| **Descrição** | O validador importa `log_call` e o aplica como decorator (`@log_call`). O módulo só define a classe `Logger`, que é uma interface completamente diferente. Além disso, o validador verifica que o nome da função decorada apareça nos logs via `logging` padrão do Python (não `print`). |
| **Impacto** | `ImportError`; teste 5 falha completamente. |
| **Correção** | Implementar `log_call` como decorator que usa `logging.getLogger("logger")` para registrar entrada e saída da função decorada, preservando `__name__` via `functools.wraps`. |

---

## Resumo

| # | Arquivo | Tipo de Bug | Severidade |
|---|---------|-------------|------------|
| 1 | cache.py | Lógica — operador errado no cálculo de TTL | Alta |
| 2 | cache.py | Interface — parâmetro `ttl` ausente em `set()` | Alta |
| 3 | cache.py | Robustez — `KeyError` não tratado em `delete()` | Média |
| 4 | cache.py | Lógica — `size()` retorna `dict` em vez de `int` | Média |
| 5 | retry.py | Interface — função `with_retry` não implementada | Alta |
| 6 | retry.py | Sintaxe — `=` em vez de `<` no `while` | Crítica |
| 7 | logger.py | Interface — decorator `log_call` não implementado | Alta |
