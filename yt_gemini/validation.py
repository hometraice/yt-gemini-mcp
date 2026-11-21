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
MAX_TRANSCRIPT_LENGTH = 120_000  # 約 1–2 小時影片的轉錄稿（含時間戳）
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


_HIDDEN_CATEGORIES = frozenset({"Cc", "Cf", "Cs", "Co", "Cn"})
_HIDDEN_CHARS = frozenset({0x3164, 0x115F, 0x1160, 0xFFA0})


def _is_hidden(ch: str) -> bool:
    cp = ord(ch)
    return (unicodedata.category(ch) in _HIDDEN_CATEGORIES or cp in _HIDDEN_CHARS
            or 0xFE00 <= cp <= 0xFE0F or 0xE0100 <= cp <= 0xE01EF)


# YouTube「顯示轉錄稿」複製出來的時間戳：獨立一行（或行首）的 m:ss、mm:ss、h:mm:ss。
_TIMESTAMP_RE = re.compile(r"^\s*(?:(\d{1,2}):)?(\d{1,2}):(\d{2})(?=\s|$)")
CLIP_MARGIN_SECONDS = 30


def clip_transcript(text: str, start: int | None, end: int | None) -> tuple[str, bool]:
    """有 start/end 時，依時間戳只留下 [start−30 秒, end+30 秒] 的部分，避免分段分析時每次重送整份。

    找不到足夠的時間戳（少於 2 個）或裁完是空的，就原樣回傳（fail open 只影響 token 用量，不影響安全）。
    回傳 (文字, 是否有裁切)。
    """
    if start is None and end is None:
        return text, False
    low = max(0, (start or 0) - CLIP_MARGIN_SECONDS)
    high = None if end is None else end + CLIP_MARGIN_SECONDS
    segments: list[tuple[int | None, list[str]]] = [(None, [])]
    for line in text.split("\n"):
        m = _TIMESTAMP_RE.match(line)
        if m:
            h, mm, ss = m.groups()
            seconds = int(h or 0) * 3600 + int(mm) * 60 + int(ss)
            segments.append((seconds, [line]))
        else:
            segments[-1][1].append(line)
    timed = [(t, lines) for t, lines in segments if t is not None]
    if len(timed) < 2:
        return text, False
    kept = [ln for t, lines in timed if t >= low and (high is None or t <= high) for ln in lines]
    clipped = "\n".join(kept).strip()
    if not clipped:
        return text, False
    return clipped, clipped != text


def validate_transcript(transcript: object) -> str | None:
    """使用者自己從 YouTube 複製的轉錄稿。只做格式清理與長度限制；內容仍是不可信資料。"""
    if transcript is None:
        return None
    if not isinstance(transcript, str):
        raise ValidationError("transcript 必須是字串。")
    if len(transcript) > MAX_TRANSCRIPT_LENGTH * 2:  # 清理前先擋掉明顯過大的輸入，避免白做工
        raise ValidationError(f"transcript 太長（上限 {MAX_TRANSCRIPT_LENGTH} 字元）。請只貼要分析的那一段。")
    text = transcript.replace("\r\n", "\n").replace("\r", "\n").replace("\u2028", "\n").replace("\u2029", "\n")
    # 移除看不見的字元：控制字元（保留 \n、\t）、格式字元（零寬、bidi）、surrogate、私用區、未指派，
    # 以及常被拿來夾帶隱藏文字的 variation selector 與韓文填充字元。
    text = "".join(ch for ch in text if ch in "\n\t" or not _is_hidden(ch)).strip()
    if not text:
        return None
    if len(text) > MAX_TRANSCRIPT_LENGTH:
        raise ValidationError(f"transcript 太長（上限 {MAX_TRANSCRIPT_LENGTH} 字元）。請只貼要分析的那一段。")
    return text


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
