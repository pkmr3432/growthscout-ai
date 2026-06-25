# agents/orchestrator_agent/cache_layer.py
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

class CacheEntry:
    def __init__(self, value: Any, ttl_seconds: float) -> None:
        self.value = value
        self.created_at = datetime.now(timezone.utc)
        self.expires_at = self.created_at + timedelta(seconds=ttl_seconds)

    def is_expired(self) -> bool:
        return datetime.now(timezone.utc) > self.expires_at

class DiscoveryCache:
    def __init__(self, ttl_seconds: float = 3600.0) -> None:
        self.ttl_seconds = ttl_seconds
        self._cache: Dict[str, CacheEntry] = {}
        self._hits = 0
        self._misses = 0
        self._evictions = 0
        self._expired_entries = 0

    def get(self, query: str) -> Optional[Any]:
        entry = self._cache.get(query)
        if not entry:
            self._misses += 1
            return None
        if entry.is_expired():
            self._expired_entries += 1
            self._misses += 1
            del self._cache[query]
            return None
        self._hits += 1
        return entry.value

    def set(self, query: str, value: Any) -> None:
        if query in self._cache:
            self._evictions += 1
        self._cache[query] = CacheEntry(value, self.ttl_seconds)

    def invalidate(self, query: str) -> None:
        if query in self._cache:
            self._evictions += 1
            del self._cache[query]

    def clear(self) -> None:
        self._evictions += len(self._cache)
        self._cache.clear()

    @property
    def hits(self) -> int:
        return self._hits

    @property
    def misses(self) -> int:
        return self._misses

    @property
    def evictions(self) -> int:
        return self._evictions

    @property
    def expired_entries(self) -> int:
        return self._expired_entries

class AuditCache:
    def __init__(self, ttl_seconds: float = 86400.0) -> None:
        self.ttl_seconds = ttl_seconds
        self._cache: Dict[str, CacheEntry] = {}
        self._hits = 0
        self._misses = 0
        self._evictions = 0
        self._expired_entries = 0

    def get(self, url: str) -> Optional[Any]:
        entry = self._cache.get(url)
        if not entry:
            self._misses += 1
            return None
        if entry.is_expired():
            self._expired_entries += 1
            self._misses += 1
            del self._cache[url]
            return None
        self._hits += 1
        return entry.value

    def set(self, url: str, value: Any) -> None:
        if url in self._cache:
            self._evictions += 1
        self._cache[url] = CacheEntry(value, self.ttl_seconds)

    def invalidate(self, url: str) -> None:
        if url in self._cache:
            self._evictions += 1
            del self._cache[url]

    def clear(self) -> None:
        self._evictions += len(self._cache)
        self._cache.clear()

    @property
    def hits(self) -> int:
        return self._hits

    @property
    def misses(self) -> int:
        return self._misses

    @property
    def evictions(self) -> int:
        return self._evictions

    @property
    def expired_entries(self) -> int:
        return self._expired_entries

class RuntimeCacheManager:
    def __init__(self, ttl_discovery: float = 3600.0, ttl_audit: float = 86400.0) -> None:
        self.discovery = DiscoveryCache(ttl_discovery)
        self.audit = AuditCache(ttl_audit)

    def invalidate_discovery_cache(self, query: str) -> None:
        self.discovery.invalidate(query)

    def invalidate_audit_cache(self, url: str) -> None:
        self.audit.invalidate(url)

    def clear_discovery_cache(self) -> None:
        self.discovery.clear()

    def clear_audit_cache(self) -> None:
        self.audit.clear()

    def clear_all(self) -> None:
        self.discovery.clear()
        self.audit.clear()

    # CacheProtocol compliance methods
    def get(self, key: str) -> Optional[Any]:
        val = self.discovery.get(key)
        if val is not None:
            return val
        return self.audit.get(key)

    def set(self, key: str, value: Any) -> None:
        if key.startswith("http://") or key.startswith("https://"):
            self.audit.set(key, value)
        else:
            self.discovery.set(key, value)

    def invalidate(self, key: str) -> None:
        self.discovery.invalidate(key)
        self.audit.invalidate(key)

    def clear(self) -> None:
        self.clear_all()

    @property
    def hits(self) -> int:
        return self.discovery.hits + self.audit.hits

    @property
    def misses(self) -> int:
        return self.discovery.misses + self.audit.misses

    @property
    def evictions(self) -> int:
        return self.discovery.evictions + self.audit.evictions

    @property
    def expired_entries(self) -> int:
        return self.discovery.expired_entries + self.audit.expired_entries
