# Code Review — FORGE Scripts

## Sumário

| Arquivo | Problemas Encontrados | Alta Prioridade | Média Prioridade | Baixa Prioridade |
|---------|----------------------|-----------------|------------------|------------------|
| forge_runner.py | 5 | 2 | 2 | 1 |
| forge_claude_runner.py | 4 | 1 | 2 | 1 |
| forge_mock_server.py | 3 | 1 | 1 | 1 |
| forge_telegram_runner.py | 4 | 1 | 2 | 1 |

**Total: 16 problemas identificados (5 Alta, 7 Média, 4 Baixa)**

---

## forge_runner.py

### Problema 1 — Variável Global Modificada em Função de Tool
- **Categoria:** Robustez / Testabilidade
- **Localização:** linha ~208, função `exec_run_bash`
- **Descrição:** A lista `_PROTECTED_FILES` é definida globalmente mas pode ser modificada externamente. Além disso, a verificação de proteção usa regex que pode ter falsos positivos/negativos dependendo do formato da string no comando bash.
- **Impacto:** Se um atacante ou bug injetar comandos com padrões específicos, arquivos protegidos podem ser sobrescritos via `run_bash`. A lógica atual só protege contra redirecionamento direto (`> arquivo`), mas não contra outros métodos como `tee`, `cat >`, etc.
- **Prioridade:** Alta
- **Correção proposta:** Expandir a blocklist de proteção para incluir mais padrões de escrita (tee, cat com redirect, echo) e usar verificação explícita do caminho alvo em vez de regex frágil no comando inteiro.

### Problema 2 — Tratamento Incompleto de Erros HTTP
- **Categoria:** Robustez / Qualidade
- **Localização:** linha ~305, função `exec_http_get` e linha ~314, função `exec_http_post`
- **Descrição:** As funções HTTP capturam exceções genéricas mas não distinguem entre diferentes tipos de falhas (timeout vs erro 404 vs erro 500). O código retorna apenas `[ERRO] {e}` sem contexto útil para o agente.
- **Impacto:** Quando uma requisição falha, o LLM recebe mensagens vagas que dificultam diagnóstico e recuperação automática. Em cenários de benchmark, isso pode levar a resultados inconsistentes.
- **Prioridade:** Alta
- **Correção proposta:** Adicionar tratamento específico para `urllib.error.HTTPError` (extrair status code), `socket.timeout`, e outras exceções específicas. Retornar mensagens estruturadas como `[HTTP 404] URL não encontrada`.

### Problema 3 — Injeção de Variáveis sem Validação
- **Categoria:** Segurança / Robustez
- **Localização:** linha ~527, função `auto_evaluate`, método `_resolve` interno
- **Descrição:** A função usa `.format(**fmt_vars)` para substituir variáveis em strings vindas dos cenários JSON. Se um cenário malicioso contiver `{__import__('os').system('rm -rf /')}`, isso seria executado durante o format().
- **Impacto:** Embora Python não execute código no .format(), a função pode ser vulnerável se futuramente for alterada para usar eval() ou exec(). Além disso, variáveis do cenário podem sobrescrever chaves sensíveis como `workdir`.
- **Prioridade:** Média
- **Correção proposta:** Validar que as chaves de fmt_vars estão em uma whitelist permitida. Usar um parser seguro (ex: re.sub com named groups) ao invés de .format() direto, ou pelo menos limitar quais variáveis podem ser substituídas.

### Problema 4 — Limpeza de Portas sem Verificação
- **Categoria:** Robustez / Segurança
- **Localização:** linha ~203, função `_kill_port` e uso em `run_agent` (linha ~518)
- **Descrição:** A função `_kill_port` usa `fuser -k` para matar processos na porta sem verificar se o processo é realmente um servidor iniciado pelo runner. Pode matar qualquer processo escutando naquela porta, incluindo serviços do sistema ou outros usuários.
- **Impacto:** Em ambientes compartilhados (CI/CD, máquinas multi-usuário), isso pode derrubar serviços legítimos que estejam usando a mesma porta por coincidência.
- **Prioridade:** Média
- **Correção proposta:** Registrar o PID dos processos iniciados pelo runner e matar apenas esses PIDs específicos ao invés de usar `fuser -k` na porta inteira. Adicionar verificação se o processo é realmente um servidor HTTP antes de encerrar.

### Problema 5 — Documentação Desatualizada no Docstring
- **Categoria:** Qualidade / Manutenção
- **Localização:** linha ~1, docstring do módulo
- **Descrição:** O docstring menciona "Fixes v0.2" com lista de correções que já foram aplicadas, mas não há versão atual ou changelog claro sobre o estado atual do código. Isso dificulta entender quais bugs ainda podem existir.
- **Impacto:** Desenvolvedores futuros podem achar que certos problemas estão resolvidos quando na verdade a documentação está desatualizada em relação ao código real.
- **Prioridade:** Baixa
- **Correção proposta:** Atualizar o docstring com versão atual e manter changelog separado ou usar comentários inline para marcar áreas conhecidas de atenção.

---

## forge_claude_runner.py

### Problema 1 — Importação Circular Potencial
- **Categoria:** Robustez / Testabilidade
- **Localização:** linha ~32, importações do `forge_runner`
- **Descrição:** O arquivo importa funções diretamente de `forge_runner`, criando dependência entre módulos. Se `forge_claude_runner.py` for executado isoladamente ou em ambiente onde `forge_runner` não está disponível, falha completamente. Além disso, qualquer mudança na assinatura das funções importadas quebra ambos os arquivos.
- **Impacto:** Dificulta testes unitários independentes e manutenção paralela dos dois providers. Mudanças no runner principal podem quebrar o provider Claude sem aviso.
- **Prioridade:** Alta
- **Correção proposta:** Extrair as ferramentas comuns (dispatch_tool, auto_evaluate) para um módulo compartilhado `forge_common.py` ou criar interfaces claras com type hints que permitam substituição de implementação por dependency injection.

### Problema 2 — Tratamento Inadequado de Erros da API Anthropic
- **Categoria:** Robustez / Qualidade
- **Localização:** linha ~147, bloco `except anthropic.APIError`
- **Descrição:** Apenas captura `anthropic.APIError`, mas a biblioteca pode lançar outras exceções como `RateLimitError`, `PermissionError`, ou erros de rede. Essas não são tratadas e podem causar falhas inesperadas no loop principal.
- **Impacto:** Erros comuns como rate limiting (429) causam crash do runner ao invés de retry gracioso, interrompendo benchmarks em andamento.
- **Prioridade:** Média
- **Correção proposta:** Adicionar tratamento específico para `anthic.RateLimitError` com backoff exponencial e captura genérica de exceções da biblioteca Anthropic com mensagens mais informativas.

### Problema 3 — Cálculo de Custo Estimado Hardcoded
- **Categoria:** Qualidade / Manutenção
- **Localização:** linha ~279, cálculo `cost_est = (tok_input * 3 + tok_output * 15) / 1_000_000`
- **Descrição:** Os preços de tokens estão hardcoded para Sonnet ($3/MT in, $15/MT out), mas o código suporta múltiplos modelos com preços diferentes (Haiku é mais barato, Opus é mais caro). O cálculo sempre usa os preços do modelo padrão.
- **Impacto:** Relatórios de custo são imprecisos para Haiku e Opus, podendo enganar usuários sobre custos reais dos benchmarks.
- **Prioridade:** Média
- **Correção proposta:** Criar dicionário com preços por modelo (`PRICES = {"claude-haiku": {...}, "claude-opus": {...}}`) e usar o preço correto baseado no `model_id` selecionado.

### Problema 4 — Mensagem de Erro Genérica para API Key
- **Categoria:** Qualidade / UX
- **Localização:** linha ~107, verificação da chave API
- **Descrição:** A mensagem "ANTHROPIC_API_KEY ou ANTHROPIC_API_KEY_FOXDEV não definida" é genérica e não ajuda o usuário a entender como configurar. Não há link para documentação nem sugestão de onde obter a key.
- **Impacto:** Novos usuários podem ficar confusos sobre como configurar o ambiente corretamente, aumentando tempo de setup.
- **Prioridade:** Baixa
- **Correção proposta:** Melhorar mensagem com instruções claras: "Configure ANTHROPIC_API_KEY no seu .env ou exporte antes de executar. Obtenha em https://console.anthropic.com".

---

## forge_mock_server.py

### Problema 1 — Importação `os` Fora do Topo
- **Categoria:** Qualidade / Convenção
- **Localização:** linha ~98, importação tardia de `import os`
- **Descrição:** O módulo `os` é usado na função `start()` (linha ~76) mas só é importado no final do arquivo. Isso viola convenções PEP 8 e pode causar confusão sobre dependências reais do módulo.
- **Impacto:** Ferramentas de linting/analise estática podem não detectar corretamente as dependências. Desenvolvedores podem achar que `os` não é necessário até encontrar erro em runtime.
- **Prioridade:** Baixa
- **Correção proposta:** Mover todas as importações para o topo do arquivo conforme PEP 8, agrupando por padrão (padrão Python, terceiros, locais).

### Problema 2 — Falta de Tratamento de Erro em `stop()` e `status()`
- **Categoria:** Robustez / Qualidade
- **Localização:** linha ~90 (`stop()`) e linha ~103 (`status()`)
- **Descrição:** As funções não tratam adequadamente casos onde o PID_FILE existe mas contém dados inválidos (não numérico, vazio). A conversão `int(PID_FILE.read_text().strip())` pode lançar ValueError.
- **Impacto:** Se alguém corromper ou editar manualmente o arquivo de PID, as funções crasham com traceback ao invés de mensagem amigável.
- **Prioridade:** Média
- **Correção proposta:** Adicionar try/except para `ValueError` e tratar como caso onde o servidor não está rodando (remover arquivo corrompido).

### Problema 3 — Endpoint `/health` Não Verifica Fixtures
- **Categoria:** Robustez / Qualidade
- **Localização:** linha ~42, handler do endpoint `/health`
- **Descrição:** O health check retorna `{"status": "ok"}` sem verificar se as fixtures estão disponíveis ou se o servidor está realmente funcional. Um mock server com fixtures ausentes passaria no health check mas falharia em requests reais.
- **Impacto:** Scripts de CI/CD que verificam saúde do serviço podem achar tudo OK quando na verdade os dados não estão carregados, levando a benchmarks inconsistentes.
- **Prioridade:** Alta
- **Correção proposta:** Adicionar verificação no `/health` para confirmar que o diretório FIXTURES existe e contém pelo menos um arquivo de fixture esperado (ex: market-snapshot.json).

---

## forge_telegram_runner.py

### Problema 1 — Falta de Validação do TTY
- **Categoria:** Robustez / Qualidade
- **Localização:** linha ~87, função `_await_enter()`
- **Descrição:** A função tenta abrir `/dev/tty` mas se falha (ambiente sem terminal), apenas imprime mensagem e espera 20s hardcoded. Não há fallback configurável nem verificação real de que o usuário enviou a mensagem no Telegram.
- **Impacto:** Em ambientes headless ou CI, o comportamento é imprevisível — sempre espera 20s mesmo se não houver interação possível. Isso pode causar timeouts falsos em benchmarks automatizados.
- **Prioridade:** Alta
- **Correção proposta:** Adicionar flag `--auto` para bypass do await e permitir execução totalmente automática (útil para CI). Ou usar variável de ambiente `FORGE_AUTO_MODE=1`.

### Problema 2 — Limpeza Incompleta entre Runs
- **Categoria:** Robustez / Qualidade
- **Localização:** linha ~237, limpeza antes do próximo run
- **Descrição:** O código limpa apenas arquivos (`f.unlink()`) mas não remove diretórios vazios criados durante o run anterior. Após múltiplos runs, acumulam-se pastas vazias no workdir que podem confundir checks de `file_exists`.
- **Impacto:** Em benchmarks com --runs > 1, artefatos residuais entre execuções podem causar falsos positivos em verificações ou poluir resultados.
- **Prioridade:** Média
- **Correção proposta:** Usar `shutil.rmtree(workdir)` e recriar o diretório antes de cada run para garantir estado limpo completo (preservando apenas fixtures externas se necessário).

### Problema 3 — Monitoramento Não Detecta Modificações em Arquivos Existentes
- **Categoria:** Robustez / Qualidade
- **Localização:** linha ~52, função `wait_for_workdir()` e `_workdir_snapshot()`
- **Descrição:** O snapshot compara apenas timestamps de modificação (`st_mtime`), mas se um arquivo for modificado dentro do mesmo segundo (ou o sistema tiver resolução baixa no timestamp), a mudança não é detectada. Além disso, arquivos deletados não são registrados como "mudança".
- **Impacto:** Se o agente modificar rapidamente um arquivo existente sem criar novos, o monitor pode achar que estabilizou prematuramente e parar antes do trabalho estar completo.
- **Prioridade:** Média
- **Correção proposta:** Usar hash de conteúdo (md5/sha256) para detectar mudanças reais em arquivos existentes, não apenas timestamps. Adicionar detecção de deletions comparando sets de arquivos entre snapshots.

### Problema 4 — Variável `checks_key` Hardcoded e Frágil
- **Categoria:** Qualidade / Manutenção
- **Localização:** linha ~257, variável `checks_key = "aurelia_auto_checks"`
- **Descrição:** A string `"aurelia_auto_checks"` é hardcoded para suportar cenários antigos. Se um cenário tiver essa chave mas também tiver `auto_checks`, há duplicação/confusão. Não há validação ou warning sobre conflito de chaves.
- **Impacto:** Cenários malformados podem ter comportamento inesperado com checks duplicados ou sobrescritos silenciosamente. Dificulta debugging quando resultados não batem com expectativas.
- **Prioridade:** Baixa
- **Correção proposta:** Adicionar warning se ambas as chaves existirem e documentar claramente que `aurelia_auto_checks` é legado e será removido em versão futura.

---

## Resumo por Categoria

| Categoria | Total de Problemas | Arquivos Afetados |
|-----------|-------------------|-------------------|
| Robustez / Qualidade | 9 | Todos os 4 arquivos |
| Segurança | 2 | forge_runner.py, forge_claude_runner.py (indireto) |
| Performance | 0 | - |
| Testabilidade | 1 | forge_claude_runner.py |
| Manutenção / Convenções | 3 | forge_mock_server.py, forge_telegram_runner.py |

---

## Recomendações Gerais

1. **Centralizar código compartilhado:** Extrair `dispatch_tool`, `auto_evaluate` e ferramentas para módulo comum (`forge_common.py`) para evitar duplicação entre providers.
2. **Melhorar tratamento de erros:** Adicionar tipos específicos de exceção em cada provider com mensagens estruturadas que ajudem o LLM a diagnosticar problemas.
3. **Validação de entrada:** Implementar validações mais rigorosas nas funções que recebem dados externos (cenários JSON, comandos bash).
4. **Documentação consistente:** Manter docstrings atualizados e adicionar exemplos de uso em cada função pública.
