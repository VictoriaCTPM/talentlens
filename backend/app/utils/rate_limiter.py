import asyncio
import time


GROQ_FREE_LIMITS = {
    "rpm": 30,
    "rpd": 1000,
    "tpm": 12000,
    "tpd": 100_000,
}


class TokenBucketRateLimiter:
    """
    Enforces per-minute and per-day limits on requests and tokens.
    Uses asyncio.Lock so it is safe to use from concurrent async tasks.
    """

    def __init__(
        self,
        requests_per_minute: int,
        requests_per_day: int,
        tokens_per_minute: int,
        tokens_per_day: int,
    ):
        self.rpm = requests_per_minute
        self.rpd = requests_per_day
        self.tpm = tokens_per_minute
        self.tpd = tokens_per_day

        self._lock = asyncio.Lock()

        # Per-minute window
        self._minute_window_start = time.monotonic()
        self._minute_requests = 0
        self._minute_tokens = 0

        # Per-day window (seconds since epoch, reset at UTC midnight)
        self._day_window_start = time.time()
        self._day_requests = 0
        self._day_tokens = 0

    def _reset_minute_if_needed(self) -> None:
        now = time.monotonic()
        if now - self._minute_window_start >= 60:
            self._minute_window_start = now
            self._minute_requests = 0
            self._minute_tokens = 0

    def _reset_day_if_needed(self) -> None:
        now = time.time()
        if now - self._day_window_start >= 86400:
            self._day_window_start = now
            self._day_requests = 0
            self._day_tokens = 0

    def _seconds_until_minute_reset(self) -> float:
        elapsed = time.monotonic() - self._minute_window_start
        return max(0.0, 60.0 - elapsed)

    async def acquire(self, estimated_tokens: int = 500) -> bool:
        """
        Wait until the request can be made within rate limits, then consume quota.
        Returns True when quota is acquired.
        """
        async with self._lock:
            while True:
                self._reset_minute_if_needed()
                self._reset_day_if_needed()

                minute_req_ok = self._minute_requests < self.rpm
                minute_tok_ok = self._minute_tokens + estimated_tokens <= self.tpm
                day_req_ok = self._day_requests < self.rpd
                day_tok_ok = self._day_tokens + estimated_tokens <= self.tpd

                if minute_req_ok and minute_tok_ok and day_req_ok and day_tok_ok:
                    self._minute_requests += 1
                    self._minute_tokens += estimated_tokens
                    self._day_requests += 1
                    self._day_tokens += estimated_tokens
                    return True

                wait = self._seconds_until_minute_reset()
                # Release lock while waiting so other coroutines aren't blocked
                self._lock.release()
                await asyncio.sleep(wait + 0.1)
                await self._lock.acquire()
