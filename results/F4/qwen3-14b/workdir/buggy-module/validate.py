"""
Suite de validação para o buggy-module.
Execute após corrigir os bugs: python3 validate.py

Saída esperada: ALL TESTS PASSED (exit 0)
Saída com falha: FAIL: <descrição> (exit 1)
"""
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

errors = []

# ── Teste 1: Cache.set() não deve levantar TypeError ─────────────────────────
try:
    from cache import Cache
    c = Cache()
    c.set("k1", "hello", ttl=30)
    c.set("k2", 42)
    assert c.get("k1") == "hello", f"get retornou {c.get('k1')!r}, esperado 'hello'"
    assert c.get("k2") == 42,      f"get retornou {c.get('k2')!r}, esperado 42"
    assert c.size() == 2,          f"size() retornou {c.size()}, esperado 2"
except Exception as e:
    errors.append(f"cache.set/get: {e}")

# ── Teste 2: Cache.delete() não deve levantar KeyError ───────────────────────
try:
    from cache import Cache
    c = Cache()
    c.set("a", 1)
    c.set("b", 2)
    c.delete("a")
    assert c.get("a") is None, "delete não removeu a chave"
    assert c.size() == 1,     f"size() após delete: {c.size()}, esperado 1"
except Exception as e:
    errors.append(f"cache.delete: {e}")

# ── Teste 3: with_retry retorna na primeira tentativa quando não há exceção ──
try:
    from retry import with_retry
    calls = []
    def success():
        calls.append(1)
        return 99
    result = with_retry(success)
    assert result == 99,    f"with_retry retornou {result!r}, esperado 99"
    assert len(calls) == 1, f"função chamada {len(calls)}x, esperado 1"
except Exception as e:
    errors.append(f"retry (success path): {e}")

# ── Teste 4: with_retry tenta novamente após falha ───────────────────────────
try:
    from retry import with_retry
    attempts = []
    def flaky():
        attempts.append(1)
        if len(attempts) < 3:
            raise ValueError("ainda não")
        return "ok"
    result = with_retry(flaky, max_attempts=3, delay=0.0)
    assert result == "ok",      f"with_retry retornou {result!r}, esperado 'ok'"
    assert len(attempts) == 3,  f"tentativas: {len(attempts)}, esperado 3"
except Exception as e:
    errors.append(f"retry (retry path): {e}")

# ── Teste 5: log_call decora sem NameError e loga o nome correto ─────────────
try:
    import logging, io
    from logger import log_call

    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    logging.getLogger("logger").addHandler(handler)
    logging.getLogger("logger").setLevel(logging.DEBUG)

    @log_call
    def greet(name: str) -> str:
        return f"hello {name}"

    result = greet("world")
    assert result == "hello world", f"greet retornou {result!r}"

    log_output = stream.getvalue()
    assert "greet" in log_output, (
        f"log não contém o nome da função — contém: {log_output!r}"
    )
except Exception as e:
    errors.append(f"logger.log_call: {e}")

# ── Resultado ─────────────────────────────────────────────────────────────────
if errors:
    for err in errors:
        print(f"FAIL: {err}")
    sys.exit(1)
else:
    print(f"ALL TESTS PASSED ({5 - len(errors)}/5)")
    sys.exit(0)
