from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

import settings
from stock_sentiment.errors import ConfigurationError


class TestSettings(unittest.TestCase):
    def test_load_defaults_to_current_working_directory_dotenv(self) -> None:
        with patch("settings.load_dotenv") as mocked:
            settings.load()

        mocked.assert_called_once_with(Path(".env"))

    def test_require_env_uses_configuration_error(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaisesRegex(
                ConfigurationError,
                r"Missing OPENAI_API_KEY\. Set it in your shell or \./\.env, then try again\.",
            ):
                settings.require_env("OPENAI_API_KEY")
