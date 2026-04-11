from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

import settings


class TestSettings(unittest.TestCase):
    def test_load_defaults_to_current_working_directory_dotenv(self) -> None:
        with patch("settings.load_dotenv") as mocked:
            settings.load()

        mocked.assert_called_once_with(Path(".env"))
