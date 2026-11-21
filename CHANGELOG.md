# CHANGELOG

本資料夾內有版本行的文件與設定檔，每次修改都在這裡記一筆（新的在上面）。
程式本身的版本（SemVer）寫在 `pyproject.toml`。

Changes to versioned documents and config files (newest first, in Traditional Chinese). The program version (SemVer) is in `pyproject.toml`.

| 日期 | 文件 | 版本 | 改了什麼 | 為什麼 |
|---|---|---|---|---|
| 2026-11-22 | SPEC.md | v10.1 | 更正例子：Chat 與 Code 分頁實測都會跳出轉錄稿按鈕，「沒有按鈕」不再舉 Chat 為例 | 使用者實測 v0.8.1，Chat 也有按鈕；行為不變 |
| 2026-11-22 | README.md | v8.1 | 同上 | 同上 |
| 2026-11-22 | README.zh-TW.md | v8.1 | 同上 | 同上 |
| 2026-11-22 | SPEC.md | v10.0 | 轉錄稿詢問：Claude 有可點選的選項工具時才用按鈕問；沒有就不用文字問，直接帶 `skip_transcript=true` 分析，結尾附提示 | 使用者實測 v9.0 在 Chat 被用文字問、要打字回答，太不方便；希望有按鈕才問、沒有就直接分析 |
| 2026-11-22 | README.md | v8.0 | 轉錄稿段落改成：有按鈕才問，沒有就直接分析並附提示 | 配合 SPEC v10.0 |
| 2026-11-22 | README.zh-TW.md | v8.0 | 同上 | 配合 SPEC v10.0 |
| 2026-11-22 | SPEC.md | v9.0 | 轉錄稿詢問改由 server 強制：每支影片第一次沒附轉錄稿時不呼叫 Gemini，回固定說明請 Claude 詢問使用者；新增 `skip_transcript` 參數與 `ask_for_transcript` 設定；同一支影片只攔一次、記錄上限 500 支；沒附轉錄稿時結尾加提示；要求 Claude 原樣附上結尾的模型與版本 | 只寫在說明裡時 Claude 常常不問（使用者在新 session 實際遇到）；Claude 重寫回覆時會省略版本行，使用者看不到用的是哪一版 |
| 2026-11-22 | config.toml | v6.0 | 新增 `[gemini] ask_for_transcript = true` | 配合 SPEC v9.0 |
| 2026-11-22 | README.md | v7.0 | 轉錄稿段落改成 server 會先問；`skip_transcript` 參數；`ask_for_transcript` 設定；結尾版本行看不到時展開工具呼叫 | 配合 SPEC v9.0 |
| 2026-11-22 | README.zh-TW.md | v7.0 | 同上 | 配合 SPEC v9.0 |
| 2026-11-22 | SPEC.md | v8.0 | 輸出語言可設定（`output_language`：zh-TW／en），Gemini 回答與 server 回給 Claude 的訊息都切換；給 Claude 讀的工具說明、參數說明、server instructions 改英文；key 儲存支援 macOS Keychain（實驗性），依平台固定後端，其他平台拒絕；CI 加 macOS | 讓國際使用者不用改程式就能使用；英文是 MCP 生態的共通語言；涵蓋使用 Claude Code 的 Mac 使用者 |
| 2026-11-22 | config.toml | v5.0 | 新增 `[gemini] output_language = "zh-TW"`；註解補上 macOS Keychain | 配合 SPEC v8.0 |
| 2026-11-22 | README.md | v6.0 | 輸出語言設定；macOS 安裝（Homebrew）、Claude Desktop 路徑、Keychain 允許提示；Limitations 改成 macOS 實驗性、Linux 不支援、config 錯誤訊息為中文 | 配合 SPEC v8.0 |
| 2026-11-22 | README.zh-TW.md | v6.0 | 同上 | 配合 SPEC v8.0 |
| 2026-11-22 | .github/workflows/test.yml | v1.2 | 用 matrix 同時在 windows-latest 與 macos-latest 跑單元測試（fail-fast: false） | 驗證 macOS 支援 |
| 2026-11-21 | .github/workflows/test.yml | v1.1 | `actions/checkout` v4 → v7.0.1、`actions/setup-python` v5 → v7.1.0，都改成鎖定 commit SHA；加上版本行 | CI 提醒舊版用的 Node.js 20 已淘汰；SHA 鎖定避免 tag 被移動後執行到不同的程式碼 |
| 2026-11-21 | SPEC.md | v7.0 | 新增選填的 `transcript`（使用者自己從 YouTube 複製，最長 120,000 字元，清除看不見與控制字元）；轉錄稿包進帶隨機 id 的 `<transcript_reference>` 放在獨立 part；system instruction 規定轉錄稿只是參考資料；工具說明要求 Claude 沒有轉錄稿時先詢問一次；範圍外加上「不自動抓轉錄稿」與原因；結尾標示有沒有附轉錄稿 | 使用者希望提高拼法與原話的準確度；自動抓取違反 YouTube 條款且需連 YouTube；MCP elicitation 只有 Claude Code 終端機版支援，所以改由 Claude 在對話中詢問 |
| 2026-11-21 | README.md | v5.0 | 新增「Adding a transcript」：取得步驟、用途、為什麼不自動抓、安全處理、長度與隱私提醒；參數表加 `transcript` | 配合 SPEC v7.0 |
| 2026-11-21 | README.zh-TW.md | v5.0 | 新增「附上轉錄稿」，內容同上 | 配合 SPEC v7.0 |
| 2026-11-21 | SPEC.md | v6.0 | 新增 503 短重試（5 秒內回 503、剩餘時間至少 20 秒時，對同一模型等 1.5 秒再試 1 次）；錯誤分類（503 過載／504 Google 端逾時／本機逾時）與對應建議；交付內容加上 opt-in 的 `tools/compare_models.py` | 實測 chat（沒有備援）一次 503 就整個失敗，flash-lite 3 次中 1 次回 503；原本所有 5xx 都同一句話，使用者不知道該重試、分段還是換入口 |
| 2026-11-21 | README.md | v4.1 | 新增「Choosing a profile」白話對照表；回覆最後一行的重試說明與錯誤類型表；模型對照工具；Limitations 補上 3.8-flash 是 preview、chat 沒有備援 | 配合 SPEC v6.0 |
| 2026-11-21 | README.zh-TW.md | v4.1 | 同上：怎麼選 profile、重試與錯誤分類、模型對照工具、疑難排解與已知限制 | 配合 SPEC v6.0 |
| 2026-11-21 | README.md | v4.0 | 改成英文主文件：git clone 安裝、需求、設定、模式、回覆最後一行怎麼看、free tier、開發、限制、授權 | 公開到 GitHub，讓其他人用自己的 key 安裝 |
| 2026-11-21 | README.zh-TW.md | v4.0 | 新增繁中版（由 README v3.1 改寫）：git clone 安裝、移除本機路徑、加上授權與回報漏洞方式 | 同上 |
| 2026-11-21 | SPEC.md | v5.1 | 專案位置改成通用說明；交付內容加上公開文件，開發筆記改放本機 `notes/` | 公開前移除個人路徑 |
| 2026-11-21 | .gitignore | v1.1 | 加上 `notes/` | 進度、交接等開發筆記只留在本機 |
| 2026-11-21 | SPEC.md | v5.0 | 新增呼叫上限（`[limits]`）；不可信標記加隨機 id、中和全形與看不見字元；tutorial 結尾加人工審查提醒；上游錯誤原文不回傳；回覆結尾標示模型角色（主要／備援）、使用入口、程式版本；`set_key.py --check` 檢查所有模型（中間的 v4.1 未 commit，併入本版） | 獨立資安審查：缺速率限制（違反全域 §7）、標記可被全形／零寬字元繞過、上游錯誤文字在標記外；使用者看到 Chat 一直用 flash-lite，無法分辨原因 |
| 2026-11-21 | config.toml | v4.0 | 新增 `[limits]`：`max_concurrent = 2`、`max_calls_per_minute = 5`、`max_calls_per_day = 100` | 依 SPEC v5.0 |
| 2026-11-21 | README.md | v3.1 | 說明回覆最後一行怎麼看、呼叫上限、`--check` 檢查所有模型、不可信標記的 id | 配合 SPEC v5.0 |
| 2026-11-20 | README.md | v3.0 | 各 profile 的模型與思考強度表、free tier 限制、每日額度跳過、token 用量 log、疑難排解新增三項；修正「在哪裡可以用」表格重複的表頭 | 配合 SPEC v4.0 |
| 2026-11-20 | config.toml | v3.0 | `model`、`fallback_models` 移到各 `[profiles.*]`，新增 `thinking_level`；chat 改用 `gemini-3.5-flash-lite`（low、無備援），code 用 `gemini-3.8-flash`（medium、備援 flash-lite）；移除 `temperature` | 依 SPEC v4.0；chat 不設備援是因為 3.8-flash 在 70 秒內通常跑不完，還會用掉每日約 20 次的額度 |
| 2026-11-20 | SPEC.md | v4.0 | 模型順序與 thinking_level 改成每個 profile 各自設定（chat 以 flash-lite 為主、low；code 以 3.8-flash 為主、medium）；移除 temperature；每日額度用完的模型當天跳過；token 用量寫進 log；新增 free tier 限制表 | 3.8-flash 常過載、free tier 每日次數少，chat 的 80 秒限制下大多靠備援；官方已棄用 temperature；依外部整理的參考資料並對照官方文件 |
| 2026-11-20 | SPEC.md | v3.0 | 新增 `mode` 參數（summary／notes／tutorial／quotes／claims）；時間上限改成依使用入口的 profile（chat 70 秒、code 240 秒）；加入準確度規則；說明不提供逐字稿模式的原因 | 備援模型常被觸發導致分析偏淺；不同影片需要不同輸出（教學影片要可照做的步驟） |
| 2026-11-20 | config.toml | v2.0 | `timeout_seconds`、`attempt_timeout_seconds` 從 `[gemini]` 移到 `[profiles.chat]`／`[profiles.code]`；`max_output_tokens` 8192 → 16384 | Code 沒有 80 秒限制，可以給主要模型更多時間；notes、tutorial 輸出較長 |
| 2026-11-20 | README.md | v2.0 | 分析模式、profile、註冊指令加 `--profile`、取得較好結果的方法、把教學影片整理成 skill 的流程 | 配合 SPEC v3.0 |
| 2026-11-20 | SPEC.md | v2.0 | 總時間上限從「例如 180 秒」改為預設 70 秒（含備援）；新增備援模型需求、關閉 SDK 自動重試；補上威脅分析、外部服務與資料流向、範圍外 | Claude 網頁版／手機經桌機呼叫本機 MCP 約 80 秒就放棄；`gemini-3.8-flash` 過載時要 137–184 秒。威脅分析等段落依全域規則第 2 節與範本補齊 |
| 2026-11-20 | config.toml | v1.1 | `timeout_seconds` 180 → 70；新增 `fallback_models = ["gemini-3.5-flash-lite"]`、`attempt_timeout_seconds = 35` | 同上，確保 80 秒內一定有回應 |
| 2026-11-20 | .gitignore | v1.0 | 以全域範本 gitignore v1.0 為基礎，加上本專案規則（`secrets.*`、`client_secret*.json` 等） | 全域規則第 4 節：第一次 commit 前建好 `.gitignore` |
| 2026-11-20 | README.md | v1.0 | 初版：安裝、key 設定、註冊、使用入口、模型與備援、測試、元件清單、疑難排解 | 交付文件 |
| 2026-11-20 | config.toml | v1.0 | 初版：`gemini-3.8-flash`、timeout 180 秒 | 依 SPEC：模型 ID 不寫死在程式裡 |
| 2026-11-20 | SPEC.md | v1.2 | 專案路徑改為本機的專案資料夾；加上風險等級 L1、程式版本起點 v0.1.0（使用者修改） | 與實際專案位置一致 |
| 2026-11-20 | SPEC.md | v1.0–v1.1 | 初版規格 | v1.1 的內容在建立 CHANGELOG 前，未留紀錄 |
