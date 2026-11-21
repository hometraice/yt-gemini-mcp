"""把 Gemini API key 存進 Windows Credential Manager。

用法（在專案資料夾執行）：
    uv run set_key.py            設定或更新 key（隱藏輸入，不會顯示在畫面上）
    uv run set_key.py --check    確認 key 已儲存且 Gemini 接受（不會顯示 key）
    uv run set_key.py --delete   刪除已儲存的 key

key 不透過命令列參數或 pipe 傳入，所以不會留在 shell history 或任何檔案裡。
"""

from __future__ import annotations

import argparse
import getpass
import re
import sys
import warnings

from yt_gemini import keystore
from yt_gemini.redaction import redact

_KEY_SHAPE = re.compile(r"AIza[0-9A-Za-z_\-]{35}")


def _fail(message: str) -> int:
    print(f"[錯誤] {redact(message)}", file=sys.stderr)
    return 1


def _read_hidden(prompt: str) -> str:
    # getpass 在無法隱藏輸入時會「退回明碼顯示」並發出 GetPassWarning，這裡直接當成錯誤。
    with warnings.catch_warnings():
        warnings.simplefilter("error", getpass.GetPassWarning)
        return getpass.getpass(prompt).strip()


def cmd_set() -> int:
    if not sys.stdin.isatty() or sys.stdin is not sys.__stdin__:
        return _fail("請在互動式終端機直接執行，不接受 pipe 或重新導向輸入（避免 key 留在檔案或 history）。")

    print(f"將儲存到 Windows Credential Manager（service={keystore.SERVICE}, user={keystore.USERNAME}）")
    try:
        first = _read_hidden("貼上 Gemini API key（輸入不會顯示），按 Enter：")
        if not first:
            return _fail("沒有輸入內容，未儲存。")
        if not first.isascii() or not first.isprintable() or any(c.isspace() for c in first):
            return _fail("內容含有空白或非 ASCII 字元，看起來不是 API key，未儲存。")
        if not _KEY_SHAPE.fullmatch(first):
            answer = input("這看起來不像 Google AI Studio 的 key（通常是 AIza 開頭、共 39 字元）。仍要儲存？[y/N] ")
            if answer.strip().lower() != "y":
                return _fail("已取消，未儲存。")
        second = _read_hidden("再貼一次確認：")
    except getpass.GetPassWarning:
        return _fail("這個終端機無法隱藏輸入，為了安全已中止。請改用 Windows Terminal 或 PowerShell 執行。")
    except (KeyboardInterrupt, EOFError):
        print()
        return _fail("已取消，未儲存。")

    if first != second:
        return _fail("兩次輸入不一致，未儲存。")

    try:
        keystore.set_api_key(first)
    except keystore.KeyStoreError as exc:
        return _fail(str(exc))
    finally:
        first = second = ""  # 盡快丟掉參照

    print("[OK] 已存入 Windows Credential Manager。接著可執行 `uv run set_key.py --check` 驗證。")
    return 0


def cmd_check() -> int:
    try:
        api_key = keystore.get_api_key()
    except keystore.KeyStoreError as exc:
        return _fail(str(exc))
    print("[OK] Credential Manager 裡有 key。")

    # 延後匯入：設定 / 刪除 key 時不需要載入 Gemini SDK。
    from yt_gemini import gemini
    from yt_gemini.config import ConfigError, load_settings, profile_names

    # 檢查每個 profile 用到的每個模型（只查詢模型資訊，不消耗生成額度）。
    try:
        all_settings = [load_settings(profile=name) for name in profile_names()]
    except ConfigError as exc:
        return _fail(str(exc))

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
                _fail(f"{model}：{exc}")
                continue
            print(f"[OK] Gemini 接受這把 key，模型 {model} 可以使用。")
    return 1 if failed else 0


def cmd_delete() -> int:
    try:
        deleted = keystore.delete_api_key()
    except keystore.KeyStoreError as exc:
        return _fail(str(exc))
    if deleted:
        print("[OK] 已從 Windows Credential Manager 刪除 key。")
        print("  如果這把 key 可能外洩過，也請到 Google AI Studio 撤銷它。")
    else:
        print("Credential Manager 裡原本就沒有 key。")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="管理 yt-gemini-mcp 的 Gemini API key（存於 Windows Credential Manager）。"
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--check", action="store_true", help="確認 key 已儲存且可用（不顯示 key）")
    group.add_argument("--delete", action="store_true", help="刪除已儲存的 key")
    args = parser.parse_args()

    if args.check:
        return cmd_check()
    if args.delete:
        return cmd_delete()
    return cmd_set()


if __name__ == "__main__":
    sys.exit(main())
