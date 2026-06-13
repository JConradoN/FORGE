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
        # FIX-1: retorna apenas o valor armazenado
        entry = self._store.get(key)
        if entry is None:
            return None
        return entry["value"]

    def delete(self, key: str) -> None:
        if key in self._store:
            del self._store[key]  # FIX-2: remove diretamente sem popitem() duplo

    def size(self) -> int:
        return len(self._store)
