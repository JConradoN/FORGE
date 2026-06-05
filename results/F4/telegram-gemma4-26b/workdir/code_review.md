# Code Review — buggy-module

## Sumário
Foram encontrados 5 bugs distribuídos em três arquivos do módulo. Os problemas variam de erros de lógica elementar a falhas de importação e uso incorreto de APIs padrão da linguagem.

## cache.py
### Bug 1
- **Localização:** linha 24
- **Descrição:** O método `get` retorna o dicionário completo `CacheEntry` contendo chave, valor e TTL, em vez de retornar apenas o conteúdo do campo `value`.
- **Impacto:** Quebra a expectativa do usuário ao receber um objeto `TypedDict` quando esperava o dado bruto.
- **Correção:** Alterar para `return self._store.get(key)["value"] if key in self._store else None`.

### Bug 2
- **Localização:** linha 30
- **Descrição:** O método `delete` chama `popitem()` (que remove um item sem critério, geralmente o último) e depois tenta deletar a chave explicitamente via `del`. Se a chave deletada for a mesma removida pelo `popitem`, ocorre um `KeyError`.
- **Impacto:** Crash da aplicação durante operações de remoção.
- **Correção:** Usar apenas `self._store.pop(key, None)`.

## retry.py
### Bug 3
- **Localização:** linha 24
- **Descrição:** A lógica de interrupção está invertida: o código levanta a exceção logo na primeira falha (`if attempt == 0`), anulando qualquer possibilidade de reexecução nas tentativas subsequentes.
- **Impacto:** O mecanismo de retry é inútil, pois não permite que as tentativas 1 e 2 ocorram em caso de erro na tentativa 0.
- **Correção:** Remover o bloco `if attempt == 0: raise last_exc`.

## logger.py
### Bug 4
- **Localização:** linha 7
- **Descrição:** O tipo `Callable` está sendo usado como anotação, mas não foi importado do módulo `typing`.
- **Impacto:** `NameError` ao tentar carregar o módulo.
- **Correção:** Adicionar `from typing import Callable`.

### Bug 5
- **assentamento:** linha 14
- **Descrição:** A string de log utiliza `msg.format(msg)`, o que é logicamente incorreto e não injeta o nome da função na mensagem.
- **Impacto:** Logs confusos ou erro de formatação se a string contivesse placeholders mal aproveitados.
- **Correção:** Usar f-string ou format com o nome da função: `LOG.debug(f"calling {func.__name__}")`.
