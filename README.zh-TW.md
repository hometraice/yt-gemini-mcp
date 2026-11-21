> Version: v4.0 | 2026-11-21 | 公開版：用 git clone 安裝、移除本機路徑、補上授權與回報漏洞方式

# yt-gemini-mcp

[English](README.md) | 繁體中文

讓 Claude（Claude Code／Claude Desktop）透過 Google Gemini API「觀看」公開的 YouTube 影片：摘要、詳細筆記、教學步驟、重要原話、主張整理、問答、指定片段分析。

- 本機 stdio MCP server，**不開任何網路 port**
- 只有一個工具 `analyze_youtube`，沒有寫檔、shell、任意 HTTP request
- API key 只存在 **Windows Credential Manager**，不在任何檔案、環境變數或 Claude 設定裡
- 每個人用**自己的** Gemini API key（Google AI Studio 可免費申請）
- 目前**只支援 Windows**；分析結果固定用**繁體中文**輸出

---

## 資安設計

| 風險 | 對策 |
|---|---|
| API key 外洩 | key 只存在 Windows Credential Manager（`keyring`，service=`yt-gemini-mcp`、user=`gemini`），程式固定使用 WinVault 後端。不讀 `.env`、不讀環境變數。`config.toml` 若出現疑似 key，server 拒絕啟動 |
| key 留在畫面或 history | `set_key.py` 用 `getpass` 隱藏輸入；不接受命令列參數或 pipe；終端機無法隱藏輸入時直接中止 |
| key 出現在 log／錯誤訊息 | 所有 log 走 stderr 並經過遮罩（`AIza…`、`?key=`、`x-goog-api-key`、實際使用中的 key），錯誤訊息只回傳固定的中文說明，不吐 stack trace |
| SSRF／濫用 | 只接受 `youtube.com/watch?v=`、`youtu.be/`、`youtube.com/shorts/`、`m.youtube.com/watch?v=`；host 白名單完全比對；ID 必須是 11 碼；一律用 ID 重組 `https://www.youtube.com/watch?v=<ID>` 再送出 |
| Prompt injection | system instruction 規定影片內的指令只能轉述、不可執行；回傳結果包在 `<untrusted_video_analysis>` 裡，開始與結束標記帶每次隨機產生的 id（影片內容無法偽造結尾），並中和內容裡偽造的標記（含全形與看不見的字元）；tutorial 模式在結尾提醒「執行前必須人工審查」；Gemini 的原始錯誤訊息不放進回覆 |
| 供應鏈 | 只有 `mcp`、`google-genai`、`keyring` 三個直接相依，版本用 `==` 固定、`uv.lock` 鎖定，啟動時用 `--locked`；`exclude-newer` 排除剛發布的版本 |
| 額度／資源 | 整次呼叫有總時間上限（Chat 70 秒、Code 240 秒，含備援）；關閉 SDK 自動重試，改成主要模型失敗時換備援模型（最多 3 個）；每日額度用完的模型當天直接跳過；呼叫上限（同時 2 個、每分鐘 5 次、24 小時 100 次，超過就拒絕）；預設低 media resolution；token 用量寫進 log（只有數字） |

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
│   ├── keystore.py       Windows Credential Manager 存取
│   ├── redaction.py      機密遮罩（log、錯誤訊息）
│   ├── validation.py     URL 與參數驗證
│   ├── gemini.py         呼叫 Gemini、備援、錯誤轉換、token 用量 log
│   ├── quota.py          每日額度用完的模型（只存在記憶體）
│   ├── ratelimit.py      呼叫上限：同時進行數、每分鐘、每 24 小時
│   └── untrusted.py      不可信資料標記
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
| [`keyring`](https://pypi.org/project/keyring/) | 25.7.0 | MIT | 讀寫 Windows Credential Manager |

**外部服務**

| 服務 | 送出的資料 | 備註 |
|---|---|---|
| Google Gemini API | 影片標準網址、問題、system instruction；key 放在 HTTP header | free tier 的內容可能被 Google 用來改進產品 |
| YouTube | 本機不直接連線，由 Gemini 讀取公開影片 | — |
| Anthropic（Claude） | 分析結果會出現在 Claude 對話裡 | 依你使用的 Claude 產品，對話可能存於 Anthropic |

---

## 安裝

需求：Windows 10/11、Git、一般使用者權限（不需要系統管理員）。

**1. 安裝 uv**（不用另外裝 Python，uv 會管理）

```powershell
winget install --id=astral-sh.uv -e --source winget
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

以下用 `<專案資料夾>` 代表剛剛 clone 下來的資料夾完整路徑，例如 `C:\Users\<你的帳號>\yt-gemini-mcp`。

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

**建議再加兩道保護**（在 Google 那一端）：

1. 到 [Google Cloud Console → API 和服務 → 憑證](https://console.cloud.google.com/apis/credentials) 編輯這把 key，**API 限制**只勾 `Generative Language API`。這樣即使 key 外洩，也不能拿去呼叫別的 Google API。
2. 懷疑外洩時，到 [Google AI Studio](https://aistudio.google.com/apikey) 立刻刪除舊 key、建立新 key，再執行 `uv run set_key.py`。

---

## 註冊到 Claude Code

在 Git Bash 執行（PowerShell 5.1 處理 `--` 參數的方式不同，所以用 Git Bash）：

```bash
claude mcp add yt-gemini --scope user -- uv --directory '<專案資料夾>' run --locked server.py --profile code
```

`--scope user` 代表所有專案都能用。`--profile code` 讓 Claude Code 使用分析較深的 `gemini-3.8-flash` 和較長的時間上限（240 秒）。注意指令裡**沒有任何 key**，server 啟動時會自己去 Credential Manager 讀取。

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

2. 在 Claude Desktop 開啟 **設定 → Developer → Edit Config**，編輯 `claude_desktop_config.json`，加入以下內容（換成你的路徑，反斜線要寫兩次）：

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

**分析模式**

| `mode` | 適合 | 輸出 |
|---|---|---|
| `summary` | 先了解影片在講什麼 | 結構化摘要 |
| `notes` | 想掌握幾乎所有內容 | 依時間分段（每段 1–3 分鐘）的詳細筆記 |
| `tutorial` | 教學、實作影片 | 可照做的步驟；畫面上的指令、程式碼、提示詞逐字抄進 code block；列出需要對照官方文件的地方 |
| `quotes` | 需要引用講者的話 | 5–15 句重要原話與時間戳 |
| `claims` | 想查證影片的說法 | 影片中的事實性主張、講者給的證據、查證優先度 |

回答一律是繁體中文，附 `[mm:ss]` 時間戳，區分【畫面】與【語音】，不確定的地方會標明。人名、指令、程式碼這類內容畫面有出現就逐字抄寫，拼法沒把握會標「（拼法不確定）」。

**怎麼得到比較好的結果**

- 先用 `summary` 了解全貌，再針對重要段落用 `start` / `end` 深入（Claude 會照工具說明自動這樣做）。
- 長影片或 `notes`、`tutorial` 這類長輸出：分段，每段 5–10 分鐘。
- 畫面上有程式碼、指令、小字：加 `detail="default"`。
- 回覆最後一行會寫出模型和它的角色，例如「模型：gemini-3.5-flash-lite，chat 入口的主要模型」：
  - **chat 入口的主要模型**：Chat、網頁版、手機因為約 80 秒的限制，本來就用速度快的 flash-lite，不是額度或錯誤造成的。要更深入的分析，請改用 Claude Code
  - **備援模型**：主要模型失敗了，下一行會寫原因（逾時、HTTP 錯誤碼或今日額度已用完）
  - 最後的 `yt-gemini-mcp v…` 是目前載入的程式版本；更新後還看到舊版號，代表要完全重開 Claude Desktop
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

- `model`、`fallback_models`：主要模型逾時、過載（5xx）或額度用完（429）時，依序改用備援模型（最多 3 個）
- `thinking_level`：`low`／`medium`／`high`。越高越深入，但越慢、用量越多
- `timeout_seconds`：整次呼叫的總上限；`attempt_timeout_seconds`：主要模型最多等幾秒就換備援
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
| Gemini 在 N 秒內沒有回應 | 主要與備援模型都過載，稍後再試；長影片用 `start` / `end` 分段 |
| config.toml 沒有 profile「…」 | `--profile` 的名稱要和 `config.toml` 的 `[profiles.<名稱>]` 一致 |
| 輸出達到長度上限而被截斷 | 用 `start` / `end` 分段，或調高 `max_output_tokens` |

## 已知限制

- 只支援 Windows；只支援公開影片，一次分析一支；輸出固定是繁體中文。
- 主要模型逾時被中止時，Google 那邊可能仍在處理，仍可能計入額度。
- `gemini-3.5-flash-lite`（Chat 的主要模型、Code 的備援）速度快，但分析深度比 `gemini-3.8-flash` 淺。
- 有開發者回報：對 YouTube 網址用 `start`/`end` 時，音訊可能仍以整支影片計算 token。

## 授權

[MIT](LICENSE)。本專案與 Google、YouTube、Anthropic 沒有關係，也沒有經過它們背書。使用 Gemini API 時請遵守 [Gemini API 使用條款](https://ai.google.dev/gemini-api/terms)。
