# Code Review

## Bug 1: Retorna o dicionário inteiro ao invés do valor em `get`
- **Localização:** buggy-module/cache.py
- **Descrição:** O método `get` retorna o dicionário inteiro ao invés do valor armazenado.
- **Impacto:** O uso do método `get` não retornará o valor esperado, causando erros em aplicações que dependem desse comportamento.
- **Correção proposta:** Alterar a linha `return self._store.get(key)` para `return self._store.get(key).get('value')`.

## Bug 2: Double-delete em `delete`
- **Localização:** buggy-module/cache.py
- **Descrição:** O método `delete` usa `popitem()` e depois `del self._store[key]`, o que pode causar um `KeyError` se a chave não for o último item.
- **Impacto:** Pode causar falhas inesperadas ao tentar deletar uma chave que não é a última no dicionário.
- **Correção proposta:** Remover a linha `self._store.popitem()`.

## Bug 3: Lógica invertida no retry
- **Localização:** buggy-module/retry.py
- **Descrição:** A lógica do retry está invertida, levantando a exceção na primeira tentativa.
- **Impacto:** O retry nunca será executado, e a exceção será levantada imediatamente.
- **Correção proposta:** Alterar a condição `if attempt == 0:` para `if attempt == max_attempts - 1:`.

## Bug 4: `Callable` não importado
- **Localização:** buggy-module/logger.py
- **Descrição:** A linha `from typing import Callable` está ausente, causando um `NameError`.
- **Impacto:** O decorador `log_call` não será reconhecido corretamente, causando erros de compilação.
- **Correção proposta:** Adicionar a linha `from typing import Callable` no início do arquivo.

## Bug 5: Auto-referência no log
- **Localização:** buggy-module/logger.py
- **Descrição:** A linha `msg.format(msg)` usa a variável `msg` para formatar a mensagem, causando uma auto-referência.
- **Impacto:** A mensagem de log será incorreta, mostrando o objeto `msg` em vez do nome da função.
- **Correção proposta:** Alterar a linha `msg = "calling {}"` para `msg = "calling {}"` e `LOG.debug(msg.format(func.__name__))`.