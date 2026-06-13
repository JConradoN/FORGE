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
        # Correção BUG-1: retorna o valor armazenado, não o dict inteiro
        entry = self._store.get(key)
        return entry["value"] if entry is not None else None

    def delete(self, key: str) -> None:
        # Correção BUG-2: remove a chave de forma segura sem double-delete
        self._store.pop(key, None)

    def size(self) -> int:
        return len(self._store)
