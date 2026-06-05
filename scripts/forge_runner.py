"""
FORGE — Framework for Open Real-world Generic Evaluation
Runner principal: executa cenários com loop de tool use real via Ollama API.

Uso:
    python3 forge_runner.py <modelo> --scenario F1
    python3 forge_runner.py <modelo> --scenario F1 F2 F3 --runs 3
    python3 forge_runner.py <modelo> --all --runs 3

Fixes v0.2:
    - BUG: {model_slug} agora substituído em auto_evaluate() [era crítico]
    - SEGURANÇA: run_bash com blocklist de comandos destrutivos
    - OVERFLOW: http_get trunca e extrai texto de HTML (max 4000 chars)
    - CLEANUP: servidores HTTP iniciados em background são encerrados pós-run
    - K RUNS: --runs N executa múltiplos runs e agrega scores (mean ± std)
    - MOCK: URLs de fixtures locais para F2/F3 (ver forge_mock_server.py)
"""

import argparse
import datetime
import json
import os
import re
import signal
import statistics
import subprocess
import time
import urllib.request
import urllib.parse
from html.parser import HTMLParser
from pathlib import Path

# ── Configuração ──────────────────────────────────────────────
OLLAMA_URL    = "http://localhost:11434/api/chat"
RESULTS_BASE   = Path(__file__).parent.parent / "results"
SCENARIOS_BASE = Path(__file__).parent.parent / "scenarios"
MAX_TURNS     = 20
TIMEOUT_S     = 300
TEMPERATURE   = 0
HTTP_MAX_CHARS = 4000   # truncamento de respostas HTTP para evitar context overflow

# Blocklist de comandos destrutivos para run_bash
_BASH_BLOCKLIST = [
    r"rm\s+-[a-z]*rf",      # rm -rf
    r"rm\s+-[a-z]*fr",      # rm -fr
    r":\(\)\s*\{",          # fork bomb
    r"dd\s+if=/dev/",       # dd sobre dispositivo
    r"mkfs",                # formatar disco
    r"fdisk",               # particionamento
    r">\s*/dev/sd",         # escrita direta em disco
    r"wget\s+.*\|\s*bash",  # wget pipe bash
    r"curl\s+.*\|\s*bash",  # curl pipe bash
    r"curl\s+.*\|\s*sh",    # curl pipe sh
    r"chmod\s+777\s+/",     # chmod 777 na raiz
    r"sudo\s+rm",           # sudo rm
    r"shutdown",            # desligar máquina
    r"reboot",              # reiniciar
]

def _load_telegram():
    cfg = Path.home() / ".aurelia/config/app.json"
    try:
        d = json.loads(cfg.read_text())
        return d.get("telegram_bot_token", ""), d.get("telegram_allowed_user_ids", [])[0]
    except:
        return "", ""

TELEGRAM_TOKEN, TELEGRAM_CHAT_ID = _load_telegram()


# ── Definição das ferramentas ─────────────────────────────────
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "run_bash",
            "description": (
                "Executa um comando bash no servidor local e retorna o stdout. "
                "Use para criar diretórios, executar scripts Python, iniciar servidores, "
                "verificar portas, rodar testes, etc. "
                "Comandos destrutivos (rm -rf, dd, mkfs) são bloqueados."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "Comando bash a executar."}
                },
                "required": ["command"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": (
                "Escreve conteúdo em um arquivo no diretório de trabalho do cenário. "
                "Use caminhos relativos (ex: 'index.html', 'subdir/app.py'). "
                "Cria diretórios intermediários automaticamente."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path":    {"type": "string", "description": "Caminho relativo do arquivo."},
                    "content": {"type": "string", "description": "Conteúdo a escrever."}
                },
                "required": ["path", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Lê o conteúdo de um arquivo no diretório de trabalho.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Caminho relativo do arquivo."}
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "http_get",
            "description": (
                "Faz uma requisição HTTP GET e retorna o conteúdo como texto. "
                "HTML é automaticamente convertido para texto limpo. "
                "Resposta limitada a 4000 chars para preservar contexto."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "url":     {"type": "string", "description": "URL completa."},
                    "headers": {"type": "object", "description": "Headers opcionais.", "default": {}}
                },
                "required": ["url"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "http_post",
            "description": "Faz uma requisição HTTP POST com body JSON.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url":     {"type": "string"},
                    "body":    {"type": "object", "description": "Body JSON."},
                    "headers": {"type": "object", "default": {}}
                },
                "required": ["url", "body"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "append_file",
            "description": (
                "Adiciona conteúdo ao final de um arquivo existente no diretório de trabalho. "
                "Use quando o conteúdo for grande demais para um único write_file, "
                "escrevendo o arquivo em múltiplos chunks. "
                "Se o arquivo não existir, ele é criado."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path":    {"type": "string", "description": "Caminho relativo do arquivo."},
                    "content": {"type": "string", "description": "Conteúdo a adicionar ao final."}
                },
                "required": ["path", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "send_claudio",
            "description": (
                "Envia uma mensagem de texto pelo bot Telegram do Claudio. "
                "Use para notificar o usuário sobre o resultado de uma tarefa."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "message": {"type": "string", "description": "Mensagem a enviar (suporta Markdown)."}
                },
                "required": ["message"]
            }
        }
    },
]


# ── Utilitários ───────────────────────────────────────────────
class _HTMLTextExtractor(HTMLParser):
    """Extrai texto limpo de HTML, descartando scripts, estilos e boilerplate."""
    SKIP_TAGS = {"script", "style", "nav", "footer", "head", "meta", "link", "noscript"}

    def __init__(self):
        super().__init__()
        self._skip_depth = 0
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP_TAGS:
            self._skip_depth += 1

    def handle_endtag(self, tag):
        if tag in self.SKIP_TAGS and self._skip_depth > 0:
            self._skip_depth -= 1

    def handle_data(self, data):
        if self._skip_depth == 0:
            text = data.strip()
            if text:
                self.parts.append(text)

    def get_text(self) -> str:
        return "\n".join(self.parts)


def _html_to_text(raw: str) -> str:
    """Converte HTML em texto limpo. Retorna raw se não parecer HTML."""
    if "<html" not in raw.lower() and "<body" not in raw.lower():
        return raw
    try:
        extractor = _HTMLTextExtractor()
        extractor.feed(raw)
        text = extractor.get_text()
        # Colapsar linhas em branco múltiplas
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text if text.strip() else raw
    except Exception:
        return raw


def _check_bash_safety(command: str) -> str | None:
    """Retorna mensagem de erro se o comando for bloqueado, None se seguro."""
    cmd_lower = command.lower()
    for pattern in _BASH_BLOCKLIST:
        if re.search(pattern, cmd_lower):
            return f"[BLOQUEADO] Comando não permitido (padrão: {pattern}). Use comandos seguros."
    return None


def _extract_server_port(command: str) -> int | None:
    """Detecta se o comando sobe um servidor e extrai a porta."""
    is_server = any(kw in command for kw in ("http.server", "uvicorn", "gunicorn", "flask run"))
    if not is_server:
        return None
    m = re.search(r"\b(\d{4,5})\b", command)
    return int(m.group(1)) if m else None


def _kill_port(port: int):
    """Encerra processo escutando na porta especificada."""
    try:
        subprocess.run(["fuser", "-k", f"{port}/tcp"],
                       capture_output=True, timeout=5)
    except Exception:
        pass


# ── Implementação das ferramentas ─────────────────────────────
def exec_run_bash(command: str, workdir: Path, cleanup_ports: list) -> str:
    if not command or not command.strip():
        return "[ERRO] Parâmetro 'command' é obrigatório e não pode ser vazio."
    # Fix SEGURANÇA: blocklist de comandos destrutivos
    block_msg = _check_bash_safety(command)
    if block_msg:
        return block_msg

    # Proteger fixtures contra escrita via bash (>, tee, cp sobrescrevendo)
    for protected in _PROTECTED_FILES:
        if re.search(rf"[>|]\s*['\"]?.*{re.escape(protected)}['\"]?", command):
            return f"[BLOQUEADO] '{protected}' é um arquivo de fixture protegido."

    # Registrar porta para cleanup pós-run
    port = _extract_server_port(command)
    if port and port not in cleanup_ports:
        cleanup_ports.append(port)

    try:
        result = subprocess.run(
            ["bash", "-c", command],
            capture_output=True, text=True,
            timeout=TIMEOUT_S, cwd=workdir
        )
        out = result.stdout
        if result.returncode != 0 and result.stderr:
            out += f"\n[STDERR] {result.stderr.strip()}"
        return out or "(sem output)"
    except subprocess.TimeoutExpired:
        return f"[ERRO] Timeout após {TIMEOUT_S}s"
    except Exception as e:
        return f"[ERRO] {e}"


# Arquivos de fixture que nunca devem ser sobrescritos pelo agente
_PROTECTED_FILES = {"validate.py", "TASK.md"}


def exec_write_file(path: str, content: str, workdir: Path) -> str:
    if not path or not path.strip():
        return "[ERRO] Parâmetro 'path' é obrigatório."
    if not content:
        return "[ERRO] Parâmetro 'content' é obrigatório e não pode ser vazio. Inclua o conteúdo completo do arquivo no parâmetro 'content'."
    target = (workdir / path).resolve()
    if not str(target).startswith(str(workdir.resolve())):
        return "[ERRO] Caminho fora do diretório de trabalho."
    if target.is_dir():
        return f"[ERRO] '{path}' é um diretório, não um arquivo."
    if target.name in _PROTECTED_FILES:
        return f"[ERRO] '{target.name}' é um arquivo de fixture protegido e não pode ser modificado."
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return f"OK: {path} ({len(content)} chars, {content.count(chr(10))+1} linhas)"


def exec_append_file(path: str, content: str, workdir: Path) -> str:
    if not path or not path.strip():
        return "[ERRO] Parâmetro 'path' é obrigatório."
    if not content:
        return "[ERRO] Parâmetro 'content' é obrigatório e não pode ser vazio."
    target = (workdir / path).resolve()
    if not str(target).startswith(str(workdir.resolve())):
        return "[ERRO] Caminho fora do diretório de trabalho."
    if target.is_dir():
        return f"[ERRO] '{path}' é um diretório, não um arquivo."
    if target.name in _PROTECTED_FILES:
        return f"[ERRO] '{target.name}' é um arquivo de fixture protegido e não pode ser modificado."
    target.parent.mkdir(parents=True, exist_ok=True)
    with open(target, "a", encoding="utf-8") as f:
        f.write(content)
    total = target.stat().st_size
    return f"OK: appended {len(content)} chars to {path} (total: {total} bytes)"


READ_MAX_CHARS = 8_000   # padrão; sobrescrito por cenários que leem arquivos grandes


def exec_read_file(path: str, workdir: Path, max_chars: int | None = None) -> str:
    target = (workdir / path).resolve()
    if not str(target).startswith(str(workdir.resolve())):
        return "[ERRO] Caminho fora do diretório de trabalho."
    if not target.exists():
        return f"[ERRO] Arquivo não encontrado: {path}"
    content = target.read_text(encoding="utf-8")
    limit = max_chars or READ_MAX_CHARS
    if len(content) > limit:
        content = content[:limit] + f"\n... [truncado — {len(content)} chars total]"
    return content


def exec_http_get(url: str, headers: dict) -> str:
    try:
        req = urllib.request.Request(url, headers=headers or {})
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read().decode("utf-8", errors="replace")
    except Exception as e:
        return f"[ERRO] {e}"

    # Fix OVERFLOW: converter HTML para texto limpo e truncar
    text = _html_to_text(raw)
    if len(text) > HTTP_MAX_CHARS:
        text = text[:HTTP_MAX_CHARS] + f"\n... [truncado — {len(text)} chars total]"
    return text


def exec_http_post(url: str, body: dict, headers: dict) -> str:
    try:
        data = json.dumps(body).encode()
        h = {"Content-Type": "application/json"}
        h.update(headers or {})
        req = urllib.request.Request(url, data=data, headers=h, method="POST")
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.read().decode("utf-8", errors="replace")[:4000]
    except Exception as e:
        return f"[ERRO] {e}"


def exec_send_claudio(message: str) -> str:
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return "[ERRO] Credenciais Telegram não disponíveis."
    try:
        data = urllib.parse.urlencode({
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "Markdown"
        }).encode()
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            data=data
        )
        with urllib.request.urlopen(req, timeout=15) as r:
            resp = json.loads(r.read())
            return f"Mensagem enviada. message_id={resp.get('result',{}).get('message_id','?')}"
    except Exception as e:
        return f"[ERRO] {e}"


def dispatch_tool(name: str, args: dict, workdir: Path, cleanup_ports: list,
                  read_max_chars: int | None = None) -> str:
    if name == "run_bash":
        return exec_run_bash(args.get("command", ""), workdir, cleanup_ports)
    if name == "write_file":
        return exec_write_file(args.get("path", ""), args.get("content", ""), workdir)
    if name == "append_file":
        return exec_append_file(args.get("path", ""), args.get("content", ""), workdir)
    if name == "read_file":
        return exec_read_file(args.get("path", ""), workdir, max_chars=read_max_chars)
    if name == "http_get":
        return exec_http_get(args.get("url", ""), args.get("headers", {}))
    if name == "http_post":
        return exec_http_post(args.get("url", ""), args.get("body", {}), args.get("headers", {}))
    if name == "send_claudio":
        return exec_send_claudio(args.get("message", ""))
    return f"[ERRO] Ferramenta desconhecida: {name}"


# ── Chamada à API Ollama ──────────────────────────────────────
def call_ollama(model: str, messages: list) -> dict:
    payload = {
        "model":    model,
        "messages": messages,
        "tools":    TOOLS,
        "stream":   False,
        "think":    False,
        "options":  {"temperature": TEMPERATURE}
    }
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        OLLAMA_URL, data=data,
        headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode()[:300]
        raise RuntimeError(f"HTTP {e.code}: {body}")
    except Exception as e:
        raise RuntimeError(str(e))


def extract_tool_calls(resp: dict) -> list:
    calls = []
    for tc in resp.get("message", {}).get("tool_calls", []):
        fn   = tc.get("function", {})
        name = fn.get("name", "")
        args = fn.get("arguments", {})
        if isinstance(args, str):
            try:    args = json.loads(args)
            except: args = {"_raw": args}
        calls.append({"name": name, "arguments": args})
    return calls


# ── Loop principal do agente ──────────────────────────────────
def run_agent(model: str, scenario_id: str, prompt: str, workdir: Path,
              read_max_chars: int | None = None) -> dict:
    messages       = [{"role": "user", "content": prompt}]
    t_start        = time.time()
    turns          = 0
    tool_calls_log = []
    final_response = ""
    error          = None
    tok_total      = 0
    cleanup_ports  = []   # Fix CLEANUP: portas a encerrar após o run

    print(f"\n  [agente] iniciando loop (max {MAX_TURNS} turns)")

    try:
        while turns < MAX_TURNS:
            turns += 1
            print(f"  [turn {turns}] chamando API...", end=" ", flush=True)

            try:
                resp = call_ollama(model, messages)
            except RuntimeError as e:
                error = str(e)
                print(f"ERRO: {error}")
                break

            tok_total += resp.get("eval_count", 0) + resp.get("prompt_eval_count", 0)
            msg       = resp.get("message", {})
            content   = msg.get("content") or ""
            tc_list   = extract_tool_calls(resp)

            if not tc_list:
                final_response = content
                print(f"resposta final ({len(content)} chars)")
                messages.append({"role": "assistant", "content": content})
                break

            print(f"{len(tc_list)} tool(s): {[t['name'] for t in tc_list]}")
            messages.append({
                "role": "assistant",
                "content": content,
                "tool_calls": resp["message"].get("tool_calls", [])
            })

            for tc in tc_list:
                name   = tc["name"]
                args   = tc["arguments"]
                print(f"    → {name}({list(args.keys())})", end=" ... ", flush=True)
                result = dispatch_tool(name, args, workdir, cleanup_ports,
                                      read_max_chars=read_max_chars)
                print(f"({len(str(result))} chars)")

                tool_calls_log.append({
                    "turn":   turns,
                    "name":   name,
                    "args":   {k: str(v)[:200] for k, v in args.items()},
                    "result": str(result)[:500]
                })
                messages.append({"role": "tool", "content": str(result)})
        else:
            print(f"  [agente] loop expirado após {MAX_TURNS} turns")

    finally:
        # Fix CLEANUP: encerrar servidores iniciados durante o run
        for port in cleanup_ports:
            print(f"  [cleanup] encerrando servidor na porta {port}")
            _kill_port(port)

    duration_ms = int((time.time() - t_start) * 1000)
    return {
        "turns":          turns,
        "tool_calls":     tool_calls_log,
        "final_response": final_response,
        "error":          error,
        "duration_ms":    duration_ms,
        "tok_total":      tok_total,
        "loop_exhausted": turns >= MAX_TURNS and not final_response,
        "cleanup_ports":  cleanup_ports,
    }


# ── Carregamento de cenários ──────────────────────────────────
def load_scenario(scenario_id: str) -> dict:
    path = Path(__file__).parent.parent / "scenarios" / f"{scenario_id}.json"
    if not path.exists():
        raise FileNotFoundError(f"Cenário não encontrado: {path}")
    return json.loads(path.read_text())


# ── Avaliação automática ──────────────────────────────────────
def auto_evaluate(scenario: dict, workdir: Path, agent_result: dict, slug: str,
                  extra_vars: dict | None = None) -> dict:
    """
    Executa os checks automáticos definidos no cenário.
    extra_vars permite substituir variáveis adicionais (ex: port, workdir).
    """
    checks    = scenario.get("auto_checks", [])
    results   = {}
    score     = 0
    max_score = 0

    fmt_vars = {"model_slug": slug, "workdir": str(workdir)}
    if extra_vars:
        fmt_vars.update(extra_vars)

    for check in checks:
        ctype  = check["type"]
        label  = check["label"]
        weight = check.get("weight", 1)
        max_score += weight
        passed = False
        detail = ""

        def _resolve(s: str) -> str:
            if not isinstance(s, str):
                return s
            try:
                return s.format(**fmt_vars)
            except KeyError:
                return s  # deixa a variável não-resolvida intacta

        if ctype == "file_exists":
            path_resolved = _resolve(check["path"])
            p = workdir / path_resolved
            passed = p.exists()
            detail = f"{path_resolved} {'existe' if passed else 'NÃO existe'}"

        elif ctype == "file_contains":
            path_resolved = _resolve(check["path"])
            p = workdir / path_resolved
            if p.exists():
                content = p.read_text(errors="replace")
                needle  = check["needle"]
                passed  = needle.lower() in content.lower()
                detail  = f"'{needle}' {'encontrado' if passed else 'NÃO encontrado'} em {path_resolved}"
            else:
                detail = f"arquivo não encontrado: {path_resolved}"

        elif ctype == "http_ok":
            url = _resolve(check["url"])
            try:
                with urllib.request.urlopen(url, timeout=10) as r:
                    passed = r.status == 200
                    detail = f"HTTP {r.status}"
            except Exception as e:
                detail = str(e)

        elif ctype == "tool_called":
            tool_name = check["tool"]
            passed = any(t["name"] == tool_name for t in agent_result["tool_calls"])
            detail = f"tool '{tool_name}' {'chamada' if passed else 'NÃO chamada'}"

        elif ctype == "response_contains":
            needle = check["needle"]
            passed = needle.lower() in agent_result["final_response"].lower()
            detail = f"'{needle}' {'encontrado' if passed else 'NÃO encontrado'} na resposta final"

        elif ctype == "file_size_min":
            path_resolved = _resolve(check["path"])
            p   = workdir / path_resolved
            min_bytes = check["min_bytes"]
            if p.exists():
                size   = p.stat().st_size
                passed = size >= min_bytes
                detail = f"{path_resolved}: {size} bytes ({'≥' if passed else '<'} {min_bytes})"
            else:
                detail = f"arquivo não encontrado: {path_resolved}"

        elif ctype == "file_contains_count":
            path_resolved = _resolve(check["path"])
            p         = workdir / path_resolved
            needle    = check["needle"]
            min_count = check.get("min_count", 1)
            if p.exists():
                content = p.read_text(errors="replace")
                count   = content.lower().count(needle.lower())
                passed  = count >= min_count
                detail  = f"'{needle}' aparece {count}x em {path_resolved} (mín {min_count})"
            else:
                detail = f"arquivo não encontrado: {path_resolved}"

        elif ctype == "port_open":
            import socket
            port = int(_resolve(str(check["port"])))
            try:
                with socket.create_connection(("localhost", port), timeout=3):
                    passed = True
                    detail = f"porta {port} aberta"
            except OSError:
                detail = f"porta {port} fechada"

        elif ctype == "file_unchanged":
            import hashlib
            path_resolved = _resolve(check["path"])
            ref_resolved  = _resolve(check["ref"])
            p   = workdir / path_resolved
            ref = SCENARIOS_BASE / ref_resolved
            if not p.exists():
                detail = f"{path_resolved} não existe"
            elif not ref.exists():
                detail = f"referência não encontrada: {ref_resolved}"
            else:
                h_cur = hashlib.md5(p.read_bytes()).hexdigest()
                h_ref = hashlib.md5(ref.read_bytes()).hexdigest()
                passed = h_cur == h_ref
                detail = "inalterado" if passed else f"modificado (md5 {h_cur[:8]} ≠ {h_ref[:8]})"

        elif ctype == "run_command_ok":
            import subprocess
            cmd = _resolve(check["cmd"]).format(workdir=str(workdir))
            expect = check.get("expect_output", "")
            try:
                r = subprocess.run(
                    cmd, shell=True, capture_output=True,
                    text=True, timeout=30, cwd=str(workdir)
                )
                out = (r.stdout + r.stderr).strip()
                if expect:
                    passed = r.returncode == 0 and expect.lower() in out.lower()
                else:
                    passed = r.returncode == 0
                detail = f"exit {r.returncode}: {out[:120]}"
            except subprocess.TimeoutExpired:
                detail = "timeout (30s)"
            except Exception as e:
                detail = str(e)

        elif ctype == "no_error":
            passed = agent_result["error"] is None
            detail = agent_result["error"] or "sem erro"

        if passed:
            score += weight

        results[label] = {"passed": passed, "weight": weight, "detail": detail}

    return {
        "score":     score,
        "max_score": max_score,
        "pct":       round(score / max_score * 100) if max_score else 0,
        "checks":    results
    }


# ── Salvar resultado de um run ────────────────────────────────
def save_run_result(scenario_id: str, model: str, run_idx: int, workdir: Path,
                    agent_result: dict, auto_eval: dict, scenario: dict) -> Path:
    slug    = model.replace(":", "-").replace("/", "_")
    ts      = datetime.datetime.now().strftime("%Y-%m-%d")
    out_dir = RESULTS_BASE / scenario_id / slug
    out_dir.mkdir(parents=True, exist_ok=True)

    summary = {
        "scenario":       scenario_id,
        "scenario_name":  scenario.get("name", ""),
        "model":          model,
        "run_idx":        run_idx,
        "date":           ts,
        "turns":          agent_result["turns"],
        "tool_calls_n":   len(agent_result["tool_calls"]),
        "loop_exhausted": agent_result["loop_exhausted"],
        "error":          agent_result["error"],
        "duration_ms":    agent_result["duration_ms"],
        "tok_total":      agent_result["tok_total"],
        "tok_per_s":      round(agent_result["tok_total"] / (agent_result["duration_ms"] / 1000), 1)
                          if agent_result["duration_ms"] else None,
        "auto_score":     auto_eval["score"],
        "auto_max":       auto_eval["max_score"],
        "auto_pct":       auto_eval["pct"],
        "auto_checks":    auto_eval["checks"],
        "tool_calls_log": agent_result["tool_calls"],
        "final_response": agent_result["final_response"][:2000],
        "llm_judge_score":  None,
        "claude_score":     None,
        "human_score":      None,
        "composite_score":  None,
        "notes":            ""
    }

    fname    = f"{scenario_id}-{slug}-{ts}-run{run_idx}.json"
    out_file = out_dir / fname
    out_file.write_text(json.dumps(summary, indent=2, ensure_ascii=False))
    return out_file


def aggregate_runs(run_results: list[dict]) -> dict:
    """Agrega múltiplos runs: mean ± std para scores automáticos."""
    pcts   = [r["auto_pct"]   for r in run_results]
    scores = [r["auto_score"] for r in run_results]
    return {
        "runs":           len(run_results),
        "auto_pct_mean":  round(statistics.mean(pcts), 1),
        "auto_pct_std":   round(statistics.stdev(pcts), 1) if len(pcts) > 1 else 0.0,
        "auto_score_mean": round(statistics.mean(scores), 2),
        "auto_score_std":  round(statistics.stdev(scores), 2) if len(scores) > 1 else 0.0,
        "errors":         sum(1 for r in run_results if r.get("error")),
        "loop_exhausted": sum(1 for r in run_results if r.get("loop_exhausted")),
    }


# ── Entry point ───────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="FORGE runner v0.2")
    parser.add_argument("model",        help="Nome do modelo Ollama (ex: gemma4:26b)")
    parser.add_argument("--scenario",   nargs="+", help="Cenário(s) a executar (ex: F1 F2)")
    parser.add_argument("--all",        action="store_true", help="Executar todos os cenários")
    parser.add_argument("--runs",       type=int, default=1,
                        help="Número de runs por cenário para medir estabilidade (default: 1, recomendado: 3)")
    parser.add_argument("--port-base",  type=int, default=8200,
                        help="Porta base para servidores web (default: 8200)")
    parser.add_argument("--mock",       action="store_true",
                        help="Usar servidor de mock local (porta 9900) para F2/F3")
    args = parser.parse_args()

    model = args.model
    slug  = model.replace(":", "-").replace("/", "_")

    if args.all:
        scenario_ids = [p.stem for p in sorted(
            (Path(__file__).parent.parent / "scenarios").glob("*.json")
        )]
    elif args.scenario:
        scenario_ids = args.scenario
    else:
        parser.error("Especifique --scenario F1 ou --all")

    print(f"\n{'='*62}")
    print(f"  FORGE v0.2 — Framework for Open Real-world Generic Evaluation")
    print(f"  Modelo    : {model}")
    print(f"  Cenários  : {', '.join(scenario_ids)}")
    print(f"  Runs/cen. : {args.runs}")
    print(f"  Max turns : {MAX_TURNS}")
    print(f"  Mock URLs : {'SIM (porta 9900)' if args.mock else 'NÃO (URLs reais)'}")
    print(f"{'='*62}")

    if args.runs < 3:
        print(f"\n  ⚠ AVISO: --runs {args.runs} — recomendado --runs 3 para resultados estáveis.\n")

    for i, sid in enumerate(scenario_ids):
        print(f"\n{'─'*62}")
        try:
            scenario = load_scenario(sid)
        except FileNotFoundError as e:
            print(f"  ERRO: {e}")
            continue

        port    = args.port_base + i
        workdir = RESULTS_BASE / sid / slug / "workdir"
        workdir.mkdir(parents=True, exist_ok=True)

        # Copiar fixtures de diretório para o workdir
        import shutil
        for fixture_rel in scenario.get("fixture_dirs", []):
            src = SCENARIOS_BASE / fixture_rel
            dst = workdir / src.name
            if dst.exists():
                shutil.rmtree(dst)
            shutil.copytree(src, dst)
            print(f"  [fixture] copiado: {src.name}/ → {dst.name}/")

        # Copiar PRD como TASK.md se definido
        prd_rel = scenario.get("prd_file")
        if prd_rel:
            prd_src = SCENARIOS_BASE / prd_rel
            prd_dst = workdir / "TASK.md"
            shutil.copy(prd_src, prd_dst)
            print(f"  [prd] copiado: {prd_src.name} → TASK.md")

        # Substituir variáveis no prompt
        prompt_vars = dict(scenario.get("prompt_vars", {}))
        if args.mock:
            prompt_vars.update(scenario.get("prompt_vars_mock", {}))

        prompt = scenario["prompt"].format(
            model_slug=slug,
            port=port,
            workdir=str(workdir),
            **prompt_vars
        )

        print(f"  [{sid}] {scenario['name']}")
        print(f"  workdir : {workdir}")
        print(f"  prompt  : {prompt[:100]}...")

        run_summaries = []

        for run_idx in range(1, args.runs + 1):
            if args.runs > 1:
                print(f"\n  ── Run {run_idx}/{args.runs} ──")

            read_max = scenario.get("read_max_chars")
            agent_result = run_agent(model, sid, prompt, workdir,
                                     read_max_chars=read_max)
            auto_eval    = auto_evaluate(scenario, workdir, agent_result, slug,
                                         extra_vars={"port": port})
            out_file     = save_run_result(sid, model, run_idx, workdir,
                                           agent_result, auto_eval, scenario)

            run_summaries.append({**auto_eval, "error": agent_result["error"],
                                   "loop_exhausted": agent_result["loop_exhausted"]})

            print(f"\n  Auto score : {auto_eval['score']}/{auto_eval['max_score']} ({auto_eval['pct']}%)")
            for label, c in auto_eval["checks"].items():
                mark = "✓" if c["passed"] else "✗"
                print(f"    {mark} {label}: {c['detail']}")
            print(f"  Salvo em   : {out_file.name}")

            # Pausa entre runs para limpar contexto de VRAM
            if run_idx < args.runs:
                print(f"  [pausa 30s entre runs]")
                time.sleep(30)

        # Agregado final
        if args.runs > 1:
            agg = aggregate_runs(run_summaries)
            print(f"\n  ── Agregado {sid} ({args.runs} runs) ──")
            print(f"  AUTO mean  : {agg['auto_pct_mean']}% ± {agg['auto_pct_std']}%")
            print(f"  Erros      : {agg['errors']}/{args.runs}")
            print(f"  Loop exh.  : {agg['loop_exhausted']}/{args.runs}")

    print(f"\n{'='*62}")
    print(f"  Pipeline concluído.")
    print(f"{'='*62}\n")


if __name__ == "__main__":
    main()
