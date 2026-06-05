"""
Simple in-memory cache with TTL (Time To Live) support.
"""
import time


class Cache:
    def __init__(self, ttl=60):
        self.ttl = ttl
        self.store = {}
        self.timestamps = {}

    def set(self, key, value):
        self.store[key] = value
        self.timestamps[key] = time.time()

    def get(self, key):
        # FIX Bug 1: guard against missing key — return None instead of raising KeyError
        if key not in self.store:
            return None
        ts = self.timestamps[key]
        if time.time() - ts > self.ttl:
            self.delete(key)
            return None
        return self.store[key]

    def delete(self, key):
        del self.store[key]
        # FIX Bug 2: also remove the timestamp to prevent memory leak
        del self.timestamps[key]

    def clear(self):
        self.store = {}
        self.timestamps = {}

    def size(self):
        # FIX Bug 3: count only entries that are still within TTL
        now = time.time()
        return sum(1 for key in self.store if now - self.timestamps[key] <= self.ttl)

    def get_all_valid(self):
        now = time.time()
        result = {}
        for key in self.store:
            # FIX Bug 4: use <= (not <) — entry is valid when age <= ttl, consistent with get()
            # which only expires when age > ttl
            if now - self.timestamps[key] <= self.ttl:
                result[key] = self.store[key]
        return result
