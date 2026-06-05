"""
Cache em memória com TTL simples.
"""
from typing import TypedDict


class CacheEntry(TypedDict):
    key: str
    value: object
    ttl: int


class Cache:
    def __init__(self):
        self._store = {}

    def set(self, key: str, value: object, ttl: int = 60) -> None:
        entry = CacheEntry(key=key, value=value, ttl=ttl)
        self._store[key] = entry

    def get(self, key: str) -> object:
        # FIX-1: retorna apenas o valor do dict de entrada
        return self._store.get(key)["value"] if key in self._store else None

    def delete(self, key: str) -> None:
        if key in self._store:
            del self._store[key]
            # FIX-2: removeu a chamada popitem() desnecessária que causava double-delete

    def size(self) -> int:
        return len(self._store)
