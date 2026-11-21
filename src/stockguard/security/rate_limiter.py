import time
import threading
from collections import defaultdict
from fastapi import HTTPException, Request, status


class InMemoryRateLimiter:
    """
    Thread-safe sliding window rate limiter.
    Limits requests per window for a given key (e.g. IP address or user ID).
    """

    def __init__(self, requests_limit: int = 60, window_seconds: int = 60):
        self.requests_limit = requests_limit
        self.window_seconds = window_seconds
        self._requests: dict[str, list[float]] = defaultdict(list)
        self._lock = threading.Lock()

    def is_rate_limited(self, key: str) -> tuple[bool, int]:
        """
        Returns (is_limited, retry_after_seconds).
        """
        now = time.time()
        window_start = now - self.window_seconds

        with self._lock:
            timestamps = self._requests[key]
            # Prune timestamps older than window
            self._requests[key] = [t for t in timestamps if t > window_start]
            current_count = len(self._requests[key])

            if current_count >= self.requests_limit:
                oldest_in_window = self._requests[key][0]
                retry_after = max(1, int(oldest_in_window + self.window_seconds - now))
                return True, retry_after

            self._requests[key].append(now)
            return False, 0

    def check_or_raise(self, key: str):
        limited, retry_after = self.is_rate_limited(key)
        if limited:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded. Try again in {retry_after} seconds.",
                headers={"Retry-After": str(retry_after)},
            )


# Global rate limiters
auth_rate_limiter = InMemoryRateLimiter(requests_limit=15, window_seconds=60)
api_rate_limiter = InMemoryRateLimiter(requests_limit=120, window_seconds=60)


def limit_auth_request(request: Request):
    client_ip = request.client.host if request.client else "unknown"
    auth_rate_limiter.check_or_raise(f"auth:{client_ip}")


def limit_api_request(request: Request):
    client_ip = request.client.host if request.client else "unknown"
    api_rate_limiter.check_or_raise(f"api:{client_ip}")
