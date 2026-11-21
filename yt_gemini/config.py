"""讀取 config.toml（只放非機密設定）。"""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass
from pathlib import Path

from yt_gemini.redaction import redact

# 以檔案位置定位，不依賴目前工作目錄（MCP client 啟動 server 時的 cwd 不一定是專案資料夾）。
CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.toml"

_MODEL_RE = re.compile(r"[a-z0-9][a-z0-9.\-]{1,63}")
_PROFILE_RE = re.compile(r"[a-z][a-z0-9_\-]{0,19}")
_FORBIDDEN_KEY_NAMES = {"api_key", "apikey", "key", "token", "secret", "password"}
_MOVED_TO_PROFILES = ("model", "fallback_models", "timeout_seconds", "attempt_timeout_seconds", "thinking_level")
# 不開放 minimal：gemini-3.8-flash 不支援，送出會錯誤。同一個 profile 的模型共用這個值。
THINKING_LEVELS = ("low", "medium", "high")
OUTPUT_LANGUAGES = ("zh-TW", "en")  # 必須和 messages.LANGUAGES 一致


class ConfigError(Exception):
    pass


MAX_FALLBACK_MODELS = 3
# 沒指定 --profile 時用最保守的 chat（80 秒內一定回應），避免忘了設定就在網頁版／手機逾時。
DEFAULT_PROFILE = "chat"


@dataclass(frozen=True)
class Settings:
    model: str
    timeout_seconds: int  # 整次工具呼叫（含備援）的總時間上限
    max_output_tokens: int
    fallback_models: tuple[str, ...] = ()
    attempt_timeout_seconds: int = 35  # 有備援時，每個非最後一個模型最多等多久
    profile: str = DEFAULT_PROFILE  # 使用入口（決定模型順序、思考強度、時間上限），例如 chat、code
    thinking_level: str | None = None  # None 代表用模型預設值
    # 呼叫上限（[limits]，所有 profile 共用；每個 server process 各自計算）
    max_concurrent: int = 2
    max_calls_per_minute: int = 5
    max_calls_per_day: int = 100
    language: str = "zh-TW"  # 輸出語言（[gemini] output_language）：Gemini 的回答與 server 回給 Claude 的訊息


def _model_id(value: object, field: str) -> str:
    if not isinstance(value, str) or not _MODEL_RE.fullmatch(value):
        raise ConfigError(f"config.toml：{field} 必須是模型 ID，例如 \"gemini-3.8-flash\"。")
    return value


def _number(table: dict, name: str, default, kind: type, low, high):
    value = table.get(name, default)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ConfigError(f"config.toml：{name} 必須是數字。")
    if kind is int and not isinstance(value, int):
        raise ConfigError(f"config.toml：{name} 必須是整數。")
    if not (low <= value <= high):
        raise ConfigError(f"config.toml：{name} 必須在 {low}–{high} 之間。")
    return kind(value)


def _reject_secrets(raw_text: str, data: dict) -> None:
    """config.toml 是明文檔案，絕不允許放 key。發現疑似 key 就拒絕啟動。"""
    if redact(raw_text) != raw_text:
        raise ConfigError(
            "config.toml 裡出現疑似 API key 的內容，已拒絕啟動。"
            "請刪除它，改用 `uv run set_key.py` 存進作業系統的安全儲存區（Windows Credential Manager／macOS Keychain），"
            "並到 Google AI Studio 撤銷（rotate）這把 key。"
        )

    def walk(node: dict) -> None:
        for k, v in node.items():
            if k.lower() in _FORBIDDEN_KEY_NAMES:
                raise ConfigError(
                    f"config.toml 不可以有「{k}」這種機密欄位。"
                    "API key 請用 `uv run set_key.py` 設定。"
                )
            if isinstance(v, dict):
                walk(v)

    walk(data)


def validate_profile_name(profile: object) -> str:
    if not isinstance(profile, str) or not _PROFILE_RE.fullmatch(profile):
        raise ConfigError("profile 名稱只能是小寫英數字、- 或 _（最多 20 字元），例如 chat、code。")
    return profile


def profile_names(path: Path = CONFIG_PATH) -> list[str]:
    """config.toml 裡所有 profile 的名稱（已通過格式驗證）。完整內容請用 load_settings 讀取與檢查。"""
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ConfigError(f"找不到設定檔：{path.name}") from None
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"config.toml 格式錯誤：{exc}") from None
    profiles = data.get("profiles")
    if not isinstance(profiles, dict) or not profiles:
        raise ConfigError("config.toml 缺少 [profiles.<名稱>] 區塊（例如 [profiles.chat]）。")
    return sorted(validate_profile_name(name) for name in profiles)


def load_settings(path: Path = CONFIG_PATH, profile: str = DEFAULT_PROFILE) -> Settings:
    profile = validate_profile_name(profile)
    try:
        raw_text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        # 只回檔名，不回本機完整路徑（錯誤訊息會進 Claude 對話紀錄）。
        raise ConfigError(f"找不到設定檔：{path.name}") from None
    try:
        data = tomllib.loads(raw_text)
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"config.toml 格式錯誤：{exc}") from None

    _reject_secrets(raw_text, data)

    gemini = data.get("gemini")
    if not isinstance(gemini, dict):
        raise ConfigError("config.toml 缺少 [gemini] 區塊。")

    for name in _MOVED_TO_PROFILES:
        if name in gemini:
            raise ConfigError(f"config.toml：{name} 已移到 [profiles.<名稱>] 區塊，請從 [gemini] 移除。")

    profiles = data.get("profiles")
    if not isinstance(profiles, dict) or not profiles:
        raise ConfigError("config.toml 缺少 [profiles.<名稱>] 區塊（例如 [profiles.chat]）。")
    for name in profiles:
        validate_profile_name(name)
    for name, sub in [("gemini", gemini), *profiles.items()]:
        if isinstance(sub, dict) and "temperature" in sub:
            # 官方已棄用 Gemini 3 系列的 temperature（API 會忽略，之後的模型會回錯誤），要明確移除，不默默忽略。
            raise ConfigError(f"config.toml：temperature 已不再使用，請從 [{name}] 移除。")
    table = profiles.get(profile)
    if not isinstance(table, dict):
        available = "、".join(sorted(profiles))
        raise ConfigError(f"config.toml 沒有 profile「{profile}」。可用的有：{available}。")

    model = _model_id(table.get("model"), f"profiles.{profile}.model")

    raw_fallbacks = table.get("fallback_models", [])
    if not isinstance(raw_fallbacks, list) or len(raw_fallbacks) > MAX_FALLBACK_MODELS:
        raise ConfigError(f"config.toml：fallback_models 必須是最多 {MAX_FALLBACK_MODELS} 個模型 ID 的清單。")
    fallbacks = tuple(_model_id(m, f"profiles.{profile}.fallback_models") for m in raw_fallbacks)
    if len(set((model, *fallbacks))) != len(fallbacks) + 1:
        raise ConfigError("config.toml：fallback_models 不可重複，也不可包含主要模型。")

    thinking = table.get("thinking_level")
    if thinking is not None and thinking not in THINKING_LEVELS:
        raise ConfigError(f"config.toml：thinking_level 只能是 {'、'.join(THINKING_LEVELS)}。")

    timeout = _number(table, "timeout_seconds", 70, int, 10, 600)
    attempt = _number(table, "attempt_timeout_seconds", 35, int, 5, 600)
    if fallbacks and attempt >= timeout:
        raise ConfigError(
            f"config.toml：profiles.{profile} 的 attempt_timeout_seconds 必須小於 timeout_seconds，"
            "備援模型才有時間執行。"
        )

    language = gemini.get("output_language", "zh-TW")
    if language not in OUTPUT_LANGUAGES:
        raise ConfigError(f"config.toml：output_language 只能是 {'、'.join(OUTPUT_LANGUAGES)}。")

    # 沒有 [limits] 也一定套用預設上限（fail closed：設定漏了不代表不限制）。
    limits = data.get("limits", {})
    if not isinstance(limits, dict):
        raise ConfigError("config.toml：[limits] 必須是區塊。")

    return Settings(
        max_concurrent=_number(limits, "max_concurrent", 2, int, 1, 5),
        max_calls_per_minute=_number(limits, "max_calls_per_minute", 5, int, 1, 60),
        max_calls_per_day=_number(limits, "max_calls_per_day", 100, int, 1, 2000),
        profile=profile,
        model=model,
        timeout_seconds=timeout,
        max_output_tokens=_number(gemini, "max_output_tokens", 8192, int, 256, 65536),
        fallback_models=fallbacks,
        attempt_timeout_seconds=attempt,
        thinking_level=thinking,
        language=language,
    )
