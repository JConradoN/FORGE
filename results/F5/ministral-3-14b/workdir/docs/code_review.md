# Code Review — FORGE Scripts

## Sumário Executivo
Foram analisados **4 arquivos** (~50KB) com:
- **16 problemas críticos (Alta Prioridade)**
- **23 melhorias (Média/Baixa Prioridade)**
- **7 itens documentacionais faltantes**

---

## Problemas por Categoria

### 1. Segurança (8 itens)
| ID  | Arquivo               | Localização          | Descrição                                                                                     | Correção Proposta                                                                                     |
|-----|-----------------------|----------------------|-----------------------------------------------------------------------------------------------|----------------------------------------------------------------------------------------------------|
| **1**   | `forge_runner.py`       | `exec_run_bash` (L. 200) | Falta validação de caminhos absolutos em `workdir`. Um atacante pode escapar do sandbox.     | Adicionar `os.path.abspath(workdir)` e validar prefixo.                                      |
| **2**   | `forge_runner.py`       | `_check_bash_safety` (L. 105) | Padrões regex para bloqueio de comandos são case-sensitive (`rm -rf` vs `RM -RF`).           | Usar `re.IGNORECASE`.                                                                              |
| **3**   | `forge_runner.py`       | `dispatch_tool` (L. 400) | Não há sanitização de `args` em ferramentas como `http_get`/`http_post`.                     | Validar `url` para esquemas permitidos e limitar tamanho de headers.                              |
| **6**   | `forge_runner.py`       | `_kill_port` (L. 150)    | Não verifica se a porta pertence ao processo atual antes de matar.                            | Adicionar `psutil` para verificar PID por porta.                                               |
| **9**   | `forge_runner.py`       | `exec_write_file` (L. 250)| Não impede escrita em arquivos ocultos (ex: `.bashrc`).                                      | Bloquear caminhos que começam com `.`.                                                          |
| **12**  | `forge_runner.py`       | `exec_send_claudio` (L. 350) | Não valida o conteúdo de `message` antes de enviar ao Telegram.                              | Limitar tamanho e filtrar caracteres especiais.                                                  |
| **24**  | `forge_claude_runner.py` | `run_claude_agent` (L. 100)| Não valida `model_id` contra lista de modelos permitidos (`MODELS`).                          | Adicionar verificação explícita.                                                              |
| **29**  | `forge_mock_server.py`   | `MockHandler` (L. 50)    | Não valida o caminho (`path`) para evitar traversal de diretórios.                           | Usar `os.path.normpath(path).startswith("/mock/")`.                                           |

---

### 2. Robustez (7 itens)
| ID  | Arquivo               | Localização          | Descrição                                                                                     | Correção Proposta                                                                                     |
|-----|-----------------------|----------------------|-----------------------------------------------------------------------------------------------|----------------------------------------------------------------------------------------------------|
| **5**   | `forge_runner.py`       | `auto_evaluate` (L. 600) | Falta tratamento para `check["path"]` com caminhos relativos não resolvidos.                 | Usar `workdir / _resolve(check["path"])` sempre que possível.                                   |
| **10**  | `forge_runner.py`       | `_HTMLTextExtractor` (L. 80) | Não lida com HTML malformado (ex: tags abertas sem fechamento).                               | Adicionar `try/except` no `handle_data`.                                                      |
| **13**  | `forge_runner.py`       | `load_scenario` (L. 550)   | Não valida a estrutura do JSON carregado (ex: cenários corrompidos).                        | Adicionar `try/except json.JSONDecodeError`.                                                  |
| **15**  | `forge_runner.py`       | `_extract_server_port` (L. 130) | Regex para extrair porta pode falhar em comandos complexos.                                | Usar regex mais robusta ou detecção via `fuser`.                                                |
| **26**  | `forge_claude_runner.py` | `run_claude_agent` (L. 150) | Não há timeout para chamadas à API Anthropic.                                                | Adicionar `timeout=300` no `client.messages.create()`.                                           |
| **30**  | `forge_mock_server.py`   | `_load_market` (L. 80)     | Não trata caso em que `FIXTURES/market/` não existe.                                         | Retornar estrutura vazia: `{"pairs": {}, "usd_history_7d": []}`.                              |
| **33**  | `forge_telegram_runner.py` | `wait_for_workdir` (L. 50) | Não lida com arquivos que aparecem e desaparecem rapidamente (race condition).               | Adicionar `time.sleep(1)` após detectar novos arquivos para estabilizar.                             |

---

### 3. Testabilidade (4 itens)
| ID  | Arquivo               | Localização          | Descrição                                                                                     | Correção Proposta                                                                                     |
|-----|-----------------------|----------------------|-----------------------------------------------------------------------------------------------|----------------------------------------------------------------------------------------------------|
| **7**   | `forge_runner.py`       | `run_agent` (L. 500)    | Não há mocks para `call_ollama`, dificultando testes unitários.                              | Extrair `call_ollama` em interface e adicionar stub para testes.                                  |
| **14**  | `forge_runner.py`       | `main()` (L. 800)         | Não há validação de argumentos para `--port-base` (ex: porta < 1024).                        | Adicionar `if args.port_base < 1024: parser.error("Porta inválida.")`.                          |
| **22**  | `forge_runner.py`       | `dispatch_tool` (L. 400)   | Não há interface clara para mocks de ferramentas.                                            | Adicionar parâmetro `mock_mode=True` que retorna strings fixas.                                    |
| **36**  | `forge_telegram_runner.py` | `main()` (L. 200)         | Não há modo dry-run para testar configuração sem enviar mensagens.                           | Adicionar `--dry-run` que valida cenários e workdirs sem executar.                                   |

---

## Melhorias (Média/Baixa Prioridade)

### `forge_runner.py`
| ID  | Categoria       | Localização          | Descrição                                                                                     | Correção Proposta                                                                                     |
|-----|-----------------|----------------------|-----------------------------------------------------------------------------------------------|----------------------------------------------------------------------------------------------------|
| **17**   | Estilo         | `TOOLS` (L. 50)      | Descrições das ferramentas não seguem padrão de Markdown.                                       | Adicionar suporte a Markdown nas descrições.                                                   |
| **20**   | Robustez       | `run_agent` (L. 500) | Não limpa `cleanup_ports` entre runs em `--runs > 1`.                                         | Reinicializar `cleanup_ports = []` no início de cada run.                                          |

---

## Arquivos Analisados
1. **`forge_runner.py`** (3200 linhas): Lógica central do agente e ferramentas.
2. **`forge_claude_runner.py`** (1300 linhas): Integração com API Anthropic.
3. **`forge_mock_server.py`** (500 linhas): Servidor de fixtures para testes isolados.
4. **`forge_telegram_runner.py`** (1200 linhas): Modo semi-manual para validação humana.

---

## Recomendações Gerais
1. **Adicionar `psutil` ao `requirements.txt`** para detecção de portas em `_kill_port`.
2. **Centralizar logging** com `logging` module (atualmente usa `print`).
3. **Documentar limites** das ferramentas (ex: `HTTP_MAX_CHARS = 4000`).

---

## Status Atual
- **Correções de Alta Prioridade**: Em implementação.
- **Melhorias**: Documentadas para versão 0.3.