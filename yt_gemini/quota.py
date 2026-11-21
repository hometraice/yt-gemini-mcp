"""記錄「每日額度已用完」的模型：在每日重置前，後續呼叫直接跳過它。

- 只存在 server 的記憶體裡，不寫檔；server 重新啟動就清空。
- 只有 429 的錯誤細節明確指出是每日額度（QuotaFailure 的 quotaId 含 PerDay）才記錄；
  判斷不出來就當一般 429 處理（只換備援模型），避免把每分鐘限制誤判成一整天不能用。
"""

from __future__ import annotations

import re
from collections.abc import Callable
from datetime import datetime, timedelta, timezone

# 官方文件：每日額度（RPD）在太平洋時間午夜重置。
# Windows 的 Python 沒有內建時區資料（要另外裝 tzdata 套件），所以一律算到 UTC 08:00，
# 也就是太平洋標準時間午夜。夏令時間期間 Google 實際在 UTC 07:00 重置，最多多跳過 1 小時。
RESET_HOUR_UTC = 8
TAIWAN = timezone(timedelta(hours=8), "台灣時間")

# quotaId 只接受這些字元；其他內容一律不採用、不寫進 log。
_QUOTA_ID_RE = re.compile(r"[A-Za-z0-9_.\-]{1,100}")
_QUOTA_FAILURE_TYPE = "type.googleapis.com/google.rpc.QuotaFailure"
_MAX_IDS = 10  # 只取前幾個，避免異常的回應讓 log 變很長


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def next_reset(now: datetime) -> datetime:
    """now 之後的下一個 UTC 08:00。"""
    now = now.astimezone(timezone.utc)
    reset = now.replace(hour=RESET_HOUR_UTC, minute=0, second=0, microsecond=0)
    if reset <= now:
        reset += timedelta(days=1)
    return reset


def format_reset(moment: datetime) -> str:
    return moment.astimezone(TAIWAN).strftime("%m/%d %H:%M") + "（台灣時間）"


def quota_ids(details: object) -> list[str]:
    """從 APIError.details 取出 QuotaFailure 的 quotaId。格式不符就略過，不會丟例外。"""
    error = details.get("error", details) if isinstance(details, dict) else None
    items = error.get("details") if isinstance(error, dict) else None
    if not isinstance(items, list):
        return []
    ids: list[str] = []
    for item in items:
        if not isinstance(item, dict) or item.get("@type") != _QUOTA_FAILURE_TYPE:
            continue
        violations = item.get("violations")
        if not isinstance(violations, list):
            continue
        for violation in violations:
            value = violation.get("quotaId") if isinstance(violation, dict) else None
            if isinstance(value, str) and _QUOTA_ID_RE.fullmatch(value):
                ids.append(value)
                if len(ids) >= _MAX_IDS:
                    return ids
    return ids


def is_daily_quota(ids: list[str]) -> bool:
    return any("perday" in quota_id.lower() for quota_id in ids)


class DailyQuotaTracker:
    def __init__(self, clock: Callable[[], datetime] = _utc_now):
        self._clock = clock
        self._blocked: dict[str, datetime] = {}

    def mark_exhausted(self, model: str) -> datetime:
        until = next_reset(self._clock())
        self._blocked[model] = until
        return until

    def blocked_until(self, model: str) -> datetime | None:
        """還在跳過期間就回傳恢復時間；已過重置時間就清掉記錄並回傳 None。"""
        until = self._blocked.get(model)
        if until is None:
            return None
        if self._clock() >= until:
            del self._blocked[model]
            return None
        return until


tracker = DailyQuotaTracker()
