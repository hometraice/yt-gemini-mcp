# CHANGELOG

本資料夾內有版本行的文件與設定檔，每次修改都在這裡記一筆（新的在上面）。
程式本身的版本（SemVer）寫在 `pyproject.toml`。

Changes to versioned documents and config files (newest first, in Traditional Chinese). The program version (SemVer) is in `pyproject.toml`.

| 日期 | 文件 | 版本 | 改了什麼 | 為什麼 |
|---|---|---|---|---|
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
