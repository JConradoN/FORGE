# Code Review — buggy-module

Revisão dos arquivos `cache.py`, `retry.py` e `logger.py`.
Total de bugs encontrados: **5**

---

## cache.py

### BUG-1 — `get()` retorna o `CacheEntry` inteiro em vez do valor

| Campo | Detalhe |
|---|---|
| **Localização** | `cache.py`, método `Cache.get()`, linha 22 |
| **Descrição** | `self._store.get(key)` retorna o dicionário `CacheEntry` completo `{"key": ..., "value": ..., "ttl": ...}` em vez de extrair o campo `"value"`. |
| **Impacto** | Todo consumidor de `cache.get()` recebe o envelope interno em vez do dado armazenado, corrompendo silenciosamente os dados da aplicação. |
| **Correção proposta** | Extrair o campo `"value"` da entrada: `entry = self._store.get(key); return entry["value"] if entry is not None else None` |

---

### BUG-2 — `delete()` usa `popitem()` + `del` causando `KeyError`

| Campo | Detalhe |
|---|---|
| **Localização** | `cache.py`, método `Cache.delete()`, linhas 26-28 |
| **Descrição** | O método chama `self._store.popitem()` — que remove um par **arbitrário** do dicionário — e logo em seguida tenta `del self._store[key]`. Se a chave removida por `popitem()` não for `key`, o `del` lança `KeyError`. Mesmo que seja, o item já foi removido e `del` também falha. |
| **Impacto** | `delete()` é não-determinístico: às vezes remove a entrada errada e levanta `KeyError` na sequência, tornando o cache completamente não confiável. |
| **Correção proposta** | Substituir todo o corpo por `del self._store[key]` (já protegido pelo `if key in self._store`). |

---

## retry.py

### BUG-3 — Condição de `raise` invertida encerra na **primeira** falha

| Campo | Detalhe |
|---|---|
| **Localização** | `retry.py`, função `with_retry()`, linhas 22-24 |
| **Descrição** | O bloco `if attempt == 0: raise last_exc` relança a exceção imediatamente na primeira tentativa fracassada (`attempt == 0`), impedindo qualquer retry. A condição correta deveria relançar apenas na **última** tentativa (`attempt == max_attempts - 1`). |
| **Impacto** | A função nunca realiza retentativas; qualquer falha na primeira chamada propaga a exceção imediatamente, tornando o mecanismo de retry completamente inoperante. |
| **Correção proposta** | Alterar a condição para `if attempt == max_attempts - 1: raise last_exc` — ou simplesmente remover o `if` e deixar o loop continuar, confiando no `raise last_exc` ao final. |

---

## logger.py

### BUG-4 — `Callable` não importado causa `NameError`

| Campo | Detalhe |
|---|---|
| **Localização** | `logger.py`, linha 1 (ausência de import) e linha 11 (`func: Callable`) |
| **Descrição** | `Callable` é usado como anotação de tipo na assinatura de `log_call`, porém não foi importado de `typing`. Python avalia as anotações e lança `NameError: name 'Callable' is not defined` ao carregar o módulo. |
| **Impacto** | O módulo inteiro falha ao ser importado; nenhuma função do arquivo fica disponível. |
| **Correção proposta** | Adicionar `from typing import Callable` no topo do arquivo. |

---

### BUG-5 — `msg.format(msg)` usa auto-referência em vez do nome da função

| Campo | Detalhe |
|---|---|
| **Localização** | `logger.py`, função `log_call` → `wrapper`, linha 16 |
| **Descrição** | `msg.format(msg)` substitui `{}` pela própria string `"calling {}"`, produzindo a mensagem `"calling calling {}"` em vez do nome da função chamada. O argumento correto é `func.__name__`. |
| **Impacto** | O log de rastreamento de chamadas fica incorreto/inútil, dificultando depuração e observabilidade. |
| **Correção proposta** | Alterar para `msg.format(func.__name__)`. |

---

## Resumo

| # | Arquivo | Método / Linha | Severidade | Tipo |
|---|---|---|---|---|
| BUG-1 | `cache.py` | `Cache.get()` / L22 | 🔴 Alta | Lógica — retorno errado |
| BUG-2 | `cache.py` | `Cache.delete()` / L26-28 | 🔴 Alta | Lógica — `KeyError` / deleção errada |
| BUG-3 | `retry.py` | `with_retry()` / L22-24 | 🔴 Alta | Lógica — condição invertida |
| BUG-4 | `logger.py` | topo do arquivo / L1 | 🔴 Alta | Import ausente — `NameError` |
| BUG-5 | `logger.py` | `wrapper()` / L16 | 🟡 Média | Lógica — mensagem de log incorreta |
