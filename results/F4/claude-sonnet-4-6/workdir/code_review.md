# Code Review — buggy-module

> Revisão estática e dinâmica dos arquivos `cache.py`, `retry.py` e `logger.py`.
> Total de bugs encontrados: **10**

---

## cache.py

### Bug 1 — `get()`: ausência de verificação de existência da chave
| Campo | Detalhe |
|---|---|
| **Localização** | `cache.py`, método `get()`, linha 18 |
| **Descrição** | O método acessa `self.timestamps[key]` sem verificar se `key` existe no dicionário. |
| **Impacto** | `KeyError` em qualquer chamada `get()` com chave inexistente — comportamento esperado de um cache é retornar `None`. |
| **Correção proposta** | Adicionar guarda `if key not in self.store: return None` antes de acessar os dicionários. |

---

### Bug 2 — `delete()`: entrada em `timestamps` não é removida (memory leak)
| Campo | Detalhe |
|---|---|
| **Localização** | `cache.py`, método `delete()`, linha 25 |
| **Descrição** | O método remove `self.store[key]` mas esquece de remover `self.timestamps[key]`. |
| **Impacto** | Vazamento de memória progressivo; `timestamps` cresce indefinidamente. Além disso, `size()` pode reportar contagem incorreta caso a lógica de tamanho evolua para usar `timestamps`. |
| **Correção proposta** | Adicionar `del self.timestamps[key]` junto ao `del self.store[key]`. |

---

### Bug 3 — `size()`: conta entradas expiradas não despejadas
| Campo | Detalhe |
|---|---|
| **Localização** | `cache.py`, método `size()`, linha 29 |
| **Descrição** | `len(self.store)` inclui entradas cujo TTL já venceu mas que ainda não foram eviccionadas (lazy eviction). |
| **Impacto** | O tamanho reportado é maior do que o número real de entradas válidas, levando a decisões erradas em código que usa `size()` para controle de capacidade. |
| **Correção proposta** | Calcular o tamanho contando apenas chaves cujo `timestamp` ainda está dentro do TTL, espelhando a lógica de `get_all_valid()`. |

---

### Bug 4 — `get_all_valid()`: operador `<=` expira entradas prematuramente
| Campo | Detalhe |
|---|---|
| **Localização** | `cache.py`, método `get_all_valid()`, linha 35 |
| **Descrição** | A condição `now - self.timestamps[key] <= self.ttl` exclui a entrada quando a diferença é **exatamente igual** ao TTL, pois a lógica foi invertida (deveria incluir o caso de igualdade). |
| **Impacto** | Entradas ainda válidas (no exato limite do TTL) são descartadas, causando reprocessamento desnecessário e resultados inconsistentes com `get()`. |
| **Correção proposta** | Alterar para `now - self.timestamps[key] < self.ttl` — a entrada expira apenas quando a diferença **supera** o TTL (mesmo critério de `get()`). |

---

## retry.py

### Bug 5 — `retry()` decorator: condição do loop corta a última tentativa
| Campo | Detalhe |
|---|---|
| **Localização** | `retry.py`, `wrapper()`, linha 16 |
| **Descrição** | O loop usa `while attempt < max_attempts - 1`, fazendo com que `max_attempts=3` execute apenas 2 iterações (tentativas 0 e 1). |
| **Impacto** | O número real de tentativas é sempre `max_attempts - 1`; funções que falham nas primeiras tentativas nunca recebem sua última chance. |
| **Correção proposta** | Alterar para `while attempt < max_attempts`. |

---

### Bug 6 — `retry()` decorator: `time.sleep()` é chamado antes de verificar esgotamento
| Campo | Detalhe |
|---|---|
| **Localização** | `retry.py`, `wrapper()`, linhas 21-24 |
| **Descrição** | O incremento de `attempt` e o `time.sleep()` ocorrem **antes** da verificação `if attempt >= max_attempts: raise`, causando uma espera desnecessária após a última falha. |
| **Impacto** | Latência extra no caminho de erro; em testes automatizados ou contextos de tempo-real, o atraso espúrio causa falhas de timeout e degrada a experiência. |
| **Correção proposta** | Incrementar `attempt`, verificar se esgotou (`raise` imediato) e só então chamar `time.sleep()` caso ainda haja tentativas restantes. |

---

### Bug 7 — `retry_call()`: re-levanta `Exception` genérica em vez da exceção original
| Campo | Detalhe |
|---|---|
| **Localização** | `retry.py`, função `retry_call()`, linha 45 |
| **Descrição** | Após esgotar as tentativas, `raise Exception("All attempts failed")` descarta o tipo e a mensagem da exceção original capturada em `last_exc`. |
| **Impacto** | O chamador perde informação de diagnóstico (tipo real da exceção, stack trace original, mensagem). Blocos `except CustomError` nunca são ativados, quebrando tratamento de erros upstream. |
| **Correção proposta** | Substituir por `raise last_exc` para preservar a exceção original. |

---

## logger.py

### Bug 8 — `Logger.__init__()`: nível armazenado como string em vez de inteiro
| Campo | Detalhe |
|---|---|
| **Localização** | `logger.py`, `__init__()`, linha 15 |
| **Descrição** | `self.level = level` armazena a string `"INFO"` (ou qualquer nível fornecido) diretamente, sem converter para o valor inteiro correspondente via `LEVELS`. |
| **Impacto** | Causa falha em `is_enabled()` ao comparar `int >= str`, tornando o logger completamente não-funcional — nenhuma mensagem é registrada. |
| **Correção proposta** | Converter na inicialização: `self.level = LEVELS.get(level, 1)`. |

---

### Bug 9 — `is_enabled()`: comparação `int >= str` sempre falha
| Campo | Detalhe |
|---|---|
| **Localização** | `logger.py`, método `is_enabled()`, linha 19 |
| **Descrição** | Consequência direta do Bug 8: `LEVELS.get(level_name, -1) >= self.level` compara um `int` com uma `str`, lançando `TypeError` no Python 3. |
| **Impacto** | Exceção `TypeError` em qualquer chamada de log; nenhuma mensagem jamais é registrada. |
| **Correção proposta** | Corrigido automaticamente pela correção do Bug 8 (ambos os operandos passam a ser `int`). |

---

### Bug 10 — `get_records()`: direção de comparação invertida filtra registros errados
| Campo | Detalhe |
|---|---|
| **Localização** | `logger.py`, método `get_records()`, linha 40 |
| **Descrição** | A condição `LEVELS[r["level"]] <= min_val` retorna registros com nível **menor ou igual** ao mínimo solicitado, ou seja, retorna os registros de **baixa** severidade em vez dos de **alta**. |
| **Impacto** | `get_records(min_level="ERROR")` retorna `DEBUG` e `INFO` em vez de `ERROR` e `CRITICAL`, invertendo completamente o comportamento esperado de filtragem de log. |
| **Correção proposta** | Alterar para `LEVELS[r["level"]] >= min_val` para retornar apenas registros com severidade maior ou igual ao mínimo. |

---

## Resumo

| # | Arquivo | Método / Linha | Categoria | Severidade |
|---|---|---|---|---|
| 1 | `cache.py` | `get()` | KeyError / ausência de guarda | 🔴 Alta |
| 2 | `cache.py` | `delete()` | Memory leak | 🟠 Média |
| 3 | `cache.py` | `size()` | Lógica incorreta | 🟡 Baixa |
| 4 | `cache.py` | `get_all_valid()` | Operador errado (off-by-one) | 🟠 Média |
| 5 | `retry.py` | `wrapper()` | Off-by-one no loop | 🔴 Alta |
| 6 | `retry.py` | `wrapper()` | Sleep espúrio na última falha | 🟠 Média |
| 7 | `retry.py` | `retry_call()` | Exceção original descartada | 🔴 Alta |
| 8 | `logger.py` | `__init__()` | Tipo errado armazenado | 🔴 Alta |
| 9 | `logger.py` | `is_enabled()` | TypeError por comparação int/str | 🔴 Alta |
| 10 | `logger.py` | `get_records()` | Comparação invertida | 🔴 Alta |
