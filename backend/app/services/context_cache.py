"""
ProjectContextCache — simple in-process TTL cache for per-project context strings.

Caches team_context and reports_context for 5 minutes to avoid redundant DB
queries and TeamContextService calls across rapid successive analysis requests.

Invalidated when a document finishes processing (job_queue.py calls invalidate).
"""
from datetime import datetime, timedelta
from typing import Optional


class ProjectContextCache:
    def __init__(self, ttl_seconds: int = 300):
        self._cache: dict[str, tuple[str, datetime]] = {}
        self._ttl = timedelta(seconds=ttl_seconds)

    def get(self, project_id: int, context_type: str) -> Optional[str]:
        key = f"{project_id}:{context_type}"
        entry = self._cache.get(key)
        if entry is not None:
            value, timestamp = entry
            if datetime.utcnow() - timestamp < self._ttl:
                return value
            del self._cache[key]
        return None

    def set(self, project_id: int, context_type: str, value: str) -> None:
        key = f"{project_id}:{context_type}"
        self._cache[key] = (value, datetime.utcnow())

    def invalidate(self, project_id: int) -> None:
        prefix = f"{project_id}:"
        keys = [k for k in self._cache if k.startswith(prefix)]
        for k in keys:
            del self._cache[k]


# Module-level singleton shared across all requests in a process
context_cache = ProjectContextCache()
