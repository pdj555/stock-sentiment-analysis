from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from stock_sentiment.env import load_dotenv


class TestDotenv(unittest.TestCase):
    def test_load_dotenv_sets_missing_vars(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / ".env"
            path.write_text("FOO=bar\n# comment\nBAZ='qux'\n", encoding="utf-8")

            os.environ.pop("FOO", None)
            os.environ.pop("BAZ", None)
            load_dotenv(path)

            self.assertEqual(os.environ.get("FOO"), "bar")
            self.assertEqual(os.environ.get("BAZ"), "qux")

    def test_load_dotenv_does_not_override_existing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / ".env"
            path.write_text("FOO=from_file\n", encoding="utf-8")

            os.environ["FOO"] = "from_env"
            load_dotenv(path)

            self.assertEqual(os.environ.get("FOO"), "from_env")

    def test_load_dotenv_supports_export_and_inline_comments(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / ".env"
            path.write_text(
                "export FOO=bar # comment\n"
                "BAZ=qux#not_a_comment\n"
                'QUOTED="hello # not a comment" # trailing comment\n'
                "1BAD=ignored\n",
                encoding="utf-8",
            )

            os.environ.pop("FOO", None)
            os.environ.pop("BAZ", None)
            os.environ.pop("QUOTED", None)
            os.environ.pop("1BAD", None)
            load_dotenv(path)

            self.assertEqual(os.environ.get("FOO"), "bar")
            self.assertEqual(os.environ.get("BAZ"), "qux#not_a_comment")
            self.assertEqual(os.environ.get("QUOTED"), "hello # not a comment")
            self.assertIsNone(os.environ.get("1BAD"))
