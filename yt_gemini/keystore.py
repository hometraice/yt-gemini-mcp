"""API key 的唯一存放處：作業系統的安全儲存區（透過 keyring）。

- Windows：Windows Credential Manager（WinVaultKeyring）。
- macOS：macOS Keychain（keyring.backends.macOS.Keyring）。實驗性，尚未實機驗證。
- 其他平台一律拒絕。依平台「固定」後端，不用 keyring 的自動選擇（keyring.get_keyring），所以
  PYTHON_KEYRING_BACKEND、keyringrc 等設定都不影響選到哪個後端，key 不會被導到明文的後端（例如 keyrings.alt）。
  註：keyring 的 macOS 後端在 import 時會讀 KEYCHAIN_PATH，但只會印出「Specified keychain is ignored」警告，
  不會改變存放位置。
- 本程式不讀環境變數、不讀 .env、不讀任何設定檔來取得 key。
"""

from __future__ import annotations

import sys

from yt_gemini.messages import DEFAULT_LANGUAGE, LocalizedError, t
from yt_gemini.redaction import register_secret

SERVICE = "yt-gemini-mcp"
USERNAME = "gemini"

_STORE_NAMES = {"win32": "Windows Credential Manager", "darwin": "macOS Keychain"}


class KeyStoreError(LocalizedError):
    """存取安全儲存區失敗。訊息保證不含 key。"""


class KeyNotFoundError(KeyStoreError):
    """安全儲存區裡沒有 key。提示文字（執行 set_key.py）跟著語言切換。"""

    def __init__(self) -> None:
        super().__init__("key_not_found", hint=t(DEFAULT_LANGUAGE, "set_key_hint"))

    def render(self, language: str) -> str:
        return t(language, "key_not_found", hint=t(language, "set_key_hint"))


def store_name() -> str:
    """目前平台的安全儲存區名稱（給使用者看的）。"""
    return _STORE_NAMES.get(sys.platform, "OS key store")


def _backend():
    if sys.platform == "win32":
        from keyring.backends.Windows import WinVaultKeyring

        return WinVaultKeyring()
    if sys.platform == "darwin":
        from keyring.backends.macOS import Keyring

        return Keyring()
    raise KeyStoreError("key_platform_unsupported")


def get_api_key() -> str:
    try:
        value = _backend().get_password(SERVICE, USERNAME)
    except KeyStoreError:
        raise
    except Exception as exc:  # 不串接原始例外，避免任何內容外洩
        raise KeyStoreError("key_read_failed", store=store_name(), error=type(exc).__name__) from None
    if not value:
        raise KeyNotFoundError()
    register_secret(value)
    return value


def set_api_key(value: str) -> None:
    register_secret(value)
    try:
        _backend().set_password(SERVICE, USERNAME, value)
    except KeyStoreError:
        raise
    except Exception as exc:
        raise KeyStoreError("key_write_failed", store=store_name(), error=type(exc).__name__) from None


def delete_api_key() -> bool:
    """刪除 key。回傳 True 表示有刪到，False 表示原本就沒有。"""
    backend = _backend()
    try:
        if backend.get_password(SERVICE, USERNAME) is None:
            return False
        backend.delete_password(SERVICE, USERNAME)
        return True
    except Exception as exc:
        raise KeyStoreError("key_delete_failed", store=store_name(), error=type(exc).__name__) from None
