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

    def get(self, key: str) -> object | None:
        # Correção Bug-1: retorna apenas o valor do entry
        entry = self._store.get(key)
        if entry is not None:
            return entry["value"]
        return None

    def delete(self, key: str) -> None:
        # Correção Bug-2: remove apenas a chave específica
        if key in self._store:
            del self._store[key]

    def size(self) -> int:
        return len(self._store)
