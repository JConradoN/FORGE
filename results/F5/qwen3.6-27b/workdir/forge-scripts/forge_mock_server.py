"""
FORGE Mock Server — serve fixtures locais para F2 e F3.

Substitui dependências externas por snapshots versionados, garantindo
que todos os modelos recebam exatamente a mesma entrada.

Uso:
    python3 forge_mock_server.py &          # inicia em background
    python3 forge_mock_server.py --stop     # encerra

Porta: 9900
Endpoints:
    GET /mock/github-n8n                   → fixture GitHub n8n (F2)
    GET /mock/usd-brl                      → cotação USD/BRL snapshot (F3)
    GET /mock/eur-brl                      → cotação EUR/BRL snapshot (F3)
    GET /mock/btc-brl                      → cotação BTC/BRL snapshot (F3)
    GET /mock/eth-brl                      → cotação ETH/BRL snapshot (F3)
    GET /mock/usd-brl-7d                   → histórico 7 dias USD (F3)
    GET /health                            → {"status": "ok"}
"""

import argparse
import json
import signal
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

MOCK_PORT  = 9900
FIXTURES   = Path(__file__).parent.parent / "fixtures"
PID_FILE   = Path("/tmp/forge_mock_server.pid")


class MockHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass  # silenciar logs para não poluir output do runner

    def do_GET(self):
        path = self.path.rstrip("/")

        if path == "/health":
            self._respond(200, "application/json", json.dumps({"status": "ok"}))

        elif path == "/mock/github-n8n":
            f = FIXTURES / "github-n8n" / "page-snapshot.txt"
            self._serve_file(f, "text/plain")

        elif path in ("/mock/usd-brl", "/mock/eur-brl", "/mock/btc-brl", "/mock/eth-brl"):
            pair_key  = path.split("/")[-1].upper().replace("-", "")
            pair_dash = path.split("/")[-1].upper()
            data = self._load_market()
            pair_data = data.get("pairs", {}).get(pair_dash, {})
            # Formato idêntico ao awesomeapi real
            self._respond(200, "application/json",
                          json.dumps({pair_key: pair_data}))

        elif path == "/mock/usd-brl-7d":
            data = self._load_market()
            self._respond(200, "application/json",
                          json.dumps(data.get("usd_history_7d", [])))

        else:
            self._respond(404, "text/plain", f"Mock endpoint não encontrado: {path}")

    def _serve_file(self, path: Path, content_type: str):
        if not path.exists():
            self._respond(404, "text/plain", f"Fixture não encontrada: {path}")
            return
        self._respond(200, content_type, path.read_text(encoding="utf-8"))

    def _load_market(self) -> dict:
        f = FIXTURES / "market" / "market-snapshot.json"
        if f.exists():
            return json.loads(f.read_text())
        return {}

    def _respond(self, code: int, content_type: str, body: str):
        data = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("X-Forge-Mock", "1")
        self.send_header("X-Fixture-Date", "2026-06-04")
        self.end_headers()
        self.wfile.write(data)


def start():
    PID_FILE.write_text(str(os.getpid()))
    print(f"[forge_mock] Servidor iniciado na porta {MOCK_PORT}")
    print(f"[forge_mock] Fixtures: {FIXTURES}")
    server = HTTPServer(("127.0.0.1", MOCK_PORT), MockHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("[forge_mock] Encerrando.")
    finally:
        PID_FILE.unlink(missing_ok=True)


def stop():
    if not PID_FILE.exists():
        print("[forge_mock] Servidor não está rodando.")
        return
    pid = int(PID_FILE.read_text().strip())
    try:
        import os as _os
        _os.kill(pid, signal.SIGTERM)
        PID_FILE.unlink(missing_ok=True)
        print(f"[forge_mock] Servidor (PID {pid}) encerrado.")
    except ProcessLookupError:
        print(f"[forge_mock] Processo {pid} não encontrado (já encerrado?).")
        PID_FILE.unlink(missing_ok=True)


def status():
    if not PID_FILE.exists():
        print("[forge_mock] Não está rodando.")
        return
    pid = PID_FILE.read_text().strip()
    try:
        import urllib.request as _ur
        with _ur.urlopen(f"http://localhost:{MOCK_PORT}/health", timeout=2) as r:
            print(f"[forge_mock] Rodando (PID {pid}) — {r.read().decode()}")
    except Exception as e:
        print(f"[forge_mock] PID {pid} registrado mas servidor não responde: {e}")


import os

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="FORGE Mock Server")
    parser.add_argument("--stop",   action="store_true", help="Encerra o servidor")
    parser.add_argument("--status", action="store_true", help="Verifica status")
    args = parser.parse_args()

    if args.stop:
        stop()
    elif args.status:
        status()
    else:
        start()
