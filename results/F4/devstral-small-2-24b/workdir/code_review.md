# Code Review - buggy-module

## Bugs encontrados e correções

### cache.py

#### BUG-1: Método `get` retorna o dict inteiro ao invés do valor armazenado
- **Localização**: Linha ~20 no método `Cache.get`
- **Descrição**: O método retorna `self._store.get(key)` que é um objeto `CacheEntry`, não o valor armazenado.
- **Impacto**: Consumidores recebem um dict com chaves `key`, `value`, `ttl` ao invés do valor esperado.
- **Correção proposta**: Retornar `self._store.get(key)["value"]` se a entrada existir, senão `None`.

#### BUG-2: Método `delete` tenta deletar duas vezes e usa método errado
- **Localização**: Linha ~24 no método `Cache.delete`
- **Descrição**: 
  - Usa `popitem()` que remove o último item do dict, não o item pela chave.
  - Em seguida tenta deletar novamente com `del self._store[key]`, causando KeyError se a chave não for o último item.
- **Impacto**: Falha em tempo de execução ao tentar deletar qualquer chave que não seja a última inserida.
- **Correção proposta**: Usar apenas `self._store.pop(key, None)` para remover a chave de forma segura.

---

### retry.py

#### BUG: Lógica invertida no loop de retry
- **Localização**: Linha ~18 dentro do loop for
- **Descrição**: A condição `if attempt == 0` levanta a exceção na primeira tentativa, nunca permitindo retries.
- **Impacto**: O decorator falha imediatamente e nunca executa as tentativas subsequentes.
- **Correção proposta**: Remover a condicional e sempre dormir entre tentativas (exceto na última).

---

### logger.py

#### BUG-1: Import missing para `Callable`
- **Localização**: Topo do arquivo, falta import do typing
- **Descrição**: O tipo `Callable` é usado mas não importado.
- **Impacto**: NameError ao carregar o módulo.
- **Correção proposta**: Adicionar `from typing import Callable`.

#### BUG-2: Mensagem de log usa auto-referência em vez do nome da função
- **Localização**: Linha ~18 dentro do wrapper
- **Descrição**: A mensagem usa `msg.format(msg)` ao invés de `func.__name__`, resultando em uma string recursiva.
- **Impacto**: Logs mostram "calling calling calling..." ao invés do nome da função decorada.
- **Correção proposta**: Usar `func.__name__` na mensagem de log.
