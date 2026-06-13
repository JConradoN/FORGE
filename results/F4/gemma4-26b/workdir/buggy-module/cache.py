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
        entry = self._store.get(key)
        if entry:
            return entry["value"]
        return None

    def delete(self, key: str) -> None:
        if key in self._store:
            del self._store[key]

    def size(self) -> int:
        return len(self._store)
