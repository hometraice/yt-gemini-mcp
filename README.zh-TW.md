> Version: v8.0 | 2026-11-22 | 轉錄稿詢問：有可點選的按鈕才問，沒有就直接分析並附提示

# yt-gemini-mcp

[English](README.md) | 繁體中文

讓 Claude（Claude Code／Claude Desktop）透過 Google Gemini API「觀看」公開的 YouTube 影片：摘要、詳細筆記、教學步驟、重要原話、主張整理、問答、指定片段分析。

- 本機 stdio MCP server，**不開任何網路 port**
- 只有一個工具 `analyze_youtube`，沒有寫檔、shell、任意 HTTP request
- API key 只存在**作業系統的安全儲存區**（Windows Credential Manager 或 macOS Keychain），不在任何檔案、環境變數或 Claude 設定裡
- 每個人用**自己的** Gemini API key（Google AI Studio 可免費申請）
- 支援 **Windows**，**macOS 為實驗性支援**；輸出可選**繁體中文或英文**（`config.toml` 的 `output_language`）

---

## 資安設計

| 風險 | 對策 |
|---|---|
| API key 外洩 | key 只存在作業系統的安全儲存區（`keyring`，service=`yt-gemini-mcp`、user=`gemini`），依平台固定後端：Windows 用 WinVault、macOS 用 Keychain；其他平台一律拒絕，不會退回明文檔案。不讀 `.env`、不讀環境變數。`config.toml` 若出現疑似 key，server 拒絕啟動 |
| key 留在畫面或 history | `set_key.py` 用 `getpass` 隱藏輸入；不接受命令列參數或 pipe；終端機無法隱藏輸入時直接中止 |
| key 出現在 log／錯誤訊息 | 所有 log 走 stderr 並經過遮罩（`AIza…`、`?key=`、`x-goog-api-key`、實際使用中的 key），錯誤訊息只回傳固定的中文說明，不吐 stack trace |
| SSRF／濫用 | 只接受 `youtube.com/watch?v=`、`youtu.be/`、`youtube.com/shorts/`、`m.youtube.com/watch?v=`；host 白名單完全比對；ID 必須是 11 碼；一律用 ID 重組 `https://www.youtube.com/watch?v=<ID>` 再送出 |
| Prompt injection | system instruction 規定影片內的指令只能轉述、不可執行；回傳結果包在 `<untrusted_video_analysis>` 裡，開始與結束標記帶每次隨機產生的 id（影片內容無法偽造結尾），並中和內容裡偽造的標記（含全形與看不見的字元）；tutorial 模式在結尾提醒「執行前必須人工審查」；Gemini 的原始錯誤訊息不放進回覆 |
| 供應鏈 | 只有 `mcp`、`google-genai`、`keyring` 三個直接相依，版本用 `==` 固定、`uv.lock` 鎖定，啟動時用 `--locked`；`exclude-newer` 排除剛發布的版本 |
| 額度／資源 | 整次呼叫有總時間上限（Chat 70 秒、Code 240 秒，含備援）；關閉 SDK 自動重試，改成主要模型失敗時換備援模型（最多 3 個），快速回 503 時對同一模型最多短重試 1 次；每日額度用完的模型當天直接跳過；呼叫上限（同時 2 個、每分鐘 5 次、24 小時 100 次，超過就拒絕）；預設低 media resolution；token 用量寫進 log（只有數字） |

發現資安問題請依 [SECURITY.md](SECURITY.md) 私下回報，不要開公開的 issue。

---

## 資料夾結構

```
yt-gemini-mcp/
├── server.py           MCP server 進入點（唯一工具 analyze_youtube）
├── set_key.py          設定／檢查／刪除 API key
├── config.toml         各使用入口的模型、思考強度、時間上限、呼叫上限等非機密設定
├── yt_gemini/          內部模組
│   ├── config.py         讀取並檢查 config.toml
│   ├── keystore.py       安全儲存區存取（Windows Credential Manager／macOS Keychain）
│   ├── messages.py       使用者看得到的訊息（繁中／英文）
│   ├── redaction.py      機密遮罩（log、錯誤訊息）
│   ├── validation.py     URL 與參數驗證
│   ├── gemini.py         呼叫 Gemini、備援、錯誤轉換、token 用量 log
│   ├── quota.py          每日額度用完的模型（只存在記憶體）
│   ├── ratelimit.py      呼叫上限：同時進行數、每分鐘、每 24 小時
│   └── untrusted.py      不可信資料標記
├── tools/              開發用工具（compare_models.py：模型對照，會消耗額度，要明確加參數才執行）
├── tests/              單元測試與實際呼叫測試
├── pyproject.toml      專案設定與程式版本（SemVer）
├── uv.lock             鎖定所有套件的版本與 hash
├── SPEC.md             開發規格與威脅分析（中文）
├── CHANGELOG.md        文件與設定檔的變更紀錄
├── SECURITY.md         資安問題回報方式
├── CONTRIBUTING.md     貢獻方式
└── LICENSE             MIT
```

---

## 元件清單

**直接使用的第三方套件**（版本在 `pyproject.toml` 用 `==` 固定；含間接相依全部記在 `uv.lock`）

| 套件 | 版本 | 授權 | 用途 |
|---|---|---|---|
| [`mcp`](https://pypi.org/project/mcp/) | 2.3.0 | MIT | MCP 官方 Python SDK（`MCPServer`、stdio transport） |
| [`google-genai`](https://pypi.org/project/google-genai/) | 2.34.0 | Apache-2.0 | Google 官方 Gemini SDK |
| [`keyring`](https://pypi.org/project/keyring/) | 25.7.0 | MIT | 讀寫 Windows Credential Manager／macOS Keychain |

**外部服務**

| 服務 | 送出的資料 | 備註 |
|---|---|---|
| Google Gemini API | 影片標準網址、問題、system instruction；key 放在 HTTP header | free tier 的內容可能被 Google 用來改進產品 |
| YouTube | 本機不直接連線，由 Gemini 讀取公開影片 | — |
| Anthropic（Claude） | 分析結果會出現在 Claude 對話裡 | 依你使用的 Claude 產品，對話可能存於 Anthropic |

---

## 安裝

需求：Windows 10/11 或 macOS（實驗性，見下方）、Git、一般使用者權限（不需要系統管理員）。

**1. 安裝 uv**（不用另外裝 Python，uv 會管理）

Windows（PowerShell）：

```powershell
winget install --id=astral-sh.uv -e --source winget
```

macOS（終端機，需要 [Homebrew](https://brew.sh)）：

```bash
brew install uv
```

裝完後**重開終端機**，PATH 才會更新。

**2. 下載程式並建立環境**（依照 `uv.lock` 安裝鎖定的版本）

```powershell
git clone https://github.com/hometraice/yt-gemini-mcp.git
```

```powershell
cd yt-gemini-mcp
```

```powershell
uv sync --locked
```

以下用 `<專案資料夾>` 代表剛剛 clone 下來的資料夾完整路徑，例如 `C:\Users\<你的帳號>\yt-gemini-mcp` 或 `/Users/<你的帳號>/yt-gemini-mcp`。

---

## 設定 API key

1. 到 [Google AI Studio](https://aistudio.google.com/apikey) 建立一把 Gemini API key。
2. **自己**在終端機執行（不要把 key 貼進 Claude 的對話框）：

```powershell
uv run set_key.py
```

畫面會要求貼上 key 兩次，輸入不會顯示。接著驗證：

```powershell
uv run set_key.py --check
```

每個模型都顯示 `[OK] Gemini 接受這把 key，模型 … 可以使用` 就完成了。`--check` 會檢查 `config.toml` 所有使用入口用到的模型，只查詢模型資訊，不消耗生成額度。

其他操作：

- 更換 key：再執行一次 `uv run set_key.py`
- 刪除 key：`uv run set_key.py --delete`
- 在 Windows 裡查看：控制台 → 認證管理員 → Windows 認證 → 一般認證 → `yt-gemini-mcp`
- macOS：key 存在登入鑰匙圈（「鑰匙圈存取」App 可以看到 `yt-gemini-mcp`）。server 第一次讀取時 macOS 可能詢問是否允許，要求的程式是 uv 為這個專案管理的 Python

**建議再加兩道保護**（在 Google 那一端）：

1. 到 [Google Cloud Console → API 和服務 → 憑證](https://console.cloud.google.com/apis/credentials) 編輯這把 key，**API 限制**只勾 `Generative Language API`。這樣即使 key 外洩，也不能拿去呼叫別的 Google API。
2. 懷疑外洩時，到 [Google AI Studio](https://aistudio.google.com/apikey) 立刻刪除舊 key、建立新 key，再執行 `uv run set_key.py`。

---

## 怎麼選 profile

每個 Claude 入口註冊一次，註冊時選一個 profile。白話對照：

| 你在哪裡用 | profile | 會得到什麼 |
|---|---|---|
| Claude Desktop 一般 Chat、網頁版、手機 App（經由桌機） | `chat` | 用 `gemini-3.5-flash-lite`，通常 5–20 秒就有結果。這些入口大約 80 秒就放棄等待，所以 `chat` 一定在 70 秒內結束 |
| Claude Code（終端機、Code 分頁、Remote Control） | `code` | 用分析較深的 `gemini-3.8-flash`（常要 1–3 分鐘），失敗時改用 flash-lite。適合長影片、教學影片、詳細筆記 |

簡單記：隨手問問 → `chat`；想把影片內容完整整理、可以等 → 在 Claude Code 用 `code`。

## 註冊到 Claude Code

Windows 在 Git Bash 執行（PowerShell 5.1 處理 `--` 參數的方式不同，所以用 Git Bash）；macOS 用終端機：

```bash
claude mcp add yt-gemini --scope user -- uv --directory '<專案資料夾>' run --locked server.py --profile code
```

`--scope user` 代表所有專案都能用。`--profile code` 讓 Claude Code 使用分析較深的 `gemini-3.8-flash` 和較長的時間上限（240 秒）。注意指令裡**沒有任何 key**，server 啟動時會自己去安全儲存區讀取。

確認（Git Bash）：

```bash
claude mcp list
```

---

## 註冊到 Claude Desktop

1. 先找出 uv 的完整路徑（Claude Desktop 不一定讀得到 PATH）：

   ```powershell
   (Get-Command uv).Source
   ```

   macOS：`which uv`（通常是 `/opt/homebrew/bin/uv`）。

2. 在 Claude Desktop 開啟 **設定 → Developer → Edit Config**，編輯 `claude_desktop_config.json`，加入以下內容（換成你的路徑；Windows 的反斜線要寫兩次）：

   ```json
   {
     "mcpServers": {
       "yt-gemini": {
         "command": "C:\\Users\\<你的帳號>\\...\\uv.exe",
         "args": [
           "--directory", "<專案資料夾，反斜線寫兩次>",
           "run", "--locked", "server.py", "--profile", "chat"
         ]
       }
     }
   }
   ```

   macOS 寫一般路徑即可，例如 `"command": "/opt/homebrew/bin/uv"`、`"--directory", "/Users/<你的帳號>/yt-gemini-mcp"`。

   **不要**加 `env` 區塊放 key，這個檔案是明文。這裡要用 `chat`（速度快的 flash-lite、70 秒），因為 Claude 網頁版和手機經由桌機呼叫時，約 80 秒就放棄等待。

3. 完全結束 Claude Desktop（系統匣圖示也要結束）再重開。

---

## 使用方式

直接跟 Claude 說，例如：

- 「幫我摘要這支影片 https://youtu.be/xxxxxxxxxxx」
- 「這支影片 5 分到 10 分在講什麼？」
- 「影片裡投影片上寫的數字是多少？用高解析度看」
- 「把這支教學影片整理成我可以照做的步驟」（tutorial）
- 「幫我做這支影片的詳細筆記」（notes）

工具參數：

| 參數 | 型別 | 必填 | 說明 |
|---|---|---|---|
| `url` | string | 是 | YouTube 網址 |
| `mode` | 見下表 | 否 | 分析模式，預設 `summary` |
| `question` | string | 否 | 要問的問題或想聚焦的範圍（最多 2000 字元）。`summary` 模式下只回答問題；其他模式照該模式的格式、聚焦在問題上 |
| `start` | int | 否 | 開始秒數 |
| `end` | int | 否 | 結束秒數，必須大於 `start` |
| `detail` | `"low"` \| `"default"` | 否 | 畫面解析度，預設 `low`（省 token）；要看小字或細節用 `default` |
| `transcript` | string | 否 | 你自己從 YouTube 複製的轉錄稿（最多 120,000 字元）。讓人名、產品名拼法更準，quotes 能逐字引用 |
| `skip_transcript` | bool | 否 | 你選擇不附轉錄稿、直接分析時，由 Claude 設定 |

**附上轉錄稿（選填）**

每支影片第一次分析、又沒附轉錄稿時，server 先不呼叫 Gemini（這一步不耗額度）：

- Claude 能顯示可點選的選項時（例如 Code 分頁），會跳出兩個按鈕讓你點：**貼上轉錄稿**或**直接分析**
- 沒有按鈕時（例如 Claude Desktop 的 Chat），Claude 不會用文字問你，直接分析，結尾附一行可以附轉錄稿的提示
- 每支影片只檢查一次

取得轉錄稿的步驟：

1. 在 YouTube 打開影片頁面，點資訊欄的「顯示完整資訊」
2. 點「顯示轉錄稿」
3. 把轉錄稿全選、複製，貼回對話

- 畫面上的內容仍由 Gemini 看影片判斷；轉錄稿用來對照專有名詞拼法和原話。轉錄稿和語音對不上時，結果會標出來
- 不想附就回「直接分析」；說「不要再問」，之後就不會再問
- 完全不想被問：把 `config.toml` 的 `ask_for_transcript` 改成 `false`。沒附轉錄稿的結果，結尾會多一行提示
- server 不會自己去 YouTube 抓轉錄稿：非官方的抓法違反 YouTube 服務條款，官方 API 只能下載自己影片的字幕
- 轉錄稿和影片一樣當成不可信資料：包在帶隨機 id 的標記裡，Gemini 被要求不可執行裡面的任何指令
- Claude 要把轉錄稿原封不動放進工具參數，長影片會比較慢、比較耗 token，建議只貼要分析的那一段。有 `start`／`end` 時，server 會依時間戳只留下那段時間（前後各多 30 秒）
- 轉錄稿會和影片一起送給 Google（free tier 的內容可能被用來改進產品），不要貼私人內容

**分析模式**

| `mode` | 適合 | 輸出 |
|---|---|---|
| `summary` | 先了解影片在講什麼 | 結構化摘要 |
| `notes` | 想掌握幾乎所有內容 | 依時間分段（每段 1–3 分鐘）的詳細筆記 |
| `tutorial` | 教學、實作影片 | 可照做的步驟；畫面上的指令、程式碼、提示詞逐字抄進 code block；列出需要對照官方文件的地方 |
| `quotes` | 需要引用講者的話 | 5–15 句重要原話與時間戳 |
| `claims` | 想查證影片的說法 | 影片中的事實性主張、講者給的證據、查證優先度 |

回答預設是繁體中文（`output_language = "en"` 則改成英文，標示用 `[Visual]`／`[Audio]`），附 `[mm:ss]` 時間戳，區分【畫面】與【語音】，不確定的地方會標明。人名、指令、程式碼這類內容畫面有出現就逐字抄寫，拼法沒把握會標「（拼法不確定）」。

**怎麼得到比較好的結果**

- 先用 `summary` 了解全貌，再針對重要段落用 `start` / `end` 深入（Claude 會照工具說明自動這樣做）。
- 長影片或 `notes`、`tutorial` 這類長輸出：分段，每段 5–10 分鐘。
- 畫面上有程式碼、指令、小字：加 `detail="default"`。
- 回覆最後一行會寫出模型和它的角色，例如「模型：gemini-3.5-flash-lite，chat 入口的主要模型」：
  - **chat 入口的主要模型**：Chat、網頁版、手機因為約 80 秒的限制，本來就用速度快的 flash-lite，不是額度或錯誤造成的。要更深入的分析，請改用 Claude Code
  - **備援模型**：主要模型失敗了，下一行會寫原因（逾時、HTTP 錯誤碼或今日額度已用完）
  - **重試 1 次後成功**：Gemini 幾秒內就回 503（過載），server 等 1.5 秒後對同一個模型再試一次。只有剩下的時間夠才會重試，每個模型最多 1 次
  - 最後的 `yt-gemini-mcp v…` 是目前載入的程式版本；更新後還看到舊版號，代表要完全重開 Claude Desktop。Claude 被要求在回覆最後原樣附上這一行；沒附的話，可以在 Claude 裡展開工具呼叫看原始結果
- 回覆最後寫了「今日額度已用完」，代表那個模型要等每日重置（太平洋時間午夜，台灣時間約 16:00）才會再用。

**把教學影片整理成 Claude 能重複使用的做法**

Claude 不會因為看過影片就「記住」。要讓它以後都會用，要把做法寫成它每次都會讀到的文件：

1. 在 Claude Code 裡請 Claude 用 `tutorial` 模式分段整理影片。
2. 請 Claude 對照官方文件，把過時或錯誤的步驟修正，再用自己的話寫成 skill（`SKILL.md`），不要整段照抄影片。
3. 你看過、確認沒問題後，再放進 `~/.claude/skills/<名稱>/`（所有專案都能用）或專案的 `.claude/skills/`。
4. skill 裡的指令和設定，第一次使用前仍要自己看過；影片內容屬於不可信資料。

**在哪裡可以用**

| 入口 | profile | 說明 |
|---|---|---|
| Claude Code（終端機、Claude Desktop 的 Code 分頁） | `code` | 用 `claude mcp add --scope user` 註冊後，所有專案都能用 |
| Claude Desktop 的一般 Chat | `chat` | 加進 `claude_desktop_config.json` 並完全重開 Claude Desktop |
| Claude 網頁版／手機 App（經由桌機的 Claude Desktop） | `chat` | 桌機要開著、不睡眠。這條路大約 **80 秒**就放棄等待 |

**模型與備援**（都在 `config.toml`，不用改程式）

每個使用入口（profile）各自設定，註冊時用 `--profile` 指定，沒指定就用 `chat`：

| profile | 主要模型 | 備援模型 | 思考強度 | 總時間／主要模型最多等 |
|---|---|---|---|---|
| `chat` | `gemini-3.5-flash-lite` | 無 | `low` | 70 秒／35 秒 |
| `code` | `gemini-3.8-flash` | `gemini-3.5-flash-lite` | `medium` | 240 秒／150 秒 |

- `model`、`fallback_models`：主要模型逾時、過載（5xx）或額度用完（429）時，依序改用備援模型（最多 3 個）。換備援之前，快速回 503 的模型會先在自己的等待時間內短重試 1 次
- `thinking_level`：`low`／`medium`／`high`。越高越深入，但越慢、用量越多
- `timeout_seconds`：整次呼叫的總上限；`attempt_timeout_seconds`：主要模型最多等幾秒就換備援
- `[gemini]` 的 `output_language`：`"zh-TW"`（繁體中文，預設）或 `"en"`（英文）。決定 Gemini 的回答，以及 server 回給 Claude 的訊息（結尾、錯誤訊息）。給 Claude 讀的工具說明一律是英文，Claude 回你時仍會用你的語言
- `[gemini]` 的 `ask_for_transcript`：`true`（預設）或 `false`。開啟時，每支影片第一次分析、沒附轉錄稿，會先問你要不要附上
- `[gemini]` 的 `max_output_tokens`：回應長度上限，預設 16384
- 不使用 `temperature`：官方已棄用 Gemini 3 系列的這個參數，`config.toml` 裡有它的話 server 會拒絕啟動

**Free tier 的限制**（2026-11 對照官方文件）

| 項目 | 內容 |
|---|---|
| 額度計算單位 | 依 Google Cloud **project**，不是依 key。同一個 project 建新 key 不會多出額度 |
| 每日額度重置 | 太平洋時間午夜 |
| 各模型每天幾次 | 官方文件沒有列出，請到 [AI Studio](https://aistudio.google.com) 的 rate limit 頁面查看 |
| YouTube 影片 | 每天最多 8 小時；只能分析公開影片 |
| 功能狀態 | YouTube 網址功能仍是 preview，價格與額度可能改變 |
| 資料使用 | free tier 的內容會被 Google 用來改進產品，`question` 不要放機密 |

**每日額度用完時**：Gemini 回 429，而且錯誤細節明確寫是「每日」額度時，server 會記住這個模型，在重置前直接跳過它、改用備援模型，回覆最後一行會寫出原因和恢復時間。恢復時間一律算到 UTC 08:00（夏令時間期間最多多跳過 1 小時）。判斷不出是不是每日額度時，只換備援模型。這份記錄只在記憶體裡，重開就清空。

**呼叫上限**（`config.toml` 的 `[limits]`）：同時最多 2 個分析、每分鐘 5 次、最近 24 小時 100 次。目的是防止 Claude 被影片內容誘導、或自己陷入迴圈，連續呼叫把額度用完。超過時會直接回覆「請約 N 秒後再試」，不會排隊。

**token 用量**：每次成功呼叫後，server 會在 log（stderr）寫一行 `Gemini usage: model=… prompt=… output=… thoughts=… total=…`，只有數字，不含影片或問題內容。

---

## 測試

單元測試（不連網路、不需要 key）：

```powershell
uv run python -m unittest -v
```

實際呼叫測試（需要先設定 key，會分析一支 19 秒的公開短片，消耗少量額度）：

```powershell
$env:YT_GEMINI_LIVE_TEST = "1"; uv run python -m unittest tests.test_live -v; Remove-Item Env:YT_GEMINI_LIVE_TEST
```

**比較兩個模型**（開發用，⚠️ 會消耗額度）：`tools/compare_models.py` 用同一支影片、同一個 mode，對最多兩個模型各跑一次，記錄耗時和 token 數，方便決定 profile 要用哪個模型。

```powershell
uv run tools/compare_models.py "https://youtu.be/<影片ID>" --mode summary --start 0 --end 300
```

- 沒加 `--yes-use-quota` 時只印出會做什麼（dry-run：不讀 key、不連網路）；加上才會真的呼叫，**每個模型各用掉 1 次請求**（快速回 503 觸發自動重試時是 2 次）
- 模型只能選 `config.toml` 裡有的；沒指定時比較每個 profile 的主要模型
- 結果寫進 `logs\compare-<時間>-<隨機碼>\`（不會進 git）：每個模型一個 `.md`（Gemini 的輸出，包在不可信標記裡）、`summary.json`（耗時、token 數）和 `run.log`；log 只寫進 `run.log`，不印到終端機
- key 只從安全儲存區讀，不會印出或寫進檔案

---

## 疑難排解

| 訊息 | 處理方式 |
|---|---|
| 找不到 Gemini API key，請先執行 set_key.py | 在專案資料夾執行 `uv run set_key.py` |
| Gemini API 額度已用完（429） | 稍後再試；free tier 每天最多 8 小時 YouTube 影片 |
| 今日額度已用完／今日額度都已用完 | 等每日重置；重開 Claude 會清掉記錄，但額度沒恢復前仍會失敗 |
| 每分鐘最多分析 N 次／24 小時內最多分析 N 次／同時進行的影片分析已達上限 | 呼叫上限，等訊息裡寫的時間再試；需要的話調整 `config.toml` 的 `[limits]` |
| Gemini 拒絕了這次請求（HTTP …）。詳細原因已記錄在 server 的 log | 原始錯誤訊息只寫在 log（stderr），不放進回覆 |
| config.toml：temperature 已不再使用 | 從 `config.toml` 刪掉 `temperature` 那一行 |
| Gemini 無法讀取這支影片 | 只支援公開影片，私人、不公開、有年齡／地區限制的都不行 |
| 影片太長 | 用 `start` / `end` 分段，或保持 `detail="low"` |
| 找不到模型 | `config.toml` 的模型 ID 可能已下架，到 [Gemini 定價頁](https://ai.google.dev/gemini-api/docs/pricing) 查目前的 ID |
| Claude Desktop 看不到工具 | `command` 改用 uv 的完整路徑，並完全重開 Claude Desktop |
| 網頁版／手機呼叫時「80 秒內沒有回應」 | 確認 Claude Desktop 設定用的是 `--profile chat`；改過程式或設定後要完全重開 Claude Desktop |
| Gemini 模型暫時過載（HTTP 503） | Google 那邊這個模型容量不足，約 1 分鐘後再試；server 已經自動重試過 1 次（時間夠的話） |
| Gemini 處理這支影片超過 Google 端的時間上限（HTTP 504） | 用 `start` / `end` 縮短範圍，保持 `detail="low"` |
| Gemini 在 N 秒內沒有回應，本機已停止等待 | server 自己的時間上限到了。chat 入口可以再試一次，或改用 Claude Code（code，時間上限較長）；長影片分段 |
| config.toml 沒有 profile「…」 | `--profile` 的名稱要和 `config.toml` 的 `[profiles.<名稱>]` 一致 |
| 輸出達到長度上限而被截斷 | 用 `start` / `end` 分段，或調高 `max_output_tokens` |

## 已知限制

- 支援 Windows 與 macOS。**macOS 是實驗性支援**：CI 會在 macOS 跑單元測試，但還沒在真的 Mac 上驗證 Keychain，歡迎回報結果。Linux 尚不支援（沒有固定的安全儲存區，server 也不會退回存成明文檔案）。
- 只支援公開影片，一次分析一支；輸出語言只有繁體中文與英文。`config.toml` 本身的錯誤訊息固定是中文（讀到語言設定之前就可能出錯）。
- 主要模型逾時被中止時，Google 那邊可能仍在處理，仍可能計入額度。
- `gemini-3.5-flash-lite`（Chat 的主要模型、Code 的備援）速度快，但分析深度比 `gemini-3.8-flash` 淺。
- `gemini-3.8-flash` 是 preview 模型，常常過載（503／504）；這時 code 會改用 flash-lite。
- chat 沒有備援模型（70 秒內來不及）。偶爾遇到 503 屬於預期，server 會自動重試 1 次；還是失敗就再問一次。
- 有開發者回報：對 YouTube 網址用 `start`/`end` 時，音訊可能仍以整支影片計算 token。

## 授權

[MIT](LICENSE)。本專案與 Google、YouTube、Anthropic 沒有關係，也沒有經過它們背書。使用 Gemini API 時請遵守 [Gemini API 使用條款](https://ai.google.dev/gemini-api/terms)。
