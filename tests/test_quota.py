"""每日額度記錄的單元測試：時間全部用 mock，不依賴真實時鐘。"""

import unittest
from datetime import datetime, timedelta, timezone

from yt_gemini import quota

UTC = timezone.utc
TW = timezone(timedelta(hours=8))
DAILY = "GenerateRequestsPerDayPerProjectPerModel-FreeTier"


class FakeClock:
    def __init__(self, now):
        self.now = now

    def __call__(self):
        return self.now


def details(*violations, type_="type.googleapis.com/google.rpc.QuotaFailure"):
    return {"error": {"code": 429, "status": "RESOURCE_EXHAUSTED",
                      "details": [{"@type": type_, "violations": list(violations)}]}}


class TestNextReset(unittest.TestCase):
    def test_before_reset_same_day(self):
        self.assertEqual(quota.next_reset(datetime(2026, 11, 20, 7, 59, 59, tzinfo=UTC)),
                         datetime(2026, 11, 20, 8, 0, tzinfo=UTC))

    def test_exactly_at_reset_moves_to_next_day(self):
        self.assertEqual(quota.next_reset(datetime(2026, 11, 20, 8, 0, tzinfo=UTC)),
                         datetime(2026, 11, 21, 8, 0, tzinfo=UTC))

    def test_after_reset(self):
        self.assertEqual(quota.next_reset(datetime(2026, 11, 20, 23, 30, tzinfo=UTC)),
                         datetime(2026, 11, 21, 8, 0, tzinfo=UTC))

    def test_month_and_year_boundary(self):
        self.assertEqual(quota.next_reset(datetime(2026, 12, 31, 9, 0, tzinfo=UTC)),
                         datetime(2027, 1, 1, 8, 0, tzinfo=UTC))

    def test_taiwan_time_input(self):
        # 台灣時間 15:00 = UTC 07:00 → 同一天台灣時間 16:00 重置
        self.assertEqual(quota.next_reset(datetime(2026, 11, 20, 15, 0, tzinfo=TW)),
                         datetime(2026, 11, 20, 8, 0, tzinfo=UTC))

    def test_format_reset_in_taiwan_time(self):
        self.assertEqual(quota.format_reset(datetime(2026, 11, 20, 8, 0, tzinfo=UTC)), "11/20 16:00（台灣時間）")


class TestTracker(unittest.TestCase):
    def test_blocked_until_reset_then_cleared(self):
        clock = FakeClock(datetime(2026, 11, 20, 10, 0, tzinfo=UTC))
        tracker = quota.DailyQuotaTracker(clock)
        self.assertIsNone(tracker.blocked_until("m1"))
        until = tracker.mark_exhausted("m1")
        self.assertEqual(until, datetime(2026, 11, 21, 8, 0, tzinfo=UTC))
        self.assertIsNone(tracker.blocked_until("m2"))  # 只影響被標記的模型

        clock.now = datetime(2026, 11, 21, 7, 59, tzinfo=UTC)
        self.assertEqual(tracker.blocked_until("m1"), until)
        clock.now = datetime(2026, 11, 21, 8, 0, tzinfo=UTC)
        self.assertIsNone(tracker.blocked_until("m1"))
        clock.now = datetime(2026, 11, 20, 10, 0, tzinfo=UTC)  # 就算時鐘倒退，記錄也已清掉
        self.assertIsNone(tracker.blocked_until("m1"))

    def test_default_clock_is_utc_now(self):
        tracker = quota.DailyQuotaTracker()
        until = tracker.mark_exhausted("m1")
        now = datetime.now(UTC)
        self.assertGreater(until, now)
        self.assertLessEqual(until - now, timedelta(days=1))


class TestQuotaIds(unittest.TestCase):
    def test_daily_quota_detected(self):
        ids = quota.quota_ids(details({"quotaMetric": "x", "quotaId": DAILY}))
        self.assertEqual(ids, [DAILY])
        self.assertTrue(quota.is_daily_quota(ids))

    def test_per_minute_is_not_daily(self):
        ids = quota.quota_ids(details({"quotaId": "GenerateRequestsPerMinutePerProjectPerModel-FreeTier"}))
        self.assertEqual(len(ids), 1)
        self.assertFalse(quota.is_daily_quota(ids))

    def test_mixed_violations(self):
        ids = quota.quota_ids(details({"quotaId": "GenerateContentInputTokensPerModelPerMinute-FreeTier"},
                                      {"quotaId": DAILY}))
        self.assertTrue(quota.is_daily_quota(ids))

    def test_malformed_details_never_raise(self):
        cases = [None, "text", 42, [], {}, {"error": None}, {"error": {"details": "x"}},
                 {"error": {"details": [None, 1, "x"]}},
                 details("not a dict"), details({"quotaId": 123}),
                 {"error": {"details": [{"@type": "type.googleapis.com/google.rpc.QuotaFailure",
                                         "violations": "x"}]}}]
        for case in cases:
            with self.subTest(case=case):
                self.assertEqual(quota.quota_ids(case), [])

    def test_number_of_ids_is_capped(self):
        ids = quota.quota_ids(details(*[{"quotaId": f"Q{i}PerDay"} for i in range(50)]))
        self.assertEqual(len(ids), 10)

    def test_other_detail_types_ignored(self):
        self.assertEqual(quota.quota_ids(details({"quotaId": DAILY},
                                                 type_="type.googleapis.com/google.rpc.RetryInfo")), [])

    def test_suspicious_quota_id_rejected(self):
        # 不符合白名單字元的內容不採用，也就不會寫進 log
        for bad in ("PerDay <script>", "PerDay\nINJECT", "x" * 101, ""):
            with self.subTest(bad=bad):
                self.assertEqual(quota.quota_ids(details({"quotaId": bad})), [])


if __name__ == "__main__":
    unittest.main()
