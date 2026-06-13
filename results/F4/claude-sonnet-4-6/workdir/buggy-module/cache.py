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
        # FIX BUG-1: retorna entry["value"] em vez do dict inteiro
        entry = self._store.get(key)
        return entry["value"] if entry is not None else None

    def delete(self, key: str) -> None:
        # FIX BUG-2: remove popitem() (que apagava item arbitrário) e o
        # segundo del (que causava KeyError); usa apenas del self._store[key]
        if key in self._store:
            del self._store[key]

    def size(self) -> int:
        return len(self._store)
