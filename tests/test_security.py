import unittest
from types import SimpleNamespace

from core.security import LoginAttemptLimiter, get_client_ip


class FakeClock:
    def __init__(self):
        self.now = 0

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


class LoginAttemptLimiterTest(unittest.TestCase):
    def test_blocks_after_three_failures_and_releases_after_one_minute(self):
        clock = FakeClock()
        limiter = LoginAttemptLimiter(clock=clock)

        self.assertFalse(limiter.register_failure("ip:user", 3, 60).blocked)
        self.assertFalse(limiter.register_failure("ip:user", 3, 60).blocked)

        blocked = limiter.register_failure("ip:user", 3, 60)
        self.assertTrue(blocked.blocked)
        self.assertEqual(blocked.retry_after, 60)
        self.assertTrue(limiter.is_blocked("ip:user").blocked)

        clock.advance(61)
        self.assertFalse(limiter.is_blocked("ip:user").blocked)

    def test_success_resets_consecutive_failures(self):
        clock = FakeClock()
        limiter = LoginAttemptLimiter(clock=clock)

        limiter.register_failure("ip:user", 3, 60)
        limiter.register_failure("ip:user", 3, 60)
        limiter.reset("ip:user")

        self.assertFalse(limiter.register_failure("ip:user", 3, 60).blocked)
        self.assertFalse(limiter.register_failure("ip:user", 3, 60).blocked)


class ClientIpTest(unittest.TestCase):
    def test_uses_remote_addr_by_default(self):
        request = SimpleNamespace(
            headers={"X-Forwarded-For": "203.0.113.10, 10.0.0.1"},
            remote_addr="127.0.0.1",
        )

        self.assertEqual(get_client_ip(request), "127.0.0.1")

    def test_uses_forwarded_for_when_proxy_headers_are_trusted(self):
        request = SimpleNamespace(
            headers={"X-Forwarded-For": "203.0.113.10, 10.0.0.1"},
            remote_addr="127.0.0.1",
        )

        self.assertEqual(
            get_client_ip(request, trust_proxy_headers=True),
            "203.0.113.10",
        )


if __name__ == "__main__":
    unittest.main()
