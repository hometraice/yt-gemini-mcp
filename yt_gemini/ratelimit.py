"""限制呼叫次數與同時進行的數量，避免 Claude 被誘導或自己陷入迴圈時耗盡 Gemini 額度。

- 只存在 server 的記憶體裡；Chat 與 Code 是不同的 server process，各自計算。
- 超過上限就直接拒絕（fail closed），不排隊等待：排隊可能讓 Chat 超過約 80 秒的等待限制。
- 每次工具呼叫都算一次（不論成功或失敗），比較保守。
"""

from __future__ import annotations

import math
import time
from collections import deque
from collections.abc import Callable, Iterator
from contextlib import contextmanager

from yt_gemini.messages import LocalizedError

MINUTE = 60.0
DAY = 86400.0


class RateLimitError(LocalizedError):
    """超過呼叫上限。用 render(language) 取得要顯示給使用者的訊息。"""


class CallLimiter:
    def __init__(self, clock: Callable[[], float] = time.monotonic):
        self._clock = clock
        self._active = 0
        self._recent: deque[float] = deque()  # 最近 24 小時內每次呼叫的時間；長度不超過每日上限

    @contextmanager
    def slot(self, max_concurrent: int, per_minute: int, per_day: int) -> Iterator[None]:
        now = self._clock()
        while self._recent and now - self._recent[0] >= DAY:
            self._recent.popleft()

        if self._active >= max_concurrent:
            raise RateLimitError("limit_concurrent", limit=max_concurrent)
        last_minute = [t for t in self._recent if now - t < MINUTE]
        if len(last_minute) >= per_minute:
            wait = math.ceil(MINUTE - (now - last_minute[0]))
            raise RateLimitError("limit_per_minute", limit=per_minute, wait=wait)
        if len(self._recent) >= per_day:
            wait_hours = math.ceil((DAY - (now - self._recent[0])) / 3600)
            raise RateLimitError("limit_per_day", limit=per_day, hours=wait_hours)

        self._recent.append(now)
        self._active += 1
        try:
            yield
        finally:
            self._active -= 1


limiter = CallLimiter()
