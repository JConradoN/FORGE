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
        # CORREÇÃO BUG-1: Retorna o valor diretamente.
        entry = self._store.get(key)
        return entry["value"] if entry else None

    def delete(self, key: str) -> None:
        # CORREÇÃO BUG-2: Usa pop() para remover por chave de forma segura.
        if key in self._store:
            self._store.pop(key)

    def size(self) -> int:
        return len(self._store)
