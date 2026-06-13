# Code Review - Módulo com Bugs

## Resumo
Foram identificados **5 bugs** em 3 arquivos do módulo `buggy-module`.

---

## Arquivo: cache.py

### Bug-1: Método get() retorna dict inteiro ao invés do valor
- **Localização**: Linha 20, método `get()` da classe `Cache`
- **Descrição**: O método retorna o dicionário completo (`self._store.get(key)`) em vez de retornar apenas o valor armazenado no entry.
- **Impacto**: Consumidores do cache recebem um dict com estrutura `{key: ..., value: ..., ttl: ...}` ao invés do valor esperado, quebrando contratos de API e causando erros downstream.
- **Correção proposta**: Retornar `entry["value"]` em vez de `self._store.get(key)`.

### Bug-2: Método delete() faz double-delete com popitem()
- **Localização**: Linhas 23-25, método `delete()` da classe `Cache`
- **Descrição**: O método usa `popitem()` que remove um item arbitrário do dicionário (geralmente o último), e depois tenta deletar a chave específica com `del`. Isso causa:
  - Remoção incorreta de dados (remove outro key-value pair)
  - KeyError se a chave não for o último item após popitem()
- **Impacto**: Dados errados são removidos do cache, podendo causar perda de informações e exceções inesperadas.
- **Correção proposta**: Usar apenas `self._store.pop(key)` ou remover as duas linhas problemáticas e usar um único método correto para deletar a chave específica.

---

## Arquivo: retry.py

### Bug-3: Lógica invertida no controle de tentativas
- **Localização**: Linha 21, dentro do loop `for` da função `with_retry()`
- **Descrição**: A condição `if attempt == 0:` levanta exceção na primeira tentativa (índice 0), impedindo que as tentativas subsequentes ocorram. O retry nunca funciona porque a exceção é levantada imediatamente após o primeiro erro.
- **Impacto**: A função de retry não realiza nenhuma nova tentativa - comporta-se como uma execução única sem fallback, invalidando completamente seu propósito.
- **Correção proposta**: Remover ou inverter a condição para permitir que todas as tentativas ocorram antes de levantar exceções.

---

## Arquivo: logger.py

### Bug-4: Importação faltante - Callable não definido
- **Localização**: Linha 6 (falta import) e linha 10 (uso em anotação de tipo)
- **Descrição**: O módulo usa `Callable` nas anotações de tipo mas não importa da biblioteca `typing`. Isso causa um `NameError` ao tentar definir o decorator.
- **Impacto**: Módulo falha na importação/definição, tornando todo o sistema de logging inoperante.
- **Correção proposta**: Adicionar `from typing import Callable` no início do arquivo.

### Bug-5: Log com auto-referência incorreta
- **Localização**: Linha 16, dentro da função `wrapper()`
- **Descrição**: A string de log usa `msg.format(msg)` que substitui `{}` pelo próprio texto "calling {}", resultando em mensagem inútil. Deveria usar o nome da função decorada (`func.__name__`).
- **Impacto**: Logs não identificam qual função está sendo chamada, tornando o rastreamento e debugging impossíveis.
- **Correção proposta**: Usar `msg.format(func.__name__)` para logar corretamente o nome da função.

---

## Total de Bugs: 5
- cache.py: 2 bugs
- retry.py: 1 bug  
- logger.py: 2 bugs
