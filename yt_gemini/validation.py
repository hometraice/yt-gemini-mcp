"""輸入驗證：防 SSRF、防濫用。

原則：只認得白名單裡的 YouTube 網址格式，從中取出 11 碼影片 ID，
之後一律用 ID 重組成標準網址；使用者給的原始字串絕不轉送出去。
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from urllib.parse import parse_qs, urlsplit

MAX_URL_LENGTH = 2048
MAX_QUESTION_LENGTH = 2000
MAX_SECONDS = 12 * 3600  # 合理上限：12 小時

WATCH_HOSTS = frozenset({"youtube.com", "www.youtube.com", "m.youtube.com"})
SHORT_HOST = "youtu.be"
DETAIL_LEVELS = ("low", "default")
MODES = ("summary", "notes", "tutorial", "quotes", "claims")

_VIDEO_ID_RE = re.compile(r"[A-Za-z0-9_-]{11}")
_SCHEME_RE = re.compile(r"[A-Za-z][A-Za-z0-9+.\-]*:")


class ValidationError(ValueError):
    """輸入不合法。訊息可以直接回給使用者。"""


@dataclass(frozen=True)
class VideoRef:
    video_id: str

    @property
    def canonical_url(self) -> str:
        return f"https://www.youtube.com/watch?v={self.video_id}"


def _strip_trailing_slash(segment: str) -> str:
    return segment[:-1] if segment.endswith("/") else segment


def parse_youtube_url(raw: object) -> VideoRef:
    if not isinstance(raw, str):
        raise ValidationError("url 必須是字串。")
    if len(raw) > MAX_URL_LENGTH:
        raise ValidationError(f"網址太長（上限 {MAX_URL_LENGTH} 字元）。")

    url = raw.strip()
    if not url:
        raise ValidationError("url 不可為空。")
    if not url.isascii():
        raise ValidationError("網址只能包含 ASCII 字元。")
    if any(c.isspace() or not c.isprintable() for c in url):
        raise ValidationError("網址不可包含空白或控制字元。")
    if "\\" in url:
        raise ValidationError("網址不可包含反斜線。")

    scheme_match = _SCHEME_RE.match(url)
    if scheme_match:
        scheme = scheme_match.group(0)[:-1].lower()
        if scheme not in ("http", "https"):
            raise ValidationError("只接受 http 或 https 網址。")
        if not url[scheme_match.end():].startswith("//"):
            raise ValidationError("網址格式不正確。")
    elif url.startswith("//"):
        raise ValidationError("網址格式不正確。")
    else:
        url = "https://" + url  # 允許省略 https://，例如 youtu.be/xxxxxxxxxxx

    parts = urlsplit(url)
    if "@" in parts.netloc:
        raise ValidationError("網址不可包含帳號或密碼。")
    try:
        port = parts.port
    except ValueError:
        raise ValidationError("網址格式不正確。") from None
    if port is not None:
        raise ValidationError("網址不可指定 port。")

    host = (parts.hostname or "").lower()
    path = parts.path

    if host in WATCH_HOSTS:
        if path in ("/watch", "/watch/"):
            values = parse_qs(parts.query, keep_blank_values=True).get("v", [])
            if len(values) != 1:
                raise ValidationError("watch 網址必須剛好有一個 v= 參數。")
            video_id = values[0]
        elif path.startswith("/shorts/"):
            video_id = _strip_trailing_slash(path[len("/shorts/"):])
        else:
            raise ValidationError(
                "不支援的 YouTube 網址格式。請用 youtube.com/watch?v=、youtu.be/ 或 youtube.com/shorts/。"
            )
    elif host == SHORT_HOST:
        video_id = _strip_trailing_slash(path[1:])
    else:
        raise ValidationError("只接受 YouTube 網址（youtube.com、m.youtube.com、youtu.be）。")

    if not _VIDEO_ID_RE.fullmatch(video_id):
        raise ValidationError("影片 ID 格式不正確（應為 11 個英數字、- 或 _）。")
    return VideoRef(video_id)


def validate_question(question: object) -> str | None:
    if question is None:
        return None
    if not isinstance(question, str):
        raise ValidationError("question 必須是字串。")
    question = question.strip()
    if not question:
        return None
    if len(question) > MAX_QUESTION_LENGTH:
        raise ValidationError(f"question 太長（上限 {MAX_QUESTION_LENGTH} 字元）。")
    for c in question:
        if c not in "\n\t" and unicodedata.category(c) == "Cc":
            raise ValidationError("question 不可包含控制字元。")
    return question


def _validate_seconds(name: str, value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValidationError(f"{name} 必須是整數秒數。")
    if value < 0:
        raise ValidationError(f"{name} 不可為負數。")
    if value > MAX_SECONDS:
        raise ValidationError(f"{name} 不可超過 {MAX_SECONDS} 秒（12 小時）。")
    return value


def validate_time_range(start: object, end: object) -> tuple[int | None, int | None]:
    s = _validate_seconds("start", start)
    e = _validate_seconds("end", end)
    if e is not None and e <= (s or 0):
        raise ValidationError("end 必須大於 start。")
    return s, e


def validate_detail(detail: object) -> str:
    if detail is None:
        return "low"
    if detail not in DETAIL_LEVELS:
        raise ValidationError('detail 只能是 "low" 或 "default"。')
    return detail


def validate_mode(mode: object) -> str:
    if mode is None:
        return "summary"
    if mode not in MODES:
        raise ValidationError(f"mode 只能是：{'、'.join(MODES)}。")
    return mode
