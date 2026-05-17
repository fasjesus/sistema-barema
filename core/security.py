from collections import defaultdict, deque
from dataclasses import dataclass
from math import ceil
from threading import Lock
from time import monotonic


@dataclass(frozen=True)
class RateLimitResult:
    allowed: bool
    retry_after: int = 0


@dataclass(frozen=True)
class LoginBlockResult:
    blocked: bool
    retry_after: int = 0


class SlidingWindowRateLimiter:
    def __init__(self, clock=None):
        self._clock = clock or monotonic
        self._events = defaultdict(deque)
        self._lock = Lock()

    def hit(self, key, limit, window_seconds):
        if limit <= 0 or window_seconds <= 0:
            return RateLimitResult(allowed=True)

        now = self._clock()
        cutoff = now - window_seconds

        with self._lock:
            events = self._events[key]
            while events and events[0] <= cutoff:
                events.popleft()

            if len(events) >= limit:
                retry_after = max(1, ceil(events[0] + window_seconds - now))
                return RateLimitResult(allowed=False, retry_after=retry_after)

            events.append(now)
            return RateLimitResult(allowed=True)

    def clear(self):
        with self._lock:
            self._events.clear()


class LoginAttemptLimiter:
    def __init__(self, clock=None):
        self._clock = clock or monotonic
        self._attempts = {}
        self._lock = Lock()

    def is_blocked(self, key):
        now = self._clock()

        with self._lock:
            record = self._attempts.get(key)
            if not record:
                return LoginBlockResult(blocked=False)

            blocked_until = record.get("blocked_until", 0)
            if blocked_until > now:
                retry_after = max(1, ceil(blocked_until - now))
                return LoginBlockResult(blocked=True, retry_after=retry_after)

            if blocked_until:
                self._attempts.pop(key, None)

            return LoginBlockResult(blocked=False)

    def register_failure(self, key, max_attempts, block_seconds):
        if max_attempts <= 0 or block_seconds <= 0:
            return LoginBlockResult(blocked=False)

        now = self._clock()

        with self._lock:
            record = self._attempts.setdefault(
                key,
                {"failures": 0, "blocked_until": 0},
            )

            blocked_until = record.get("blocked_until", 0)
            if blocked_until > now:
                retry_after = max(1, ceil(blocked_until - now))
                return LoginBlockResult(blocked=True, retry_after=retry_after)

            if blocked_until:
                record["failures"] = 0
                record["blocked_until"] = 0

            record["failures"] += 1

            if record["failures"] >= max_attempts:
                record["failures"] = 0
                record["blocked_until"] = now + block_seconds
                return LoginBlockResult(blocked=True, retry_after=ceil(block_seconds))

            return LoginBlockResult(blocked=False)

    def reset(self, key):
        with self._lock:
            self._attempts.pop(key, None)

    def clear(self):
        with self._lock:
            self._attempts.clear()


def get_client_ip(request, trust_proxy_headers=False):
    forwarded_for = request.headers.get("X-Forwarded-For", "")
    if trust_proxy_headers and forwarded_for:
        return forwarded_for.split(",", 1)[0].strip()
    return request.remote_addr or "unknown"


request_rate_limiter = SlidingWindowRateLimiter()
login_attempt_limiter = LoginAttemptLimiter()
