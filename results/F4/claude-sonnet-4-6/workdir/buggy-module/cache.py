"""Simple in-memory cache with TTL support."""

import time


class Cache:
    def __init__(self, ttl=60):
        self._store = {}
        self._default_ttl = ttl

    def set(self, key, value, ttl=None):
        # FIX bug 2: aceita TTL por item; usa o TTL global como fallback
        effective_ttl = ttl if ttl is not None else self._default_ttl
        self._store[key] = (value, time.time(), effective_ttl)

    def get(self, key):
        if key not in self._store:
            return None
        value, ts, ttl = self._store[key]
        # FIX bug 1: operador correto — subtração para calcular tempo decorrido
        if time.time() - ts > ttl:
            del self._store[key]
            return None
        return value

    def delete(self, key):
        # FIX bug 3: pop() é idempotente — sem KeyError se chave não existir
        self._store.pop(key, None)

    def clear(self):
        self._store = {}

    def size(self):
        # FIX bug 4: retorna o número de entradas, não o dict
        return len(self._store)
