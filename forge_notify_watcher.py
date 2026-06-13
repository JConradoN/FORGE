#!/usr/bin/env python3
"""
Monitora o log do batch FORGE e envia notificação Telegram via bot Claudio.

Uso:
    python3 forge_notify_watcher.py F1
"""
import os, re, sys, time, json
import urllib.request, urllib.parse

TOKEN   = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CHAT_ID = int(os.environ.get("TELEGRAM_CHAT_ID", "0"))

SCENARIO = sys.argv[1] if len(sys.argv) > 1 else "F5"
LOG      = f"/tmp/forge_{SCENARIO.lower()}_batch.log"

# Sentinela única emitida pelo batch script no fim — inclui o cenário
# ex: "  Pipeline F1 concluído — 17:45:23"
DONE_SENTINEL = f"Pipeline {SCENARIO} concluído"


def send(text: str):
    if not TOKEN or not CHAT_ID:
        print(f"[notify] sem credenciais")
        return
    url  = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    data = urllib.parse.urlencode({"chat_id": CHAT_ID, "text": text}).encode()
    try:
        urllib.request.urlopen(
            urllib.request.Request(url, data=data), timeout=10
        )
        print(f"[notify] >> {text[:100]}")
    except Exception as e:
        print(f"[notify] ERRO: {e}")


def read_new_lines(path):
    """Tail -f simples: aguarda arquivo existir, depois entrega novas linhas."""
    while not os.path.exists(path):
        time.sleep(2)
    with open(path, "r", errors="replace") as f:
        f.seek(0, 2)
        while True:
            line = f.readline()
            if line:
                yield line.rstrip()
            else:
                time.sleep(0.5)


def main():
    print(f"[watcher] {SCENARIO} | log: {LOG}")
    print(f"[watcher] sentinela de fim: '{DONE_SENTINEL}'")

    model_atual = None
    score_atual = None
    notificados = set()   # modelos já notificados (evita duplicata por linha dobrada)
    last_line   = ""      # descarta linha imediatamente repetida (tee + nohup)

    for line in read_new_lines(LOG):
        if line == last_line:          # linha dobrada → ignora segunda cópia
            last_line = ""
            continue
        last_line = line

        # ── Início de modelo ──────────────────────────────────────────
        # batch script loga: "  >>> granite4.1:8b  17:45:23"
        m = re.search(r">>>\s+(\S+)\s+\d{2}:\d{2}:\d{2}", line)
        if m:
            model_atual = m.group(1)
            score_atual = None
            print(f"[watcher] iniciando: {model_atual}")
            send(f"FORGE - {SCENARIO} - Iniciando o modelo ({model_atual})")
            continue

        # ── Score capturado ───────────────────────────────────────────
        m = re.search(r"Auto score\s*:\s*(\d+)/(\d+)\s*\((\d+)%\)", line)
        if m:
            score_atual = f"{m.group(1)}/{m.group(2)} ({m.group(3)}%)"
            continue

        # ── Modelo finalizado com sucesso ─────────────────────────────
        # batch script loga: "  [OK] granite4.1:8b concluído"
        # Extrai nome da própria linha — não depende de ter visto o >>>
        if "[OK]" in line:
            m2 = re.search(r"\[OK\]\s+(\S+)\s+conclu", line)
            nome = m2.group(1) if m2 else model_atual
            if nome and nome not in notificados:
                notificados.add(nome)
                score_txt = score_atual or "?"
                send(f"FORGE - {SCENARIO} - Finalizado o modelo ({nome})\nScore: {score_txt}")
            model_atual = None
            score_atual = None
            continue

        # ── Modelo com erro ───────────────────────────────────────────
        if "[ERRO]" in line:
            m2 = re.search(r"\[ERRO\]\s+(\S+)\s+falhou", line)
            nome = m2.group(1) if m2 else model_atual
            if nome and nome not in notificados:
                notificados.add(nome)
                send(f"FORGE - {SCENARIO} - Falhou o modelo ({nome})")
            model_atual = None
            score_atual = None
            continue

        # ── Fim do batch ──────────────────────────────────────────────
        if DONE_SENTINEL in line:
            send(f"FORGE - {SCENARIO} - Batch completo! Todos os modelos rodaram.")
            print("[watcher] batch concluído — encerrando")
            break


if __name__ == "__main__":
    main()
