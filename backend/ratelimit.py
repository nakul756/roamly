"""Tiny in-memory sliding-window limiter (per process; use Redis if you ever run several workers)."""
import threading
import time
from collections import defaultdict, deque


class Limiter:
    def __init__(self):
        self._h, self._l = defaultdict(deque), threading.Lock()

    def _prune(self, key, window):
        q, now = self._h[key], time.time()
        while q and q[0] < now - window:
            q.popleft()
        return q

    def count(self, key, window):
        with self._l:
            return len(self._prune(key, window))

    def add(self, key, window=3600):
        with self._l:
            self._prune(key, window).append(time.time())

    def allow(self, key, limit, window):
        """Records a hit and returns False if the key already made `limit` hits in the last `window` seconds."""
        with self._l:
            q = self._prune(key, window)
            if len(q) >= limit:
                return False
            q.append(time.time())
            return True

    def clear(self, key):
        with self._l:
            self._h.pop(key, None)
