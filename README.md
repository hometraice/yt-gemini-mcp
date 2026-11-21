> Version: v6.0 | 2026-11-22 | Output language setting (zh-TW / en); macOS support (experimental); tool descriptions in English

# yt-gemini-mcp

English | [繁體中文](README.zh-TW.md)

A local MCP server that lets Claude (Claude Code / Claude Desktop) "watch" public YouTube videos through the Google Gemini API: summaries, detailed notes, step-by-step tutorials, key quotes, claim extraction, Q&A, and analysis of a specific time range.

- Local **stdio** MCP server — opens **no network ports**
- Exactly one read-only tool, `analyze_youtube`; no file writes, no shell, no arbitrary HTTP
- Your API key lives **only in your OS key store** (Windows Credential Manager or macOS Keychain) — never in files, environment variables, or Claude config
- Bring your **own** Gemini API key (free to create in Google AI Studio)
- **Windows**, plus **macOS (experimental)**; output in **Traditional Chinese or English** (set `output_language` in `config.toml`)

---

## Security design

| Risk | Mitigation |
|---|---|
| API key leakage | Key stored only in the OS key store via `keyring` (service `yt-gemini-mcp`, user `gemini`), pinned per platform: WinVault on Windows, Keychain on macOS; other platforms are refused, never a plaintext fallback. No `.env`, no environment variables. The server refuses to start if `config.toml` contains anything that looks like a key |
| Key left on screen or in shell history | `set_key.py` uses `getpass` (hidden input); refuses command-line arguments and piped input; aborts if the terminal cannot hide input |
| Key in logs or error messages | All logs go to stderr through a redacting formatter (`AIza…`, `?key=`, `x-goog-api-key`, and the actual key in use); errors are fixed, human-readable messages with no stack traces |
| SSRF / abuse | Only `youtube.com/watch?v=`, `youtu.be/`, `youtube.com/shorts/`, `m.youtube.com/watch?v=` are accepted; exact host allowlist; 11-character video ID; the URL sent to Gemini is always rebuilt as `https://www.youtube.com/watch?v=<ID>` |
| Prompt injection | The Gemini system instruction says instructions inside the video must only be reported, never followed. Results are wrapped in `<untrusted_video_analysis>` tags whose opening and closing tags carry a per-call random id, so video content cannot forge the closing tag; tag-like text in the content (including full-width and invisible characters) is neutralized. Tutorial mode adds a "review before running" notice. Raw upstream error text is never returned to Claude |
| Supply chain | Only three direct dependencies (`mcp`, `google-genai`, `keyring`), pinned with `==`, locked with hashes in `uv.lock`, started with `--locked`; `exclude-newer` avoids freshly published releases |
| Quota / resources | Total time budget per call (70 s for chat, 240 s for code, including fallback); SDK auto-retry disabled in favour of a bounded model fallback (max 3) and at most one short retry per model on a fast 503; models whose daily quota is exhausted are skipped until reset; call limits (2 concurrent, 5 per minute, 100 per 24 h — excess calls are rejected); low media resolution by default; token usage logged (numbers only) |

Found a vulnerability? Please report it privately as described in [SECURITY.md](SECURITY.md) — do not open a public issue.

---

## Requirements

- Windows 10/11, or macOS (experimental — see below); a normal (non-admin) user account
- [Git](https://git-scm.com/downloads)
- [uv](https://docs.astral.sh/uv/) (manages Python for you)
- A Gemini API key from [Google AI Studio](https://aistudio.google.com/apikey)
- Claude Code and/or Claude Desktop

## Installation

**1. Install uv**

Windows (PowerShell):

```powershell
winget install --id=astral-sh.uv -e --source winget
```

macOS (Terminal, with [Homebrew](https://brew.sh)):

```bash
brew install uv
```

Open a **new** terminal afterwards so `PATH` is updated.

**2. Clone and create the environment** (installs the exact versions in `uv.lock`)

```powershell
git clone https://github.com/hometraice/yt-gemini-mcp.git
```

```powershell
cd yt-gemini-mcp
```

```powershell
uv sync --locked
```

Below, `<project-dir>` means the full path of the cloned folder, e.g. `C:\Users\<you>\yt-gemini-mcp` or `/Users/<you>/yt-gemini-mcp`.

## Set your API key

Run this **yourself** in a terminal (never paste the key into a Claude chat):

```powershell
uv run set_key.py
```

You will be asked to paste the key twice; input is hidden. Then verify:

```powershell
uv run set_key.py --check
```

You should see `[OK]` for every model used in `config.toml`. `--check` only fetches model metadata and does not consume generation quota.

On macOS the key goes into your login Keychain. The first time the server reads it, macOS may ask whether to allow access — the requesting program is the Python that uv manages for this project.

- Replace the key: run `uv run set_key.py` again
- Delete the key: `uv run set_key.py --delete`

**Recommended on the Google side:** restrict the key to the `Generative Language API` in [Google Cloud Console → Credentials](https://console.cloud.google.com/apis/credentials). If you suspect a leak, delete the key in [AI Studio](https://aistudio.google.com/apikey), create a new one, and run `set_key.py` again.

## Choosing a profile

You register the server once per Claude app and pick a **profile** for it. In plain terms:

| You use… | Profile | What you get |
|---|---|---|
| Claude Desktop chat, claude.ai on the web, or the mobile app (through Claude Desktop) | `chat` | Fast answers (usually 5–20 s) from `gemini-3.5-flash-lite`. These apps give up after about 80 s, so `chat` always finishes within 70 s |
| Claude Code (terminal, Code tab, Remote Control) | `code` | Deeper analysis from `gemini-3.8-flash` (often 1–3 minutes), with `flash-lite` as fallback. Best for long videos, tutorials and detailed notes |

Rule of thumb: quick questions anywhere → `chat`; "I want everything in this video and can wait" → `code` in Claude Code.

## Register with Claude Code

On Windows run this in **Git Bash** (Windows PowerShell 5.1 handles the `--` separator differently); on macOS use Terminal:

```bash
claude mcp add yt-gemini --scope user -- uv --directory '<project-dir>' run --locked server.py --profile code
```

`--profile code` uses the stronger `gemini-3.8-flash` model and a longer time budget (240 s). Note that the command contains **no key** — the server reads it from the OS key store at runtime.

Check with `claude mcp list`.

## Register with Claude Desktop

1. Find the full path of uv (Claude Desktop may not see your `PATH`):

   ```powershell
   (Get-Command uv).Source
   ```

   On macOS: `which uv` (usually `/opt/homebrew/bin/uv`).

2. In Claude Desktop open **Settings → Developer → Edit Config** and add (use your own paths; on Windows escape backslashes):

   ```json
   {
     "mcpServers": {
       "yt-gemini": {
         "command": "C:\\Users\\<you>\\...\\uv.exe",
         "args": [
           "--directory", "<project-dir with escaped backslashes>",
           "run", "--locked", "server.py", "--profile", "chat"
         ]
       }
     }
   }
   ```

   On macOS the same block works with plain paths, e.g. `"command": "/opt/homebrew/bin/uv"` and `"--directory", "/Users/<you>/yt-gemini-mcp"`.

   Do **not** add an `env` block with your key — this file is plain text. Use the `chat` profile here (fast `flash-lite`, 70 s budget): when Claude on the web or mobile calls a local MCP server through Claude Desktop, it gives up after roughly 80 seconds.

3. Fully quit Claude Desktop (including the tray icon) and start it again.

---

## Usage

Just ask Claude, for example:

- "Summarize this video: https://youtu.be/xxxxxxxxxxx"
- "What is discussed between 5:00 and 10:00?"
- "What numbers are on the slide? Use high resolution."
- "Turn this tutorial video into steps I can follow." (`tutorial`)
- "Write detailed notes for this video." (`notes`)

### Tool parameters

| Parameter | Type | Required | Description |
|---|---|---|---|
| `url` | string | yes | YouTube URL |
| `mode` | see below | no | Analysis mode, default `summary` |
| `question` | string | no | A question or focus (max 2000 chars). In `summary` mode only the question is answered; other modes keep their format and focus on it |
| `start` | int | no | Start time in seconds |
| `end` | int | no | End time in seconds (must be greater than `start`) |
| `detail` | `"low"` \| `"default"` | no | Frame resolution, default `low` (cheaper); use `default` for small on-screen text |
| `transcript` | string | no | The YouTube transcript you copied yourself (max 120,000 chars). Improves spelling of names and lets `quotes` cite the exact words |

### Adding a transcript (optional)

When you ask Claude to analyze a video without a transcript, Claude first asks whether you want to add one, or just analyze. To get the transcript:

1. Open the video on YouTube and click **...more** under the video
2. Click **Show transcript**
3. Select all of the transcript, copy it, and paste it into the chat

Gemini still watches the video for what is on screen; the transcript is used for exact names and quotes. Where it disagrees with the audio, the result says so. Answer "just analyze" (or "don't ask again") to skip.

- The server never fetches transcripts itself: unofficial scrapers break YouTube's terms and the official API only serves captions for your own videos
- The transcript is treated as untrusted data, like the video: it is wrapped in tags with a random id and Gemini is told never to follow instructions inside it
- Claude has to copy the transcript into the tool call, so for long videos paste only the part you care about. With `start`/`end`, the server keeps only that range (plus 30 s on each side) based on the timestamps
- It is sent to Google together with the video (free-tier data may be used by Google), so don't paste anything private

### Modes

| `mode` | Best for | Output |
|---|---|---|
| `summary` | Getting the big picture | Structured summary |
| `notes` | Capturing nearly everything | Detailed notes in 1–3 minute sections |
| `tutorial` | How-to / coding videos | Followable steps; on-screen commands, code and prompts copied verbatim into code blocks; a list of things to verify against official docs |
| `quotes` | Citing the speaker | 5–15 key quotes with timestamps |
| `claims` | Fact-checking | Factual claims, the evidence given, and verification priority |

Output always includes `[mm:ss]` timestamps and separates what was **seen** (【畫面】) from what was **heard** (【語音】); uncertain parts are marked.

### Reading the last line of a result

The footer (outside the untrusted tags) tells you which model answered and why, e.g. `模型：gemini-3.5-flash-lite，chat 入口的主要模型` ("primary model of the chat profile"):

- **Primary model of the chat profile** — expected: chat uses the fast `flash-lite` because of the ~80 s limit. Use Claude Code for deeper analysis.
- **Fallback model** — the primary model failed; the next line gives the reason (timeout, HTTP code, or daily quota exhausted).
- **Retried once** — Gemini answered `503` (overloaded) within a few seconds, so the server waited 1.5 s and tried the same model once more. It only does this when enough time is left, at most once per model.

When a call fails, the message says which kind of failure it was:

| Message | Meaning | What to do |
|---|---|---|
| Model temporarily overloaded (HTTP 503) | Google is short on capacity for this model | Try again in about a minute |
| Exceeded Google's time limit (HTTP 504) | Gemini took too long on Google's side | Analyze a shorter range with `start`/`end`; keep `detail="low"` |
| No response within N seconds; stopped waiting | The server's own time budget ran out | In `chat`, try again or switch to Claude Code (`code`, longer budget); split long videos |
- `yt-gemini-mcp v…` is the version currently loaded; if you still see an old version after updating, fully restart Claude Desktop.

### Tips

- Start with `summary`, then dig into important parts with `start`/`end`.
- For long videos or long outputs (`notes`, `tutorial`), work in 5–10 minute segments.
- Use `detail="default"` when the screen shows code, commands, or small text.

---

## Configuration (`config.toml`)

Each entry point (profile) has its own models and limits; pick one with `--profile` (default `chat`).

| Profile | Primary model | Fallback | Thinking level | Total / primary wait |
|---|---|---|---|---|
| `chat` | `gemini-3.5-flash-lite` | none | `low` | 70 s / 35 s |
| `code` | `gemini-3.8-flash` | `gemini-3.5-flash-lite` | `medium` | 240 s / 150 s |

- `model`, `fallback_models` — fallback is used on timeout, overload (5xx) or quota (429); max 3. Before falling back, a fast `503` gets one short retry on the same model (within that model's wait time)
- `thinking_level` — `low` / `medium` / `high`
- `timeout_seconds`, `attempt_timeout_seconds` — total budget and how long to wait for the primary model
- `[gemini] output_language` — `"zh-TW"` (Traditional Chinese, default) or `"en"` (English). Controls Gemini's answer and the messages the server returns to Claude (footer, errors). The descriptions Claude reads (tool and parameter descriptions, server instructions) are always in English; Claude still replies in your language
- `[gemini] max_output_tokens` — response length cap (default 16384)
- `[limits]` — `max_concurrent` (2), `max_calls_per_minute` (5), `max_calls_per_day` (100, rolling 24 h). Limits always apply, even if the section is missing
- `temperature` is not used (deprecated for Gemini 3 models); the server refuses to start if it is present

### Gemini free tier notes (checked against Google's docs, 2026-11)

- Quotas are per Google Cloud **project**, not per key; daily quotas reset at midnight Pacific Time
- Per-model free-tier numbers are not listed in the docs — check the rate-limit page in [AI Studio](https://aistudio.google.com)
- YouTube input: max 8 hours of video per day on the free tier; public videos only; the feature is in preview
- Free-tier content may be used by Google to improve its products — don't put secrets in `question`

When Gemini returns a 429 whose error details clearly indicate a **daily** quota, the server remembers that model and skips it until the next reset (computed as 08:00 UTC; up to one hour late during daylight saving time). Anything ambiguous is treated as a normal 429. This state is in memory only.

Token usage is logged to stderr after each successful call: `Gemini usage: model=… prompt=… output=… thoughts=… total=…` (numbers only, no content).

---

## Development

```powershell
uv run python -m unittest -v
```

Unit tests use mocks only — no network, no key. A live test (uses your key and a little quota; analyzes a 19-second public video) is opt-in:

```powershell
$env:YT_GEMINI_LIVE_TEST = "1"; uv run python -m unittest tests.test_live -v; Remove-Item Env:YT_GEMINI_LIVE_TEST
```

### Comparing two models (opt-in, uses quota)

`tools/compare_models.py` runs the same video and mode once on each of up to two models and records the time taken and token counts, to help you decide which model a profile should use:

```powershell
uv run tools/compare_models.py "https://youtu.be/<id>" --mode summary --start 0 --end 300
```

Without `--yes-use-quota` it only prints what it would do (dry run: no key read, no network). Add `--yes-use-quota` to actually call Gemini — **each model uses one request of your quota** (two if a fast `503` triggers the automatic retry). Only models listed in `config.toml` are accepted; by default it compares each profile's primary model. Results go to `logs\compare-<timestamp>-<random>\` (git-ignored): one `.md` per model with Gemini's output wrapped in untrusted tags, a `summary.json` with timings and token counts, and `run.log`. Logs are written only to `run.log`, never to the terminal. The key is read from the OS key store and never printed or written.

Project layout:

```
server.py        MCP server entry point (the only tool: analyze_youtube)
set_key.py       store / check / delete the API key
tools/           opt-in developer tools (compare_models.py)
config.toml      non-secret settings: profiles, models, time budgets, call limits
yt_gemini/       internal modules (config, keystore, messages, redaction, validation, gemini, quota, ratelimit, untrusted)
tests/           unit tests and the opt-in live test
SPEC.md          design spec and threat model (Traditional Chinese)
```

Dependencies: [`mcp`](https://pypi.org/project/mcp/) 2.3.0 (MIT), [`google-genai`](https://pypi.org/project/google-genai/) 2.34.0 (Apache-2.0), [`keyring`](https://pypi.org/project/keyring/) 25.7.0 (MIT). External services: Google Gemini API (receives the canonical video URL, your question and the system instruction; the key is sent in an HTTP header). Results appear in your Claude conversation.

See [CONTRIBUTING.md](CONTRIBUTING.md) before opening a pull request.

## Limitations

- Windows and macOS only. **macOS support is experimental**: unit tests run on macOS in CI, but Keychain access has not yet been verified on a real Mac — please report how it goes. Linux is not supported yet (there is no pinned secure key store, and the server never falls back to a plaintext file)
- Output languages: Traditional Chinese and English. Error messages about `config.toml` itself are in Chinese, because they can occur before the language setting is read
- Public videos only, one video per call
- `gemini-3.8-flash` is a preview model and is often overloaded (503/504); `code` falls back to `flash-lite` when that happens
- The `chat` profile has no fallback model (there is no time for one within 70 s). An occasional `503` is expected; the server retries once automatically, and if it still fails, just ask again
- A timed-out request may still be processed (and counted) on Google's side
- Developers have reported that with `start`/`end` on YouTube URLs, audio may still be billed for the whole video

## License

[MIT](LICENSE). This project is not affiliated with or endorsed by Google, YouTube, or Anthropic. Use of the Gemini API is subject to the [Gemini API Terms](https://ai.google.dev/gemini-api/terms).
