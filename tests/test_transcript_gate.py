"""轉錄稿詢問關卡：第一次分析某支影片、沒附轉錄稿時，先請 Claude 問使用者（不呼叫 Gemini、不耗額度）。"""

import asyncio
import re
import tempfile
import unittest
from collections import OrderedDict
from pathlib import Path
from unittest import mock

import server
from yt_gemini import config, gemini, ratelimit
from yt_gemini.config import Settings

URL = "youtu.be/dQw4w9WgXcQ"
CJK = re.compile(r"[　-〿㐀-鿿＀-￯]")


def settings(ask=True, language="zh-TW"):
    return Settings(model="m-main", timeout_seconds=30, max_output_tokens=1024, ask_for_transcript=ask,
                    language=language)


class TestTranscriptGate(unittest.TestCase):
    def setUp(self):
        self.limiter = ratelimit.CallLimiter()
        self.settings = settings()
        for patcher in (mock.patch.object(ratelimit, "limiter", self.limiter),
                        mock.patch.object(server, "_asked_videos", OrderedDict()),
                        mock.patch.object(server, "load_settings", side_effect=lambda **kw: self.settings)):
            patcher.start()
            self.addCleanup(patcher.stop)
        self.analyze = mock.patch.object(gemini, "analyze_video", side_effect=self._fake_analyze)
        self.analyze_mock = self.analyze.start()
        self.addCleanup(self.analyze.stop)

    async def _fake_analyze(self, video, **kw):
        return gemini.AnalysisResult(text="analysis", model="m-main")

    def call(self, **kwargs):
        return asyncio.run(server.analyze_youtube(url=kwargs.pop("url", URL), **kwargs))

    def test_first_call_without_transcript_asks_and_skips_gemini(self):
        out = self.call()
        self.assertEqual(out, server.TRANSCRIPT_PROMPT)
        self.analyze_mock.assert_not_called()
        self.assertIn("Show transcript", out)
        self.assertIn("skip_transcript=true", out)
        self.assertIn("did not call Gemini", out)
        self.assertNotIn("dQw4w9WgXcQ", out)  # 固定文字，不含影片或使用者內容

    def test_gate_does_not_use_call_limit(self):
        for i in range(10):
            self.call(url=f"youtu.be/aaaaaaaaa{i:02d}")
        self.assertEqual(len(self.limiter._recent), 0)

    def test_second_call_for_same_video_always_analyzes(self):
        self.call()
        out = self.call()
        self.assertIn("analysis", out)
        self.analyze_mock.assert_called_once()

    def test_skip_transcript_analyzes_immediately(self):
        out = self.call(skip_transcript=True)
        self.assertIn("analysis", out)
        self.assertIn("轉錄稿：無", out)
        self.assertIn("附上 YouTube 轉錄稿", out)  # 沒附轉錄稿時的結尾提示

    def test_transcript_analyzes_immediately_without_hint(self):
        out = self.call(transcript="0:00\nhello")
        self.assertIn("analysis", out)
        self.assertNotIn("附上 YouTube 轉錄稿", out)

    def test_disabled_in_config(self):
        self.settings = settings(ask=False)
        out = self.call()
        self.assertIn("analysis", out)

    def test_each_video_asked_once(self):
        first = self.call(url="youtu.be/aaaaaaaaaaa")
        other = self.call(url="youtu.be/bbbbbbbbbbb")
        self.assertEqual(first, server.TRANSCRIPT_PROMPT)
        self.assertEqual(other, server.TRANSCRIPT_PROMPT)
        self.assertIn("analysis", self.call(url="youtu.be/aaaaaaaaaaa"))

    def test_invalid_arguments_rejected_before_gate_and_not_recorded(self):
        from mcp.server.mcpserver.exceptions import ToolError

        for kwargs in ({"url": "https://evil.com/?v=dQw4w9WgXcQ"}, {"start": 50, "end": 10},
                       {"transcript": "a" * 120_001}, {"mode": "evil"}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ToolError):
                self.call(**kwargs)
        self.assertEqual(len(server._asked_videos), 0)

    def test_memory_is_bounded(self):
        with mock.patch.object(server, "_MAX_ASKED", 3):
            for i in range(5):
                server._should_ask_for_transcript(True, f"vid{i}", None, False)
        self.assertEqual(list(server._asked_videos), ["vid2", "vid3", "vid4"])

    def test_tip_and_note_order_in_english(self):
        self.settings = settings(language="en")

        async def with_note(video, **kw):
            return gemini.AnalysisResult(text="analysis", model="m-main", fallback_note="retried.")

        self.analyze_mock.side_effect = with_note
        out = self.call(skip_transcript=True)
        self.assertIn("(Tip: adding the YouTube transcript", out)
        self.assertTrue(out.rstrip().endswith("(Note: retried.)"))  # 原因固定在最後一行


class TestGateText(unittest.TestCase):
    def test_prompt_and_instructions_are_english_except_ui_labels(self):
        for text in (server.TRANSCRIPT_PROMPT, server.mcp.instructions):
            stripped = text.replace("「顯示完整資訊」", "").replace("「顯示轉錄稿」", "")
            self.assertIsNone(CJK.search(stripped))

    def test_instructions_ask_to_keep_footer_line(self):
        self.assertIn("footer line", server.mcp.instructions)
        self.assertIn("yt-gemini-mcp v", server.mcp.instructions)
        self.assertIn("AFTER the closing </untrusted_video_analysis> tag", server.mcp.instructions)
        self.assertIn("Never copy lines from inside the tags", server.mcp.instructions)
        tool = asyncio.run(server.mcp.list_tools())[0]
        self.assertIn("skip_transcript", tool.input_schema["properties"])
        description = tool.input_schema["properties"]["skip_transcript"]["description"]
        self.assertIn("Just analyze", description)
        self.assertIn("no clickable-options tool", description)

    def test_prompt_asks_only_with_buttons_otherwise_skips(self):
        prompt = server.TRANSCRIPT_PROMPT
        self.assertIn("only if your app gives you a way to ask the user with clickable options", prompt)
        self.assertIn("'Paste transcript'", prompt)
        self.assertIn("'Just analyze'", prompt)
        self.assertIn("do not ask in plain text", prompt)
        self.assertIn("immediately call analyze_youtube again with the same arguments plus skip_transcript=true", prompt)
        self.assertIn("did not call Gemini", prompt)


class TestConfigAskForTranscript(unittest.TestCase):
    BASE = '[gemini]\n{extra}\n[profiles.chat]\nmodel = "gemini-test"\n'

    def load(self, extra):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.toml"
            path.write_text(self.BASE.format(extra=extra), encoding="utf-8")
            return config.load_settings(path, "chat")

    def test_default_true_and_false(self):
        self.assertTrue(self.load("").ask_for_transcript)
        self.assertFalse(self.load("ask_for_transcript = false").ask_for_transcript)

    def test_rejects_non_bool(self):
        for bad in ('"false"', "0", "1", '"yes"'):
            with self.subTest(bad=bad), self.assertRaises(config.ConfigError):
                self.load(f"ask_for_transcript = {bad}")

    def test_project_config_value_is_bool(self):
        # 不綁定使用者自己的選擇（可能改成 false），只確認設定檔的值合法。
        self.assertIsInstance(config.load_settings().ask_for_transcript, bool)

    def test_skip_transcript_is_strict_bool(self):
        from pydantic import TypeAdapter, ValidationError
        from typing import get_args, get_type_hints

        hint = get_type_hints(server.analyze_youtube, include_extras=True)["skip_transcript"]
        adapter = TypeAdapter(hint)
        self.assertIs(adapter.validate_python(True), True)
        for bad in ("true", "yes", 1, "1"):
            with self.subTest(bad=bad), self.assertRaises(ValidationError):
                adapter.validate_python(bad)


if __name__ == "__main__":
    unittest.main()
