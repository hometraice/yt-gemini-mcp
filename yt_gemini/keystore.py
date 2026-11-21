"""API key 的唯一存放處：Windows Credential Manager（透過 keyring）。

- 不讀環境變數、不讀 .env、不讀任何設定檔。
- 明確指定 WinVaultKeyring，不讓 PYTHON_KEYRING_BACKEND 等環境變數把 key 導到別的後端。
"""

from __future__ import annotations

import sys

from yt_gemini.redaction import register_secret

SERVICE = "yt-gemini-mcp"
USERNAME = "gemini"

SET_KEY_HINT = "請先執行 set_key.py（在專案資料夾執行：uv run set_key.py）"


class KeyStoreError(Exception):
    """存取 Credential Manager 失敗。訊息保證不含 key。"""


class KeyNotFoundError(KeyStoreError):
    """Credential Manager 裡沒有 key。"""


def _backend():
    if sys.platform != "win32":
        raise KeyStoreError("目前只支援 Windows Credential Manager。")
    from keyring.backends.Windows import WinVaultKeyring

    return WinVaultKeyring()


def get_api_key() -> str:
    try:
        value = _backend().get_password(SERVICE, USERNAME)
    except KeyStoreError:
        raise
    except Exception as exc:  # 不串接原始例外，避免任何內容外洩
        raise KeyStoreError(
            f"無法讀取 Windows Credential Manager（{type(exc).__name__}）。"
        ) from None
    if not value:
        raise KeyNotFoundError(f"找不到 Gemini API key。{SET_KEY_HINT}")
    register_secret(value)
    return value


def set_api_key(value: str) -> None:
    register_secret(value)
    try:
        _backend().set_password(SERVICE, USERNAME, value)
    except KeyStoreError:
        raise
    except Exception as exc:
        raise KeyStoreError(
            f"無法寫入 Windows Credential Manager（{type(exc).__name__}）。"
        ) from None


def delete_api_key() -> bool:
    """刪除 key。回傳 True 表示有刪到，False 表示原本就沒有。"""
    backend = _backend()
    try:
        if backend.get_password(SERVICE, USERNAME) is None:
            return False
        backend.delete_password(SERVICE, USERNAME)
        return True
    except Exception as exc:
        raise KeyStoreError(
            f"無法刪除 Windows Credential Manager 裡的 key（{type(exc).__name__}）。"
        ) from None
