"""把 Gemini API key 存進作業系統的安全儲存區（Windows Credential Manager／macOS Keychain）。

用法（在專案資料夾執行）：
    uv run set_key.py            設定或更新 key（隱藏輸入，不會顯示在畫面上）
    uv run set_key.py --check    確認 key 已儲存且 Gemini 接受（不會顯示 key）
    uv run set_key.py --delete   刪除已儲存的 key

key 不透過命令列參數或 pipe 傳入，所以不會留在 shell history 或任何檔案裡。
訊息語言跟著 config.toml 的 [gemini] output_language（zh-TW／en）。
"""

from __future__ import annotations

import argparse
import getpass
import re
import sys
import warnings

from yt_gemini import keystore
from yt_gemini.messages import DEFAULT_LANGUAGE, t
from yt_gemini.redaction import redact

_KEY_SHAPE = re.compile(r"AIza[0-9A-Za-z_\-]{35}")


def _language() -> str:
    """config.toml 讀不到或有錯時用預設語言（設定錯誤會在 --check 時另外回報）。"""
    from yt_gemini.config import ConfigError, load_settings

    try:
        return load_settings().language
    except ConfigError:
        return DEFAULT_LANGUAGE


def _fail(lang: str, message: str) -> int:
    print(t(lang, "cli_error", message=redact(message)), file=sys.stderr)
    return 1


def _read_hidden(prompt: str) -> str:
    # getpass 在無法隱藏輸入時會「退回明碼顯示」並發出 GetPassWarning，這裡直接當成錯誤。
    with warnings.catch_warnings():
        warnings.simplefilter("error", getpass.GetPassWarning)
        return getpass.getpass(prompt).strip()


def cmd_set(lang: str = DEFAULT_LANGUAGE) -> int:
    if not sys.stdin.isatty() or sys.stdin is not sys.__stdin__:
        return _fail(lang, t(lang, "sk_need_tty"))

    store = keystore.store_name()
    print(t(lang, "sk_will_store", store=store, service=keystore.SERVICE, user=keystore.USERNAME))
    try:
        first = _read_hidden(t(lang, "sk_prompt_first"))
        if not first:
            return _fail(lang, t(lang, "sk_empty"))
        if not first.isascii() or not first.isprintable() or any(c.isspace() for c in first):
            return _fail(lang, t(lang, "sk_bad_chars"))
        if not _KEY_SHAPE.fullmatch(first):
            answer = input(t(lang, "sk_odd_shape"))
            if answer.strip().lower() != "y":
                return _fail(lang, t(lang, "sk_cancelled"))
        second = _read_hidden(t(lang, "sk_prompt_second"))
    except getpass.GetPassWarning:
        return _fail(lang, t(lang, "sk_no_hidden_input"))
    except (KeyboardInterrupt, EOFError):
        print()
        return _fail(lang, t(lang, "sk_cancelled"))

    if first != second:
        return _fail(lang, t(lang, "sk_mismatch"))

    try:
        keystore.set_api_key(first)
    except keystore.KeyStoreError as exc:
        return _fail(lang, exc.render(lang))
    finally:
        first = second = ""  # 盡快丟掉參照

    print(t(lang, "sk_saved", store=store))
    return 0


def cmd_check(lang: str = DEFAULT_LANGUAGE) -> int:
    try:
        api_key = keystore.get_api_key()
    except keystore.KeyStoreError as exc:
        return _fail(lang, exc.render(lang))
    print(t(lang, "sk_has_key", store=keystore.store_name()))

    # 延後匯入：設定 / 刪除 key 時不需要載入 Gemini SDK。
    from yt_gemini import gemini
    from yt_gemini.config import ConfigError, load_settings, profile_names

    # 檢查每個 profile 用到的每個模型（只查詢模型資訊，不消耗生成額度）。
    try:
        all_settings = [load_settings(profile=name) for name in profile_names()]
    except ConfigError as exc:
        return _fail(lang, str(exc))

    checked: set[str] = set()
    failed = 0
    for settings in all_settings:
        for model in (settings.model, *settings.fallback_models):
            if model in checked:
                continue
            checked.add(model)
            try:
                gemini.verify_access(api_key, settings, model=model)
            except gemini.AnalysisError as exc:
                failed += 1
                _fail(lang, t(lang, "sk_model_failed", model=model, message=str(exc)))
                continue
            print(t(lang, "sk_model_ok", model=model))
    return 1 if failed else 0


def cmd_delete(lang: str = DEFAULT_LANGUAGE) -> int:
    store = keystore.store_name()
    try:
        deleted = keystore.delete_api_key()
    except keystore.KeyStoreError as exc:
        return _fail(lang, exc.render(lang))
    if deleted:
        print(t(lang, "sk_deleted", store=store))
        print(t(lang, "sk_rotate_hint"))
    else:
        print(t(lang, "sk_nothing_to_delete", store=store))
    return 0


def main() -> int:
    lang = _language()
    parser = argparse.ArgumentParser(description=t(lang, "sk_description", store=keystore.store_name()))
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--check", action="store_true", help=t(lang, "sk_help_check"))
    group.add_argument("--delete", action="store_true", help=t(lang, "sk_help_delete"))
    args = parser.parse_args()

    if args.check:
        return cmd_check(lang)
    if args.delete:
        return cmd_delete(lang)
    return cmd_set(lang)


if __name__ == "__main__":
    # 輸出被導向時 Windows 預設用系統 codepage，中文會變亂碼；統一用 UTF-8。
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
