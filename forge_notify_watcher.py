#!/usr/bin/env python3
"""
Monitora /tmp/forge_f5_batch.log e envia notificação Telegram
via bot Claudio após cada modelo concluir.
"""
import re
import sys
import time
import urllib.request
import urllib.parse
import json

TOKEN   = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CHAT_ID = int(os.environ.get("TELEGRAM_CHAT_ID", "0"))
LOG     = "/tmp/forge_f5_batch.log"

MODELS = [
    "granite4.1:8b",
    "ministral-3:14b",
    "phi4:14b",
    "phi4-tools:14b",
    "lfm2:24b-a2b",
    "devstral-small-2:24b",
    "qwen3.5:27b",
    "qwen3.6:27b",
    "granite4.1:30b",
]


def send(text: str):
    url  = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    data = urllib.parse.urlencode({"chat_id": CHAT_ID, "text": text}).encode()
    req  = urllib.request.Request(url, data=data)
    try:
        urllib.request.urlopen(req, timeout=10)
        print(f"[notify] enviado: {text[:60]}")
    except Exception as e:
        print(f"[notify] ERRO: {e}")


def tail(path):
    with open(path, "r") as f:
        f.seek(0, 2)  # vai ao fim
        while True:
            line = f.readline()
            if line:
                yield line
            else:
                time.sleep(1)


def main():
    print(f"[watcher] monitorando {LOG}")
    send("🤖 FORGE F5 batch iniciado — 9 modelos na fila")

    current_model  = None
    current_score  = None
    model_idx      = 0

    for line in tail(LOG):
        line = line.rstrip()

        # Detecta início de novo modelo
        m = re.search(r">>>\s+(.+?)\s+\d{2}:\d{2}:\d{2}", line)
        if m:
            current_model = m.group(1)
            current_score = None
            model_idx    += 1
            print(f"[watcher] iniciando: {current_model} ({model_idx}/{len(MODELS)})")
            continue

        # Captura score
        m = re.search(r"Auto score\s*:\s*(\d+)/(\d+)\s*\((\d+)%\)", line)
        if m:
            current_score = f"{m.group(1)}/{m.group(2)} ({m.group(3)}%)"
            continue

        # Detecta conclusão
        if "[OK]" in line and current_model:
            next_model = MODELS[model_idx] if model_idx < len(MODELS) else None
            msg = (
                f"✅ FORGE F5 — {current_model}\n"
                f"Score: {current_score or '?'}\n"
            )
            if next_model:
                msg += f"Próximo: {next_model}"
            else:
                msg += "Batch concluído!"
            send(msg)
            current_model = None
            current_score = None
            continue

        # Detecta ERRO
        if "[ERRO]" in line and current_model:
            next_model = MODELS[model_idx] if model_idx < len(MODELS) else None
            msg = (
                f"❌ FORGE F5 — {current_model} FALHOU\n"
            )
            if next_model:
                msg += f"Próximo: {next_model}"
            send(msg)
            current_model = None
            current_score = None
            continue

        # Detecta fim do batch
        if "Pipeline concluído" in line:
            send("🏁 FORGE F5 batch completo! Todos os modelos rodaram.")
            print("[watcher] batch completo — encerrando")
            break


if __name__ == "__main__":
    main()
