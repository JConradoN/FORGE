"""
Validation suite — expected output: ALL TESTS PASSED (5/5)
"""
import sys
import time

sys.path.insert(0, __file__.rsplit("/", 1)[0])

from cache import Cache
from retry import retry, retry_call
from logger import Logger

passed = 0
total = 5

def ok(name):
    global passed
    passed += 1
    print(f"  [PASS] {name}")

def fail(name, reason):
    print(f"  [FAIL] {name}: {reason}")


# ── Test 1 ── cache: get missing key returns None (no KeyError) ──────────────
print("Test 1: cache.get on missing key")
try:
    c = Cache(ttl=10)
    result = c.get("nonexistent")
    assert result is None, f"expected None, got {result!r}"
    ok("get missing key returns None")
except Exception as e:
    fail("get missing key returns None", e)


# ── Test 2 ── cache: delete cleans up timestamps; size is accurate ────────────
print("Test 2: cache.delete and cache.size accuracy")
try:
    c = Cache(ttl=60)
    c.set("a", 1)
    c.set("b", 2)
    c.delete("a")
    assert c.size() == 1, f"expected size 1, got {c.size()}"
    assert "a" not in c.timestamps, "timestamps still contains deleted key"
    ok("delete cleans timestamps; size accurate")
except Exception as e:
    fail("delete cleans timestamps; size accurate", e)


# ── Test 3 ── cache: get_all_valid respects TTL boundary (>= not >) ──────────
print("Test 3: cache.get_all_valid TTL boundary")
try:
    c = Cache(ttl=5)
    c.set("x", 42)
    # Backdate the timestamp so age == ttl exactly → should still be valid
    c.timestamps["x"] = time.time() - 5
    valid = c.get_all_valid()
    assert "x" in valid, "entry at exact TTL boundary should be valid"
    ok("get_all_valid includes entry at exact TTL boundary")
except Exception as e:
    fail("get_all_valid includes entry at exact TTL boundary", e)


# ── Test 4 ── retry: retry_call re-raises the original exception ──────────────
print("Test 4: retry_call raises original exception")
try:
    class CustomError(Exception): pass

    def always_fail():
        raise CustomError("original message")

    try:
        retry_call(always_fail, max_attempts=2, delay=0.0)
        fail("retry_call raises original exception", "no exception raised")
    except CustomError as e:
        assert "original message" in str(e), f"wrong message: {e}"
        ok("retry_call raises original exception")
    except Exception as e:
        fail("retry_call raises original exception", f"wrong type {type(e).__name__}: {e}")
except Exception as e:
    fail("retry_call raises original exception", e)


# ── Test 5 ── logger: level filtering works correctly ────────────────────────
print("Test 5: logger level filtering")
try:
    log = Logger("test", level="WARNING")
    log.debug("d")
    log.info("i")
    log.warning("w")
    log.error("e")
    log.critical("c")

    assert len(log.records) == 3, (
        f"expected 3 records (WARNING+), got {len(log.records)}: "
        + str([r['level'] for r in log.records])
    )

    errors_and_above = log.get_records(min_level="ERROR")
    assert len(errors_and_above) == 2, (
        f"expected 2 records (ERROR+), got {len(errors_and_above)}: "
        + str([r['level'] for r in errors_and_above])
    )
    ok("logger filters by level correctly")
except Exception as e:
    fail("logger filters by level correctly", e)


# ── Summary ──────────────────────────────────────────────────────────────────
print()
if passed == total:
    print(f"ALL TESTS PASSED ({passed}/{total})")
else:
    print(f"FAILED: {passed}/{total} passed")
    sys.exit(1)
