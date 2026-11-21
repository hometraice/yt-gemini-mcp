"""開發用：同一支影片、同一個 mode，對最多兩個模型各跑一次，比較耗時、token 數與結果。

⚠️ 加上 --yes-use-quota 才會真的呼叫 Gemini，每個模型各用掉 1 次請求（遇到快速的 503 可能再重試 1 次）。
沒加時只印出會做什麼（dry-run），不讀 key、不連網路。

用法（在專案資料夾執行）：
    uv run tools/compare_models.py <YouTube 網址>                      dry-run，看會比較哪些模型
    uv run tools/compare_models.py <網址> --mode quotes --start 0 --end 300 --yes-use-quota
    uv run tools/compare_models.py <網址> --models gemini-3.5-flash-lite gemini-3.8-flash --yes-use-quota

- 模型只能選 config.toml 裡出現過的；沒指定時比較每個 profile 的主要模型。
- 每個模型用「它是主要模型的那個 profile」的思考強度與時間上限（可用 --profile 統一指定），不使用備援。
- 結果寫進 logs/compare-<時間>-<隨機碼>/：每個模型一個 .md（Gemini 的輸出，包在帶隨機 id 的不可信標記裡）、
  summary.json（耗時、token 數、成功與否、錯誤分類），以及 run.log（執行 log）。
  終端機只印統計數字；log 不印到終端機，避免上游錯誤原文跑進 Claude 的對話。key 只從 keyring 讀，不會印出或寫進檔案。
- 這支工具不受 server 的呼叫上限管制，所以一次最多比較 2 個模型。
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import dataclasses
import json
import logging
import secrets
import sys
import time
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from yt_gemini import gemini, validation  # noqa: E402
from yt_gemini.config import CONFIG_PATH, ConfigError, Settings, load_settings, profile_names  # noqa: E402
from yt_gemini.messages import t  # noqa: E402
from yt_gemini.redaction import RedactingFormatter, redact  # noqa: E402
from yt_gemini.untrusted import wrap_untrusted  # noqa: E402

MAX_MODELS = 2
LOGS_DIR = PROJECT_ROOT / "logs"


@dataclasses.dataclass(frozen=True)
class Job:
    model: str
    settings: Settings  # 只含這一個模型，沒有備援


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="比較兩個 Gemini 模型分析同一支影片的耗時、token 數與結果（預設 dry-run，不消耗額度）。"
    )
    parser.add_argument("url", help="公開的 YouTube 網址")
    parser.add_argument("--models", nargs="+", metavar="MODEL",
                        help=f"要比較的模型（最多 {MAX_MODELS} 個，必須出現在 config.toml）；預設為各 profile 的主要模型")
    parser.add_argument("--mode", default="summary", help="分析模式（預設 summary）")
    parser.add_argument("--question", help="要問的問題或想聚焦的範圍")
    parser.add_argument("--start", type=int, help="開始秒數")
    parser.add_argument("--end", type=int, help="結束秒數")
    parser.add_argument("--detail", default="low", help="low（預設）或 default")
    parser.add_argument("--profile", help="所有模型都用這個 profile 的思考強度與時間上限")
    parser.add_argument("--yes-use-quota", action="store_true",
                        help="確認要實際呼叫 Gemini（會消耗額度）；沒加時只做 dry-run")
    return parser


def plan_jobs(models: list[str] | None, profile: str | None, config_path: Path = CONFIG_PATH,
              language: str = "zh-TW") -> list[Job]:
    """決定要比較哪些模型、各用什麼設定。模型不在 config.toml 裡就拒絕（ValueError）。"""
    all_settings = [load_settings(config_path, name) for name in profile_names(config_path)]
    # 每個模型對應到「它是主要模型」的 profile；只當備援的模型，對應到第一個用到它的 profile。
    owner: dict[str, Settings] = {}
    for settings in all_settings:
        owner.setdefault(settings.model, settings)
    for settings in all_settings:
        for model in settings.fallback_models:
            owner.setdefault(model, settings)

    if models:
        chosen = list(dict.fromkeys(models))  # 去除重複、保留順序
    else:
        chosen = list(dict.fromkeys(s.model for s in all_settings))
    if len(chosen) > MAX_MODELS:
        raise ValueError(t(language, "cm_too_many", limit=MAX_MODELS, count=len(chosen)))
    unknown = [m for m in chosen if m not in owner]
    if unknown:
        sep = t(language, "list_sep")
        raise ValueError(t(language, "cm_unknown_model", models=sep.join(unknown), allowed=sep.join(sorted(owner))))

    forced = load_settings(config_path, profile) if profile else None
    jobs = []
    for model in chosen:
        base = forced or owner[model]
        jobs.append(Job(model, dataclasses.replace(base, model=model, fallback_models=())))
    return jobs


def describe(job: Job, language: str = "zh-TW") -> str:
    s = job.settings
    return t(language, "cm_job", model=job.model, profile=s.profile, thinking=s.thinking_level or "default",
             timeout=s.timeout_seconds)


async def run_jobs(jobs: list[Job], video: validation.VideoRef, *, mode: str, question: str | None,
                   start: int | None, end: int | None, detail: str, out_dir: Path,
                   analyze=None) -> list[dict]:
    """依序呼叫每個模型，把結果寫進 out_dir（必須已存在）。analyze 可替換（測試用）。"""
    analyze = analyze or gemini.analyze_video
    lang = jobs[0].settings.language if jobs else "zh-TW"
    rows: list[dict] = []
    for job in jobs:
        started = time.monotonic()
        row: dict = {"model": job.model, "profile": job.settings.profile,
                     "thinking_level": job.settings.thinking_level, "timeout_seconds": job.settings.timeout_seconds}
        try:
            result = await analyze(video, question=question, start=start, end=end, detail=detail,
                                   settings=job.settings, mode=mode)
        except gemini.AnalysisError as exc:
            # AnalysisError 的訊息是我們自己產生的固定說明，不含上游原文；保險起見再遮罩一次。
            row.update(ok=False, error_kind=exc.kind or "unknown", error=redact(str(exc)), usage={}, note="")
            body = t(lang, "cm_failed_body", message=redact(str(exc)))
        else:
            row.update(ok=True, error_kind="", error="", usage=dict(result.usage), note=result.fallback_note)
            # 和 server 一樣：遮罩後包進帶隨機 id 的不可信標記，之後請 Claude 讀這些檔案時才不會被影片內容誘導。
            body = wrap_untrusted(video.video_id, redact(result.text), language=lang)
        row["elapsed_seconds"] = round(time.monotonic() - started, 1)

        result_file = out_dir / f"{job.model}.md"
        header = (f"<!-- model={job.model} profile={job.settings.profile} "
                  f"thinking={job.settings.thinking_level or 'default'} elapsed={row['elapsed_seconds']}s "
                  f"usage={json.dumps(row['usage'])} -->\n"
                  + t(lang, "cm_untrusted_header") + "\n\n")
        result_file.write_text(header + body + "\n", encoding="utf-8")
        row["result_file"] = result_file.name
        rows.append(row)

        usage = row["usage"]
        tokens = (f"prompt={usage.get('prompt', 0)} output={usage.get('output', 0)} "
                  f"thoughts={usage.get('thoughts', 0)} total={usage.get('total', 0)}") if usage else "tokens=-"
        key = "cm_row_ok" if row["ok"] else "cm_row_failed"
        print(t(lang, key, kind=row["error_kind"], model=job.model, seconds=row["elapsed_seconds"], tokens=tokens,
                file=result_file.name), flush=True)

    summary = {
        "video_id": video.video_id,
        "mode": mode,
        "start": start,
        "end": end,
        "detail": detail,
        "question_given": question is not None,  # 不記問題內容
        "results": rows,
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return rows


@contextlib.contextmanager
def _log_to_file(path: Path):
    """執行期間的 log 只寫進檔案（遮罩過），不印到終端機；結束後恢復原本的 logging 設定。"""
    handler = logging.FileHandler(path, encoding="utf-8")
    handler.setFormatter(RedactingFormatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    root = logging.getLogger()
    saved_handlers, saved_level = root.handlers[:], root.level
    quiet = ("httpx", "httpcore", "google_genai", "google.genai", "urllib3")
    saved_quiet = {name: logging.getLogger(name).level for name in quiet}
    root.handlers[:] = [handler]
    root.setLevel(logging.INFO)
    # 和 server 一樣：HTTP 層的 log 可能印出 request 細節，壓到 WARNING。
    for name in quiet:
        logging.getLogger(name).setLevel(logging.WARNING)
    try:
        yield
    finally:
        root.handlers[:] = saved_handlers
        root.setLevel(saved_level)
        for name, level in saved_quiet.items():
            logging.getLogger(name).setLevel(level)
        handler.close()


def main(argv: list[str] | None = None, *, logs_dir: Path = LOGS_DIR, analyze=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        lang = load_settings().language
    except ConfigError:
        lang = "zh-TW"
    try:
        video = validation.parse_youtube_url(args.url)
        mode = validation.validate_mode(args.mode)
        question = validation.validate_question(args.question)
        start, end = validation.validate_time_range(args.start, args.end)
        detail = validation.validate_detail(args.detail)
        jobs = plan_jobs(args.models, args.profile, language=lang)
    except validation.ValidationError as exc:
        print(t(lang, "cli_error", message=exc.render(lang)), file=sys.stderr)
        return 2
    except (ConfigError, ValueError) as exc:
        print(t(lang, "cli_error", message=redact(str(exc))), file=sys.stderr)
        return 2

    print(t(lang, "cm_plan", url=video.canonical_url, mode=mode, start=start, end=end, detail=detail))
    for job in jobs:
        print(describe(job, lang))
    if not args.yes_use_quota:
        print(t(lang, "cm_dry_run", count=len(jobs)))
        return 0

    # 加隨機碼：同一秒執行兩次也不會撞名；exist_ok=False 確保絕不覆寫舊結果。
    out_dir = logs_dir / f"compare-{datetime.now():%Y%m%d-%H%M%S}-{secrets.token_hex(3)}"
    out_dir.mkdir(parents=True, exist_ok=False)
    with _log_to_file(out_dir / "run.log"):
        rows = asyncio.run(run_jobs(jobs, video, mode=mode, question=question, start=start, end=end,
                                    detail=detail, out_dir=out_dir, analyze=analyze))
    print(t(lang, "cm_done", path=out_dir))
    return 0 if all(row["ok"] for row in rows) else 1


if __name__ == "__main__":
    # 輸出被導向（pipe、Git Bash）時 Windows 預設用系統 codepage，中文會變亂碼；統一用 UTF-8。
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
