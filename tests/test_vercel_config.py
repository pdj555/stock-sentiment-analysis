from __future__ import annotations

import json
import unittest
from pathlib import Path


class TestVercelConfig(unittest.TestCase):
    def test_wsgi_entrypoint_has_function_settings(self) -> None:
        config = json.loads(Path("vercel.json").read_text())

        self.assertEqual(config["functions"]["app.py"]["maxDuration"], 60)
        self.assertIn("tests/**", config["functions"]["app.py"]["excludeFiles"])

    def test_all_paths_rewrite_to_wsgi_entrypoint(self) -> None:
        config = json.loads(Path("vercel.json").read_text())

        self.assertIn(
            {"source": "/(.*)", "destination": "/app.py"},
            config["rewrites"],
        )
