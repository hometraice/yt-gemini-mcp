# Contributing

Thanks for your interest! This is a small, security-focused tool, so the bar for changes is "keep it simple and keep it safe".

## Before you start

- For anything beyond a small fix, please open an issue first to discuss it.
- Security issues: follow [SECURITY.md](SECURITY.md) instead of opening an issue.

## Ground rules

- **Never commit secrets.** No API keys in code, tests, config, logs, or screenshots. Tests use fake keys and mocks only.
- **No new dependencies** without discussion. The project deliberately depends only on `mcp`, `google-genai`, and `keyring`, pinned in `uv.lock`.
- **Keep the attack surface small:** one read-only tool, stdio only, no file writes, no shell, no arbitrary network requests.
- Validate every external input (allowlist, type, length) and add unit tests for any security-relevant logic.
- Unit tests must not call the real Gemini API.

## Development setup

```powershell
uv sync --locked
uv run python -m unittest -v
```

Please make sure all tests pass before opening a pull request, and describe what changed and why.

---

### 繁體中文

歡迎貢獻！較大的修改請先開 issue 討論。請勿 commit 任何 key；不要新增套件；單元測試只能用 mock，不能呼叫真的 Gemini API。送 PR 前請確認 `uv run python -m unittest -v` 全部通過。
