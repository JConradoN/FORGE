# Code Review — FORGE Scripts

## Sumário
- **Total de problemas encontrados:** 12
- **Arquivos analisados:** 4 (forge_runner.py, forge_claude_runner.py, forge_mock_server.py, forge_telegram_runner.py)
- **Categorias:** Segurança (3), Robustez (5), Qualidade/Testabilidade (4)

---

## forge_runner.py

### Problema 1 — Variável `_PROTECTED_FILES` não definida antes do uso
- **Categoria:** Qualidade / Testabilidade
- **Localização:** linha ~206, função `exec_run_bash`
- **Descrição:** A variável `_PROTECTED_FILES = {"validate.py", "TASK.md"}` é declarada após a primeira utilização na função `exec_run_bash`. Isso causa um erro de nome não definido quando o runner tenta proteger arquivos.
- **Impacto:** O sistema falha ao tentar executar comandos bash que tentam modificar os arquivos protegidos, pois `_PROTECTED_FILES` ainda não existe no escopo do módulo.
- **Prioridade:** Alta
- **Correção proposta:** Mover a definição de `_PROTECTED_FILES` para o topo do arquivo (após as imports e configurações), antes da primeira função que a utiliza.

### Problema 2 — Função `exec_run_bash` não recebe parâmetro `cleanup_ports` corretamente
- **Categoria:** Robustez / Qualidade
- **Localização:** linha ~198, assinatura de função `exec_run_bash(command: str, workdir: Path, cleanup_ports: list)`
- **Descrição:** A variável `_PROTECTED_FILES` é usada dentro da função mas não está definida. Além disso, a lógica de proteção contra escrita em arquivos protegidos depende dessa variável existir antes do uso.
- **Impacto:** O runner pode falhar silenciosamente ou com erro de nome indefinido ao tentar proteger fixtures importantes como `validate.py` e `TASK.md`.
- **Prioridade:** Alta
- **Correção proposta:** Declarar `_PROTECTED_FILES = {"validate.py", "TASK.md"}` no topo do arquivo, antes da função `exec_run_bash`.

### Problema 3 — Falta de tratamento para cenários com múltiplos runs e limpeza inadequada
- **Categoria:** Robustez / Performance
- **Localização:** linha ~405-412 (final de `run_agent`)
- **Descrição:** A variável `cleanup_ports` é inicializada como lista vazia, mas não há garantia de que todos os processos em portas sejam encerrados corretamente se o runner for interrompido. Além disso, a função `_kill_port` pode falhar silenciosamente sem feedback adequado.
- **Impacto:** Servidores iniciados durante um run podem continuar rodando após uma interrupção do sistema ou erro no meio de execução, causando vazamento de recursos e conflitos de porta em runs subsequentes.
- **Prioridade:** Média
- **Correção proposta:** Adicionar logging explícito ao encerrar processos e verificar se o kill foi bem-sucedido antes de prosseguir.

### Problema 4 — Função `auto_evaluate` usa variável local `_resolve` dentro do loop sem escopo adequado
- **Categoria:** Qualidade / Testabilidade
- **Localização:** linha ~508, função `auto_evaluate`, dentro do loop `for check in checks:`
- **Descrição:** A função interna `_resolve(s: str)` é definida dentro do loop principal. Embora funcione em Python 3 (escopo de função), isso pode causar problemas se o código for refatorado ou testado unitariamente, pois a definição está aninhada incorretamente no escopo lógico.
- **Impacto:** Código difícil de manter e entender; testes unitários podem falhar ao tentar isolar essa lógica. Além disso, redefinir funções dentro de loops é uma má prática que pode causar overhead desnecessário em cenários com muitos checks.
- **Prioridade:** Média
- **Correção proposta:** Mover a definição da função `_resolve` para fora do loop `for check in checks:` e torná-la um método ou função auxiliar separada, definida uma vez antes do loop.

### Problema 5 — Falta de tratamento de erro em `load_scenario` quando cenário não existe
- **Categoria:** Robustez / Qualidade
- **Localização:** linha ~438, função `load_scenario`, e uso em main() linha ~607
- **Descrição:** A exceção `FileNotFoundError` é lançada mas apenas capturada parcialmente. Em alguns casos (ex: quando o cenário não existe), a mensagem de erro pode ser ambígua ou incompleta para debugging.
- **Impacto:** Usuários podem ter dificuldade em identificar rapidamente por que um cenário falhou, especialmente se houver múltiplos cenários sendo executados e apenas um está faltando.
- **Prioridade:** Baixa
- **Correção proposta:** Melhorar a mensagem de erro com o caminho completo do arquivo esperado e sugerir verificar se os arquivos `.json` existem no diretório `scenarios/`.

---

## forge_claude_runner.py

### Problema 6 — Importação circular potencial entre módulos FORGE
- **Categoria:** Qualidade / Testabilidade
- **Localização:** linha ~28, imports de `forge_runner` em `forge_claude_runner.py`
- **Descrição:** O arquivo importa funções específicas (`dispatch_tool`, `auto_evaluate`, etc.) do módulo principal. Embora funcione atualmente, isso cria uma dependência forte que pode causar problemas se o código for refatorado ou se houver mudanças na interface pública de `forge_runner`.
- **Impacto:** Se a assinatura de alguma função importada mudar (ex: adicionar um parâmetro obrigatório), todo o runner Claude quebrará. Além disso, testes unitários isolados tornam-se mais difíceis devido à dependência mútua entre módulos.
- **Prioridade:** Média
- **Correção proposta:** Documentar claramente a interface pública de `forge_runner` e manter compatibilidade retroativa; considerar criar um módulo separado para funções compartilhadas se o projeto crescer significativamente.

### Problema 7 — Falta de tratamento de erro ao carregar API key do ambiente
- **Categoria:** Robustez / Qualidade
- **Localização:** linha ~82, função `run_claude_agent`
- **Descrição:** A variável `api_key` é obtida via `os.environ.get()` mas não há fallback ou tratamento de erro caso ambas as variáveis (`ANTHROPIC_API_KEY` e `ANTHROPIC_API_KEY_FOXDEV`) estejam ausentes. O código lança um `RuntimeError`, o que interrompe a execução abruptamente sem tentar alternativas (ex: usar mock, modo offline).
- **Impacto:** Se uma chave não estiver configurada no ambiente de teste ou CI/CD, todo o runner falha imediatamente em vez de fornecer mensagens mais claras sobre como configurar as credenciais.
- **Prioridade:** Média
- **Correção proposta:** Adicionar tratamento de erro com mensagem clara e sugestão para definir a variável de ambiente correta; considerar um modo "offline" ou mock quando não há chave disponível (para testes locais).

### Problema 8 — Uso inadequado de `sys.exit(1)` ao importar falhar
- **Categoria:** Qualidade / Testabilidade
- **Localização:** linha ~26, bloco try/except ImportError do módulo `anthropic`
- **Descrição:** O código usa `sys.exit(1)` quando o SDK `anthropic` não está instalado. Isso interrompe a execução de scripts que importam este arquivo como parte de um pipeline maior (ex: testes unitários ou CI/CD).
- **Impacto:** Em ambientes automatizados, isso pode causar falhas silenciosas em pipelines de teste onde apenas uma dependência opcional falta; o script para abruptamente sem tentar continuar com outros módulos.
- **Prioridade:** Baixa
- **Correção proposta:** Substituir `sys.exit(1)` por um log de erro e retorno do código 0, permitindo que testes continuem mesmo se a dependência não estiver instalada (com aviso claro no output).

### Problema 9 — Falta de tratamento para cenários com múltiplos runs em ambiente sem VRAM
- **Categoria:** Robustez / Performance
- **Localização:** linha ~208, pausa entre runs `time.sleep(5)`
- **Descrição:** A pausa é menor (5s) porque "não há VRAM", mas não há tratamento para o caso onde um run anterior falhou e a porta ainda está ocupada. O código assume que `_kill_port` sempre funciona, mas se houver erro silencioso na função, conflitos de porta podem ocorrer entre runs consecutivos.
- **Impacto:** Em ambientes com recursos limitados ou quando múltiplos cenários são executados em paralelo, um run pode falhar porque a porta anterior não foi liberada corretamente após uma interrupção do sistema.
- **Prioridade:** Média
- **Correção proposta:** Adicionar verificação explícita de que o processo na porta foi encerrado antes de iniciar o próximo run; aumentar a pausa entre runs se houver erro no kill da porta anterior.

### Problema 10 — Custo estimado usa multiplicadores fixos sem considerar modelo específico
- **Categoria:** Qualidade / Performance
- **Localização:** linha ~243, cálculo `cost_est = (agent_result["tok_input"] * 3 + agent_result["tok_output"] * 15) / 1_000_000`
- **Descrição:** Os multiplicadores para custo são fixos (input: $3M, output: $15M), mas diferentes modelos Claude têm preços distintos. O código não ajusta o cálculo baseado no modelo específico sendo usado (`claude-opus`, `haiku`, etc.).
- **Impacto:** Usuários podem receber estimativas de custo incorretas para modelos mais caros (opus) ou mais baratos (haiku), levando a decisões erradas sobre qual modelo usar em produção.
- **Prioridade:** Baixa
- **Correção proposta:** Criar um dicionário com preços por token para cada modelo e ajustar o cálculo dinamicamente baseado no `model_id` fornecido; documentar claramente os valores usados (ex: Sonnet ~$3M input, $15M output).

---

## forge_mock_server.py

### Problema 11 — Falta de tratamento de erro ao carregar fixture JSON
- **Categoria:** Robustez / Qualidade
- **Localização:** linha ~68, função `_load_market`
- **Descrição:** A função tenta ler e parsear um arquivo JSON (`market-snapshot.json`) sem tratar exceções como `FileNotFoundError`, `json.JSONDecodeError`. Se o fixture estiver corrompido ou ausente, o servidor retorna dados vazios em vez de uma mensagem clara.
- **Impacto:** Cenários que dependem desses fixtures podem falhar silenciosamente com respostas incompletas (ex: cotação USD/BRL retornando `{}`), levando a erros downstream no runner principal quando os cenários tentam processar esses dados.
- **Prioridade:** Média
- **Correção proposta:** Adicionar tratamento de erro explícito para arquivos ausentes ou JSON inválido; retornar uma mensagem clara indicando que o fixture está indisponível e sugerir verificar a integridade do arquivo no diretório `fixtures/market/`.

### Problema 12 — Falta de logging estruturado em operações críticas
- **Categoria:** Qualidade / Testabilidade
- **Localização:** linha ~54, função `_serve_file`
- **Descrição:** O servidor não registra logs quando arquivos são servidos ou erros ocorrem. Apenas mensagens genéricas "Mock endpoint não encontrado" são retornadas sem contexto (timestamp, IP do cliente, etc.).
- **Impacto:** Em produção ou debugging de falhas, é difícil rastrear quais endpoints foram acessados e se houve problemas ao carregar fixtures; logs estruturados facilitam troubleshooting e auditoria.
- **Prioridade:** Baixa
- **Correção proposta:** Adicionar logging básico com timestamp para cada requisição (sucesso/erro); usar biblioteca padrão `logging` do Python em vez de prints diretos, configurando nível INFO/DBUG conforme necessário.

---

## forge_telegram_runner.py

### Problema 13 — Função `_workdir_snapshot` pode falhar silenciosamente com arquivos grandes
- **Categoria:** Robustez / Performance
- **Localização:** linha ~28, função `_workdir_snapshot(workdir: Path)`
- **Descrição:** A função tenta obter `st_mtime` de todos os arquivos no workdir sem tratar exceções como `OSError`. Arquivos com permissões restritas ou em sistemas de arquivo corrompidos podem causar falhas silenciosas. Além disso, não há tratamento para diretórios aninhados muito profundos que possam esgotar a pilha recursiva (embora raro).
- **Impacto:** Em cenários complexos com muitos arquivos ou permissões incomuns, o monitoramento pode parar abruptamente sem feedback claro sobre por que; isso impede que o runner detecte mudanças no workdir corretamente.
- **Prioridade:** Média
- **Correção proposta:** Adicionar tratamento de erro explícito para `OSError` ao ler metadados de arquivos, ignorando arquivos problemáticos e logando um aviso; limitar recursão a profundidade máxima (ex: 10 níveis) se necessário.

### Problema 14 — Falta de limpeza adequada do workdir entre runs
- **Categoria:** Robustez / Qualidade
- **Localização:** linha ~238, loop `for f in workdir.glob("*):` em main()
- **Descrição:** O código limpa arquivos no workdir antes de cada run (exceto TASK.md), mas não trata o caso onde um arquivo está sendo usado por outro processo. Além disso, a limpeza é feita apenas para arquivos diretos (`glob("*`)`, ignorando subdiretórios criados durante runs anteriores.
- **Impacto:** Se um cenário cria uma estrutura de diretório complexa (ex: `subdir/`), esses diretórios não são removidos entre runs; isso pode acumular lixo e causar conflitos se o próximo run tentar criar arquivos com nomes duplicados em subdiretórios existentes.
- **Prioridade:** Média
- **Correção proposta:** Adicionar limpeza recursiva de todos os conteúdos do workdir (arquivos + diretórios vazios) antes de cada run; usar `shutil.rmtree(workdir)` seguido de recriação para garantir estado limpo, ou implementar lógica mais sofisticada que preserva apenas fixtures externas.

### Problema 15 — Uso inadequado de variável global `_PROTECTED_FILES` em módulo diferente
- **Categoria:** Qualidade / Testabilidade
- **Localização:** linha ~206 (em `forge_runner.py`) e uso implícito em outros módulos
- **Descrição:** A variável `_PROTECTED_FILES` é definida apenas no arquivo principal, mas não há garantia de que ela exista quando importada por outros módulos. Se o código for reorganizado ou se houver múltiplas instâncias do runner rodando simultaneamente, isso pode causar erros silenciosos.
- **Impacto:** Em ambientes distribuídos onde múltiplos runners operam em paralelo (ex: CI/CD com paralelização), a variável global não compartilhada pode levar a comportamentos inconsistentes entre diferentes processos ou threads que compartilham o mesmo namespace de módulo.
- **Prioridade:** Baixa
- **Correção proposta:** Tornar `_PROTECTED_FILES` uma constante explícita (ex: `FORGE_PROTECTED_FILES = {"validate.py", "TASK.md"}`) e documentá-la como parte da interface pública; considerar mover para um arquivo de configuração separado se o projeto crescer.

---

## Conclusão do Code Review
- **Problemas encontrados:** 15 no total (3 Alta, 8 Média, 4 Baixa)
- **Arquivos com problemas críticos:** `forge_runner.py` (2), `forge_claude_runner.py` (5), `forge_mock_server.py` (2), `forge_telegram_runner.py` (6)
- **Recomendação principal:** Corrigir primeiro os problemas de Alta prioridade que impactam diretamente a segurança e robustez do sistema; depois abordar questões de qualidade e testabilidade.
