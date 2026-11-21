"""呼叫上限的單元測試：時間全部用 mock。"""

import unittest

from yt_gemini.ratelimit import CallLimiter, RateLimitError


class FakeClock:
    def __init__(self, now=1000.0):
        self.now = now

    def __call__(self):
        return self.now


def call(limiter, concurrent=2, per_minute=5, per_day=100):
    with limiter.slot(concurrent, per_minute, per_day):
        pass


class TestCallLimiter(unittest.TestCase):
    def setUp(self):
        self.clock = FakeClock()
        self.limiter = CallLimiter(self.clock)

    def test_concurrency_limit_and_release(self):
        with self.limiter.slot(2, 50, 500):
            with self.limiter.slot(2, 50, 500):
                with self.assertRaises(RateLimitError) as ctx:
                    call(self.limiter, concurrent=2, per_minute=50, per_day=500)
                self.assertIn("同時進行", str(ctx.exception))
        call(self.limiter, concurrent=2, per_minute=50, per_day=500)  # 前面的結束後就能再用

    def test_slot_released_even_when_call_fails(self):
        with self.assertRaises(ValueError):
            with self.limiter.slot(1, 50, 500):
                raise ValueError("boom")
        call(self.limiter, concurrent=1, per_minute=50, per_day=500)

    def test_per_minute_limit_rolls(self):
        for _ in range(5):
            call(self.limiter)
            self.clock.now += 1
        with self.assertRaises(RateLimitError) as ctx:
            call(self.limiter)
        self.assertIn("每分鐘最多分析 5 次", str(ctx.exception))
        self.assertIn("55 秒後", str(ctx.exception))  # 第一次在 1000，現在 1005
        self.clock.now = 1000 + 60  # 第一次呼叫滿 60 秒後，空出一個名額
        call(self.limiter)

    def test_per_day_limit_rolls(self):
        for _ in range(3):
            call(self.limiter, per_minute=60, per_day=3)
            self.clock.now += 120
        with self.assertRaises(RateLimitError) as ctx:
            call(self.limiter, per_minute=60, per_day=3)
        self.assertIn("24 小時內最多分析 3 次", str(ctx.exception))
        self.assertIn("[limits]", str(ctx.exception))
        self.clock.now = 1000 + 86400  # 第一次呼叫滿 24 小時
        call(self.limiter, per_minute=60, per_day=3)

    def test_rejected_calls_are_not_counted(self):
        for _ in range(5):
            call(self.limiter)
        for _ in range(10):
            with self.assertRaises(RateLimitError):
                call(self.limiter)
        self.clock.now += 60
        for _ in range(5):  # 被拒絕的呼叫不佔名額
            call(self.limiter)

    def test_history_is_bounded(self):
        for i in range(300):
            call(self.limiter, per_minute=60, per_day=100)
            self.clock.now += 1000
        self.assertLessEqual(len(self.limiter._recent), 100)


if __name__ == "__main__":
    unittest.main()
