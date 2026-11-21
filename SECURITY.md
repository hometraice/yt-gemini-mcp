# Security Policy

## Supported versions

Only the latest release on the default branch receives security fixes.

## Reporting a vulnerability

Please **do not** open a public issue for security problems.

Use GitHub's private reporting instead: go to the **Security** tab of this repository and choose **Report a vulnerability**. Include:

- what you found and its impact
- steps to reproduce (a minimal example is ideal)
- the version shown at the end of a tool result (`yt-gemini-mcp v…`)

**Never include API keys or other secrets in a report.** If you believe your own Gemini API key was exposed, revoke it immediately in [Google AI Studio](https://aistudio.google.com/apikey) and create a new one.

This is a small personal project maintained in spare time; I will acknowledge reports as soon as I can and credit reporters in the fix unless you prefer otherwise.

## Scope

In scope: anything that could leak the API key, make the server reach hosts other than the Gemini API, let video content escape the untrusted-content wrapper, or let the tool do more than read-only analysis.

Out of scope: issues in Google's Gemini API, YouTube, Claude, or the third-party packages themselves (please report those upstream).

---

### 繁體中文

發現資安問題請**不要**開公開的 issue，請到本 repo 的 **Security** 分頁選 **Report a vulnerability** 私下回報。回報內容請**不要**附上任何 API key；如果你的 key 可能外洩，請立刻到 Google AI Studio 撤銷並重建。
