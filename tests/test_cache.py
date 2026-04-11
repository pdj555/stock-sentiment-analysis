from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from stock_sentiment.cache import JsonDiskCache


class TestJsonDiskCache(unittest.TestCase):
    def test_get_returns_none_on_oserror_and_warns_once(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            warnings: list[str] = []
            cache = JsonDiskCache(Path(tmp), warn=warnings.append)
            with patch("pathlib.Path.read_text", side_effect=[OSError("nope"), OSError("still nope")]):
                self.assertIsNone(cache.get("k", ttl_seconds=60))
                self.assertIsNone(cache.get("k", ttl_seconds=60))

        self.assertEqual(len(warnings), 1)
        self.assertIn("Cache unavailable", warnings[0])
        self.assertIn("OpenAI calls may repeat", warnings[0])

    def test_set_ignores_oserror_and_warns_once(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            warnings: list[str] = []
            cache = JsonDiskCache(Path(tmp), warn=warnings.append)
            with patch("pathlib.Path.write_text", side_effect=[OSError("nope"), OSError("still nope")]):
                cache.set("k", {"a": 1})
                cache.set("k", {"a": 2})

        self.assertEqual(len(warnings), 1)
        self.assertIn("Cache unavailable", warnings[0])
        self.assertIn("OpenAI calls may repeat", warnings[0])

    def test_get_accepts_naive_created_at(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cache_dir = Path(tmp)
            cache = JsonDiskCache(cache_dir)

            key = "k"
            digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
            path = cache_dir / f"{digest}.json"

            created_at = datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0).isoformat()
            path.write_text(
                json.dumps({"created_at": created_at, "value": {"a": 1}}, ensure_ascii=False),
                encoding="utf-8",
            )

            self.assertEqual(cache.get(key, ttl_seconds=60), {"a": 1})
