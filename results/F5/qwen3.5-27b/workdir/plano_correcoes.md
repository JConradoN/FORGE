# Plano de Correções — FORGE Scripts

## Resumo por Prioridade

| Prioridade | Quantidade | Descrição | Ação Imediata |
|------------|-----------|-----------|---------------|
| **Alta**   | 5         | Impacta comportamento ou pode causar bugs em produção | ✅ Implementar agora |
| **Média**  | 7         | Degradação de qualidade, manutenção difícil | 📋 Planejar para próximo sprint |
| **Baixa**  | 4         | Estilo, convenções, melhorias menores | 🗂️ Registrar como backlog |

---

## 🔴 Prioridade ALTA (Implementar Agora)

### A1 — forge_runner.py: Proteção de Arquivos Incompleta em run_bash
- **Problema:** Verificação atual só bloqueia redirecionamento direto (`> arquivo`), mas não protege contra `tee`, `cat >`, `echo >>`, etc.
- **Impacto:** Agentes podem sobrescrever arquivos protegidos (validate.py, TASK.md) usando métodos alternativos de escrita.
- **Correção:** Expandir blocklist para incluir padrões adicionais e validar caminho alvo explicitamente.

```python
# Adicionar à função exec_run_bash:
_PROTECTED_WRITE_PATTERNS = [
    r"[>|]\s*['\"]?([^'\"]*\.(?:py|md))",  # redirect direto
    r"tee\s+.*\b(validate\.py|TASK\.md)",   # tee para arquivos protegidos
    r"echo\s+[\"']?.*[\"']?\s*>+\s*(validate\.py|TASK\.md)",  # echo com redirect
]

def _is_protected_write(command: str, workdir: Path) -> bool | None:
    """Retorna caminho do arquivo protegido se detectado, None se seguro."""
    for protected in _PROTECTED_FILES:
        if re.search(rf"(?:>|tee|echo).*\b{re.escape(protected)}", command):
            return str(workdir / protected)
    return None

# Em exec_run_bash:
blocked_file = _is_protected_write(command, workdir)
if blocked_file:
    return f"[BLOQUEADO] '{Path(blocked_file).name}' é um arquivo de fixture protegido."
```

---

### A2 — forge_runner.py: Tratamento Incompleto de Erros HTTP
- **Problema:** Funções `exec_http_get` e `exec_http_post` retornam apenas `[ERRO] {e}` sem distinguir tipos de falha.
- **Impacto:** Agentes não conseguem diagnosticar se erro é 404, timeout, ou problema de rede.

```python
# Em exec_http_get:
def exec_http_get(url: str, headers: dict) -> str:
    try:
        req = urllib.request.Request(url, headers=headers or {})
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        return f"[HTTP {e.code}] URL não encontrada ou erro no servidor. URL: {url}"
    except urllib.error.URLError as e:
        if "timed out" in str(e).lower():
            return f"[TIMEOUT] Requisição para {url} expirou após 30s"
        return f"[NETWORK ERROR] Não foi possível conectar a {url}: {e.reason}"
    except Exception as e:
        return f"[ERRO INESPERADO] {type(e).__name__}: {str(e)[:200]}"

# Em exec_http_post (similar):
def exec_http_post(url: str, body: dict, headers: dict) -> str:
    try:
        data = json.dumps(body).encode()
        h = {"Content-Type": "application/json"}
        h.update(headers or {})
        req = urllib.request.Request(url, data=data, headers=h, method="POST")
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.read().decode("utf-8", errors="replace")[:4000]
    except urllib.error.HTTPError as e:
        body_err = e.read().decode()[:200] if e.fp else ""
        return f"[HTTP {e.code}] Erro no POST para {url}. Response: {body_err}"
    except Exception as e:
        return f"[ERRO INESPERADO] {type(e).__name__}: {str(e)[:200]}"
```

---

### A3 — forge_claude_runner.py: Importação Circular / Dependência Acoplada
- **Problema:** `forge_claude_runner` importa diretamente de `forge_runner`, criando acoplamento forte.
- **Impacto:** Mudanças no runner principal podem quebrar o provider Claude sem aviso; dificulta testes unitários independentes.

```python
# Solução: Criar módulo compartilhado forge_common.py com interfaces claras
# Em forge_claude_runner.py, substituir importação direta por:
from forge_common import (
    dispatch_tool, auto_evaluate, save_run_result, aggregate_runs, load_scenario, RESULTS_BASE
)

# Se não for possível criar novo arquivo imediatamente, pelo menos adicionar type hints
# e comentários documentando dependências explícitas.
```

**Nota:** Como a tarefa pede para não alterar interface pública nem adicionar arquivos novos além dos 3 documentos, esta correção será implementada como melhoria de documentação nos imports existentes com warning inline sobre acoplamento.

---

### A4 — forge_mock_server.py: Health Check Não Verifica Fixtures
- **Problema:** Endpoint `/health` retorna OK mesmo se fixtures não estiverem disponíveis.
- **Impacto:** CI/CD pode achar serviço saudável quando na verdade dados estão ausentes, causando benchmarks inconsistentes.

```python
# Em MockHandler.do_GET para /health:
elif path == "/health":
    # Verificar que FIXTURES existe e tem conteúdo mínimo esperado
    fixtures_ok = False
    if FIXTURES.exists():
        market_file = FIXTURES / "market" / "market-snapshot.json"
        github_file = FIXTURES / "github-n8n" / "page-snapshot.txt"
        fixtures_ok = market_file.exists() or github_file.exists()
    
    status_data = {
        "status": "ok" if fixtures_ok else "degraded",
        "fixtures_available": fixtures_ok,
        "port": MOCK_PORT
    }
    self._respond(200, "application/json", json.dumps(status_data))
```

---

### A5 — forge_telegram_runner.py: Falta de Modo Automático para CI/Headless
- **Problema:** Função `_await_enter()` sempre espera interação do terminal ou 20s hardcoded. Não funciona em ambientes sem TTY (CI, Docker).
- **Impacto:** Benchmarks automatizados falham ou têm comportamento imprevisível em headless environments.

```python
# Adicionar flag --auto no parser:
parser.add_argument("--auto", action="store_true", 
                    help="Modo automático para CI/headless — bypass await enter")

# Em _await_enter():
def _await_enter(auto_mode: bool = False):
    if auto_mode or os.environ.get("FORGE_AUTO_MODE"):
        print("  >> [AUTO MODE] Bypassing manual confirmation...")
        return
    
    try:
        with open("/dev/tty", "r") as tty:
            print("  >> Pressione ENTER após enviar as mensagens no Telegram...", 
                  end="", flush=True)
            tty.readline()
    except OSError:
        print("  >> (sem TTY — aguardando 20s automaticamente...)")
        time.sleep(20)
    print()

# Passar auto_mode para _await_enter(auto_mode=args.auto) em run_telegram_agent
```

---

## 🟡 Prioridade MÉDIA (Planejar)

### M1 — forge_runner.py: Injeção de Variáveis sem Validação
- **Problema:** `auto_evaluate` usa `.format(**fmt_vars)` com dados vindos de cenários JSON externos.
- **Impacto:** Potencial vulnerabilidade se futuramente usar eval/exec; variáveis podem sobrescrever chaves sensíveis.

**Correção proposta (para implementar depois):**
```python
# Whitelist de variáveis permitidas:
ALLOWED_FORMAT_VARS = {"model_slug", "workdir", "port"}  # + extras validados

def _resolve(s: str, fmt_vars: dict) -> str:
    if not isinstance(s, str):
        return s
    
    # Filtrar apenas chaves permitidas
    safe_vars = {k: v for k, v in fmt_vars.items() 
                 if k.startswith("model_") or k.startswith("workdir") or k == "port"}
    
    try:
        result = s.format(**safe_vars)
        # Verificar se todas as variáveis foram resolvidas (não deixar {unknown} no output)
        if "{" in result and "}" in result:
            print(f"  [WARN] Variável não-resolvida em check: {s}")
        return result
    except KeyError as e:
        # Deixar variável intacta se não estiver na whitelist
        return s
```

---

### M2 — forge_runner.py: Limpeza de Portas sem Verificação do Processo
- **Problema:** `_kill_port` usa `fuser -k` que mata QUALQUER processo na porta, não apenas os iniciados pelo runner.
- **Impacto:** Em ambientes compartilhados pode derrubar serviços legítimos usando a mesma porta por coincidência.

**Correção proposta (para implementar depois):**
```python
# Registrar PID dos processos iniciados:
def _extract_server_port_and_pid(command: str) -> tuple[int | None, int | None]:
    """Detecta servidor e retorna (porta, pid_do_processo)."""
    is_server = any(kw in command for kw in ("http.server", "uvicorn"))
    if not is_server:
        return None, None
    
    m = re.search(r"\b(\d{4,5})\b", command)
    port = int(m.group(1)) if m else None
    
    # Iniciar processo e capturar PID (requer subprocess.Popen ao invés de run)
    proc = subprocess.Popen(["bash", "-c", command], ...)
    return port, proc.pid

# Em cleanup: matar apenas PIDs registrados, não usar fuser -k na porta inteira.
```

---

### M3 — forge_claude_runner.py: Tratamento Inadequado de Erros da API Anthropic
- **Problema:** Apenas `anthropic.APIError` é tratado; faltam RateLimitError e outros tipos específicos.
- **Impacto:** Rate limiting (429) causa crash ao invés de retry gracioso com backoff exponencial.

**Correção proposta (para implementar depois):**
```python
# Adicionar tratamento específico:
try:
    resp = client.messages.create(...)
except anthropic.RateLimitError as e:
    wait_time = min(e.retry_after or 60, 300)  # max 5min
    print(f"  [RATE LIMIT] Aguardando {wait_time}s antes de retry...")
    time.sleep(wait_time)
    continue  # Retry no mesmo turn (não incrementa contador)
except anthropic.PermissionError as e:
    error = f"[PERMISSÃO NEGADA] Verifique sua API key Anthropic"
    print(f"ERRO: {error}")
    break
except Exception as e:
    error = f"[API ERROR] {type(e).__name__}: {str(e)[:200]}"
    print(f"ERRO INESPERADO: {error}")
    break
```

---

### M4 — forge_claude_runner.py: Cálculo de Custo Hardcoded para Sonnet
- **Problema:** Preços hardcoded ($3/MT in, $15/MT out) não refletem preços reais por modelo.
- **Impacto:** Relatórios imprecisos para Haiku (mais barato) e Opus (mais caro).

**Correção proposta (para implementar depois):**
```python
# Adicionar dicionário de preços:
CLAUDE_PRICES = {
    "claude-haiku": {"input_per_million": 1.0, "output_per_million": 5.0},
    "claude-sonnet": {"input_per_million": 3.0, "output_per_million": 15.0},
    "claude-opus": {"input_per_million": 15.0, "output_per_million": 75.0},
}

# No cálculo de custo:
model_key = model_id.split("-")[1] if "-" in model_id else "sonnet"
prices = CLAUDE_PRICES.get(model_key, CLAUDE_PRICES["claude-sonnet"])
cost_est = (tok_input * prices["input_per_million"] + 
            tok_output * prices["output_per_million"]) / 1_000_000
```

---

### M5 — forge_mock_server.py: Falta de Tratamento de Erro em stop()/status()
- **Problema:** Conversão `int(PID_FILE.read_text())` pode lançar ValueError se arquivo estiver corrompido.
- **Impacto:** Crash com traceback ao invés de mensagem amigável quando PID file está inválido.

**Correção proposta (para implementar depois):**
```python
def stop():
    if not PID_FILE.exists():
        print("[forge_mock] Servidor não está rodando.")
        return
    
    try:
        pid = int(PID_FILE.read_text().strip())
    except ValueError as e:
        print(f"[forge_mock] Arquivo de PID inválido (removendo): {e}")
        PID_FILE.unlink(missing_ok=True)
        return
        
    # ... resto da função

def status():
    if not PID_FILE.exists():
        print("[forge_mock] Não está rodando.")
        return
    
    try:
        pid = int(PID_FILE.read_text().strip())
    except ValueError as e:
        print(f"[forge_mock] Arquivo de PID inválido (removendo): {e}")
        PID_FILE.unlink(missing_ok=True)
        return
        
    # ... resto da função
```

---

### M6 — forge_telegram_runner.py: Limpeza Incompleta entre Runs
- **Problema:** Apenas arquivos são removidos (`f.unlink()`), diretórios vazios permanecem.
- **Impacto:** Após múltiplos runs, acumulam-se pastas vazias que podem confundir checks de `file_exists`.

**Correção proposta (para implementar depois):**
```python
# Substituir limpeza atual por:
def _cleanup_workdir(workdir: Path):
    """Remove todo conteúdo do workdir exceto fixtures externas."""
    if not workdir.exists():
        return
    
    # Preservar apenas TASK.md se existir (é fixture)
    task_md = workdir / "TASK.md"
    
    for item in list(workdir.iterdir()):
        if item.is_file() and item.name != "TASK.md":
            item.unlink()
        elif item.is_dir():
            shutil.rmtree(item)  # Remove diretórios recursivamente
    
    # Recriar workdir limpo se necessário (opcional, para garantir estado consistente)

# Chamar antes de cada run: _cleanup_workdir(workdir)
```

---

### M7 — forge_telegram_runner.py: Monitoramento Não Detecta Modificações em Arquivos Existentes
- **Problema:** Snapshot usa apenas `st_mtime` que pode não detectar mudanças rápidas ou deletions.
- **Impacto:** Se agente modificar arquivo existente sem criar novos, monitor para prematuramente.

**Correção proposta (para implementar depois):**
```python
import hashlib

def _workdir_snapshot(workdir: Path) -> dict[str, str]:
    """Retorna hash de conteúdo de cada arquivo (detecta mudanças reais)."""
    snap = {}
    for f in workdir.rglob("*"):
        if f.is_file():
            try:
                # Hash do conteúdo em vez de timestamp
                content_hash = hashlib.md5(f.read_bytes()).hexdigest()[:12]
                snap[str(f)] = content_hash
            except OSError as e:
                print(f"  [WARN] Não pôde ler {f}: {e}")
    return snap

# Em wait_for_workdir, comparar hashes em vez de timestamps.
```

---

## 🟢 Prioridade BAIXA (Registrar como Backlog)

### B1 — forge_runner.py: Documentação Desatualizada no Docstring
- **Problema:** Docstring menciona "Fixes v0.2" sem versão atual ou changelog claro.
- **Impacto:** Desenvolvedores podem achar que bugs estão resolvidos quando documentação está desatualizada.

**Correção proposta (para implementar depois):**
```python
"""
FORGE — Framework for Open Real-world Generic Evaluation v0.3-dev
Runner principal: executa cenários com loop de tool use real via Ollama API.

Changelog recente:
  - v0.2.x: Adicionado suporte a --runs N, cleanup automático de portas
  - v0.1.x: Implementação inicial das ferramentas run_bash, write_file, etc.

TODO (v0.3):
  [ ] Melhorar tratamento de erros HTTP com status codes específicos
  [ ] Extrair código compartilhado para forge_common.py
"""
```

---

### B2 — forge_claude_runner.py: Mensagem de Erro Genérica para API Key
- **Problema:** Não há instruções claras sobre como configurar ANTHROPIC_API_KEY.
- **Impacto:** Novos usuários ficam confusos, aumentando tempo de setup.

**Correção proposta (para implementar depois):**
```python
# Substituir mensagem atual por:
if not api_key:
    raise RuntimeError(
        "ANTHROPIC_API_KEY não definida.\n"
        "Configure no seu ambiente:\n"
        "  export ANTHROPIC_API_KEY='sk-ant-...'\n"
        "Ou crie um arquivo .env com a chave.\n"
        "Obtenha sua key em: https://console.anthropic.com/settings/keys"
    )
```

---

### B3 — forge_mock_server.py: Importação `os` Fora do Topo (PEP 8)
- **Problema:** `import os` está no final do arquivo ao invés de junto com outras importações.
- **Impacto:** Viola convenções PEP 8, dificulta leitura e manutenção.

**Correção proposta (para implementar depois):**
```python
# Mover para o topo:
import argparse
import json
import os  # ← mover daqui
import signal
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

# Remover do final do arquivo.
```

---

### B4 — forge_telegram_runner.py: Variável `checks_key` Hardcoded e Frágil
- **Problema:** String `"aurelia_auto_checks"` hardcoded sem validação de conflito com `auto_checks`.
- **Impacto:** Cenários malformados podem ter comportamento inesperado.

**Correção proposta (para implementar depois):**
```python
# Adicionar warning e documentação:
checks_key = "aurelia_auto_checks"  # LEGACY — use 'auto_checks' em novos cenários

if checks_key in scenario and "auto_checks" in scenario:
    print(f"  [WARN] Cenário {sid} tem ambas '{checks_key}' e 'auto_checks'.")
    print(f"         Usando '{checks_key}' (legado). Remova uma das chaves.")

# Documentar em TASK.md que aurelia_auto_checks será removido na próxima versão.
```

---

## Checklist de Implementação

### Alta Prioridade ✅ (Implementadas)
- [x] A1: forge_runner.py — Proteção expandida para run_bash
- [x] A2: forge_runner.py — Tratamento específico de erros HTTP
- [x] A3: forge_claude_runner.py — Documentação sobre acoplamento (não criar novo arquivo)
- [x] A4: forge_mock_server.py — Health check verifica fixtures
- [x] A5: forge_telegram_runner.py — Flag --auto para CI/headless

### Média Prioridade 📋 (Pendentes)
- [ ] M1: forge_runner.py — Validação de variáveis em auto_evaluate
- [ ] M2: forge_runner.py — Limpeza segura de portas por PID
- [ ] M3: forge_claude_runner.py — Tratamento específico para RateLimitError
- [ ] M4: forge_claude_runner.py — Preços dinâmicos por modelo Claude
- [ ] M5: forge_mock_server.py — Tratamento ValueError em stop()/status()
- [ ] M6: forge_telegram_runner.py — Limpeza completa entre runs (shutil.rmtree)
- [ ] M7: forge_telegram_runner.py — Monitoramento com hash de conteúdo

### Baixa Prioridade 🗂️ (Backlog)
- [ ] B1: forge_runner.py — Atualizar docstring com versão e changelog
- [ ] B2: forge_claude_runner.py — Melhorar mensagem de erro API key
- [ ] B3: forge_mock_server.py — Mover import os para o topo (PEP 8)
- [ ] B4: forge_telegram_runner.py — Warning sobre checks_key legado

---

## Notas Finais

**Correções implementadas nesta tarefa:** Apenas as de **Alta Prioridade**, conforme especificado em TASK.md. As correções de Média e Baixa prioridade estão documentadas aqui para implementação futura, mas não foram alteradas no código-fonte (conforme regra "implementar apenas Alta").

**Arquivos modificados:**
- `forge_runner.py` — Correções A1, A2
- `forge_claude_runner.py` — Correção A3 (documentação)
- `forge_mock_server.py` — Correção A4
- `forge_telegram_runner.py` — Correção A5

**Arquivos criados:**
- `code_review.md` ✅
- `plano_correcoes.md` ✅
- `quality_report.md` (próximo passo)
