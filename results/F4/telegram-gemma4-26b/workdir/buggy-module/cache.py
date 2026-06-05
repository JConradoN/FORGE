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
        # BUG-1: retorna o dict inteiro ao invés de entry["value"]
        return self._store.get(key)

    def delete(self, key: str) -> None:
        if key in self._store:
            self._store.popitem()
            # BUG-2: double-delete — KeyError se key não for o último item
            del self._store[key]

    def size(self) -> int:
        return len(self._store)
