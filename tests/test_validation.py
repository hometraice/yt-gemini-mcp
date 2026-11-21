"""URL 與參數驗證的單元測試（不需要網路、不需要 key）。"""

import unittest

from yt_gemini.validation import (
    MAX_QUESTION_LENGTH,
    MAX_SECONDS,
    ValidationError,
    parse_youtube_url,
    validate_detail,
    validate_mode,
    validate_question,
    validate_time_range,
)

VID = "dQw4w9WgXcQ"
CANONICAL = f"https://www.youtube.com/watch?v={VID}"


class TestValidUrls(unittest.TestCase):
    def test_accepted_formats(self):
        cases = [
            f"https://www.youtube.com/watch?v={VID}",
            f"https://youtube.com/watch?v={VID}",
            f"https://m.youtube.com/watch?v={VID}",
            f"http://www.youtube.com/watch?v={VID}",
            f"https://youtu.be/{VID}",
            f"https://www.youtube.com/shorts/{VID}",
            f"https://youtube.com/shorts/{VID}/",
            f"youtube.com/watch?v={VID}",
            f"youtu.be/{VID}",
            f"m.youtube.com/watch?v={VID}",
            f"https://WWW.YouTube.COM/watch?v={VID}",
            f"HTTPS://youtu.be/{VID}",
            f"  https://youtu.be/{VID}  ",
            f"https://www.youtube.com/watch?v={VID}&t=42s&list=PL123&index=2",
            f"https://www.youtube.com/watch?feature=share&v={VID}",
            f"https://youtu.be/{VID}?si=AbCdEf123&t=10",
            f"https://www.youtube.com/shorts/{VID}?feature=share",
            f"https://www.youtube.com/watch?v={VID}#comments",
        ]
        for url in cases:
            with self.subTest(url=url):
                ref = parse_youtube_url(url)
                self.assertEqual(ref.video_id, VID)
                self.assertEqual(ref.canonical_url, CANONICAL)

    def test_canonical_url_never_contains_original_extras(self):
        ref = parse_youtube_url(f"https://youtu.be/{VID}?si=tracking&redirect=https://evil.com")
        self.assertEqual(ref.canonical_url, CANONICAL)
        self.assertNotIn("evil", ref.canonical_url)


class TestMaliciousHosts(unittest.TestCase):
    def test_rejected_hosts(self):
        cases = [
            f"https://youtube.com.evil.com/watch?v={VID}",
            f"https://www.youtube.com.evil.com/watch?v={VID}",
            f"https://evil.com/?v={VID}",
            f"https://evil.com/watch?v={VID}",
            f"https://evil.com/{VID}",
            f"https://evilyoutube.com/watch?v={VID}",
            f"https://notyoutu.be/{VID}",
            f"https://youtu.be.evil.com/{VID}",
            f"https://music.youtube.com/watch?v={VID}",
            f"https://youtube.com./watch?v={VID}",
            f"https://youtube.com@evil.com/watch?v={VID}",
            f"https://evil.com@youtube.com/watch?v={VID}",
            f"https://user:pass@www.youtube.com/watch?v={VID}",
            f"https://evil.com#@youtube.com/watch?v={VID}",
            f"https://evil.com?.youtube.com/watch?v={VID}",
            f"https://www.youtube.com:8080/watch?v={VID}",
            f"https://www.youtube.com:443/watch?v={VID}",
            f"https://www.youtube.com:abc/watch?v={VID}",
            f"https://www.youtube.com\\@evil.com/watch?v={VID}",
            f"https://%77ww.youtube.com/watch?v={VID}",
            f"https://www.уoutube.com/watch?v={VID}",  # 西里爾字母 у（同形字攻擊）
            f"https://127.0.0.1/watch?v={VID}",
            f"https://169.254.169.254/watch?v={VID}",
            f"https://localhost/watch?v={VID}",
            f"//www.youtube.com/watch?v={VID}",
        ]
        for url in cases:
            with self.subTest(url=url):
                with self.assertRaises(ValidationError):
                    parse_youtube_url(url)


class TestMaliciousSchemes(unittest.TestCase):
    def test_rejected_schemes(self):
        cases = [
            "javascript:alert(1)",
            "JaVaScRiPt:alert(document.cookie)",
            f"javascript://www.youtube.com/watch?v={VID}",
            f"javascript:%0a//youtube.com/watch?v={VID}",
            "data:text/html,<script>alert(1)</script>",
            "file:///C:/Windows/win.ini",
            f"file://www.youtube.com/watch?v={VID}",
            f"ftp://www.youtube.com/watch?v={VID}",
            f"gopher://youtu.be/{VID}",
            "vbscript:msgbox(1)",
            f"https:www.youtube.com/watch?v={VID}",
        ]
        for url in cases:
            with self.subTest(url=url):
                with self.assertRaises(ValidationError):
                    parse_youtube_url(url)


class TestBadPathsAndIds(unittest.TestCase):
    def test_rejected(self):
        cases = [
            "https://www.youtube.com/watch",
            "https://www.youtube.com/watch?v=",
            f"https://www.youtube.com/watch?v={VID}&v=aaaaaaaaaaa",  # 兩個 v，含糊不清
            "https://www.youtube.com/watch?v=short",
            f"https://www.youtube.com/watch?v={VID}X",  # 12 碼
            "https://www.youtube.com/watch?v=dQw4w9WgXc!",
            "https://www.youtube.com/watch?v=dQw4w9WgX%22",  # 編碼後的引號
            f"https://www.youtube.com/watch?v={VID}%0a",  # 編碼後的換行
            f"https://www.youtube.com/embed/{VID}",
            f"https://www.youtube.com/v/{VID}",
            f"https://www.youtube.com/{VID}",
            f"https://www.youtube.com/watch/../shorts/{VID}",
            f"https://www.youtube.com/shorts/{VID}/extra",
            f"https://youtu.be/{VID}/extra",
            "https://youtu.be/",
            f"https://youtu.be/watch?v={VID}",
            "https://www.youtube.com/channel/UC1234567890",
            "https://www.youtube.com/playlist?list=PL123",
        ]
        for url in cases:
            with self.subTest(url=url):
                with self.assertRaises(ValidationError):
                    parse_youtube_url(url)


class TestOddInput(unittest.TestCase):
    def test_non_string_and_empty(self):
        for value in (None, 123, b"https://youtu.be/dQw4w9WgXcQ", ["https://youtu.be/dQw4w9WgXcQ"], "", "   "):
            with self.subTest(value=value):
                with self.assertRaises(ValidationError):
                    parse_youtube_url(value)

    def test_surrounding_whitespace_is_stripped(self):
        for url in (f"https://www.youtube.com/watch?v={VID}\n", f"\thttps://youtu.be/{VID}\t"):
            with self.subTest(url=repr(url)):
                self.assertEqual(parse_youtube_url(url).video_id, VID)

    def test_embedded_whitespace_and_control_characters(self):
        cases = [
            f"https://www.you tube.com/watch?v={VID}",
            f"https://www.youtube.com/watch?v={VID}\r\nX-Injected: 1",
            f"https://www.youtube.com/watch?v={VID}\x00",
            f"https://www.youtube.com/watch?v={VID}\x7f",
            f"https://youtu.be/\u200b{VID}",  # zero-width space
        ]
        for url in cases:
            with self.subTest(url=repr(url)):
                with self.assertRaises(ValidationError):
                    parse_youtube_url(url)

    def test_overlong_input(self):
        cases = [
            f"https://www.youtube.com/watch?v={VID}&pad=" + "a" * 5000,
            "https://youtu.be/" + "a" * 100_000,
            "a" * 1_000_000,
        ]
        for url in cases:
            with self.subTest(length=len(url)):
                with self.assertRaises(ValidationError):
                    parse_youtube_url(url)

    def test_long_but_within_limit_is_still_checked(self):
        url = f"https://www.youtube.com/watch?v={VID}&pad=" + "a" * 1900
        self.assertEqual(parse_youtube_url(url).video_id, VID)


class TestQuestion(unittest.TestCase):
    def test_optional(self):
        self.assertIsNone(validate_question(None))
        self.assertIsNone(validate_question(""))
        self.assertIsNone(validate_question("   "))

    def test_length_limit(self):
        self.assertEqual(len(validate_question("問" * MAX_QUESTION_LENGTH)), MAX_QUESTION_LENGTH)
        with self.assertRaises(ValidationError):
            validate_question("問" * (MAX_QUESTION_LENGTH + 1))

    def test_newlines_ok_control_chars_rejected(self):
        self.assertEqual(validate_question("第一行\n第二行\t縮排"), "第一行\n第二行\t縮排")
        for bad in ("abc\x00", "abc\x1b[31m", "abc\x07"):
            with self.subTest(bad=repr(bad)):
                with self.assertRaises(ValidationError):
                    validate_question(bad)

    def test_type(self):
        with self.assertRaises(ValidationError):
            validate_question(123)


class TestTimeRange(unittest.TestCase):
    def test_valid(self):
        self.assertEqual(validate_time_range(None, None), (None, None))
        self.assertEqual(validate_time_range(0, 10), (0, 10))
        self.assertEqual(validate_time_range(30, None), (30, None))
        self.assertEqual(validate_time_range(None, 60), (None, 60))
        self.assertEqual(validate_time_range(0, MAX_SECONDS), (0, MAX_SECONDS))

    def test_invalid(self):
        cases = [
            (-1, None),
            (None, -5),
            (10, 10),
            (20, 10),
            (None, 0),
            (1.5, 10),
            (0, 10.0),
            ("0", 10),
            (True, 10),
            (0, False),
            (0, MAX_SECONDS + 1),
        ]
        for start, end in cases:
            with self.subTest(start=start, end=end):
                with self.assertRaises(ValidationError):
                    validate_time_range(start, end)


class TestDetail(unittest.TestCase):
    def test_detail(self):
        self.assertEqual(validate_detail("low"), "low")
        self.assertEqual(validate_detail("default"), "default")
        self.assertEqual(validate_detail(None), "low")
        for bad in ("high", "LOW", "", 1):
            with self.subTest(bad=bad):
                with self.assertRaises(ValidationError):
                    validate_detail(bad)


class TestMode(unittest.TestCase):
    def test_mode(self):
        for mode in ("summary", "notes", "tutorial", "quotes", "claims"):
            self.assertEqual(validate_mode(mode), mode)
        self.assertEqual(validate_mode(None), "summary")
        for bad in ("SUMMARY", "transcript", "", "summary; rm", 1, ["notes"]):
            with self.subTest(bad=bad):
                with self.assertRaises(ValidationError):
                    validate_mode(bad)


if __name__ == "__main__":
    unittest.main()
