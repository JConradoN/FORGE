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

# Blocklist de comandos destrutivos para run_bash (correção ID-2: case-insensitive)
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
    r"chmod\s+777\s+/",     # chmod 770 na raiz
    r"sudo\s+rm",           # sudo rm
    r"shutdown",            # desligar máquina
    r"reboot",              # reiniciar
]

def _check_bash_safety(command: str) -> str | None:
    """Retorna mensagem de erro se o comando for bloqueado, None se seguro."""
    cmd_lower = command.lower()
    for pattern in _BASH_BLOCKLIST:
        if re.search(pattern, cmd_lower, re.IGNORECASE):  # Correção ID-2: case-insensitive
            return f"[BLOQUEADO] Comando não permitido (padrão: {pattern}). Use comandos seguros."
    return None