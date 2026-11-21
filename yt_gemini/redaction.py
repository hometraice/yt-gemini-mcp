"""遮罩機密：任何要寫進 log、錯誤訊息或回傳給 Claude 的文字，都先經過這裡。"""

from __future__ import annotations

import logging
import re
import threading

REDACTED = "[REDACTED]"

# Google API key 的固定格式：AIza + 35 個字元。
_GOOGLE_KEY_RE = re.compile(r"AIza[0-9A-Za-z_\-]{35}")
# URL 參數 ?key=... / &key=...
_QUERY_KEY_RE = re.compile(r"(?i)([?&](?:api_?)?key=)[^&\s\"'<>]+")
# HTTP header x-goog-api-key: ...
_HEADER_KEY_RE = re.compile(r"(?i)(x-goog-api-key[\"']?\s*[:=]\s*[\"']?)[^\s\"',}]+")

_known_secrets: set[str] = set()
_lock = threading.Lock()


def register_secret(value: str) -> None:
    """登記一個實際使用中的機密，之後所有 redact() 都會把它換掉。"""
    if value and len(value) >= 8:
        with _lock:
            _known_secrets.add(value)


def redact(text: object) -> str:
    """把文字裡所有已知機密與「長得像 key」的字串換成 [REDACTED]。"""
    s = str(text)
    with _lock:
        secrets = sorted(_known_secrets, key=len, reverse=True)
    for secret in secrets:
        s = s.replace(secret, REDACTED)
    s = _GOOGLE_KEY_RE.sub(REDACTED, s)
    s = _QUERY_KEY_RE.sub(lambda m: m.group(1) + REDACTED, s)
    s = _HEADER_KEY_RE.sub(lambda m: m.group(1) + REDACTED, s)
    return s


class RedactingFormatter(logging.Formatter):
    """在 log 最終輸出前（包含 traceback）做遮罩。"""

    def format(self, record: logging.LogRecord) -> str:
        return redact(super().format(record))
