from __future__ import annotations

import hashlib
import json
import os
import time
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class JsonDiskCache:
    def __init__(
        self,
        cache_dir: Path,
        *,
        warn: Callable[[str], None] | None = None,
    ) -> None:
        self._cache_dir = cache_dir
        self._warn = warn
        self._warning_sent = False
        self._cache_dir.mkdir(parents=True, exist_ok=True)

    def _path_for_key(self, key: str) -> Path:
        return self._cache_dir / f"{_sha256(key)}.json"

    def _warn_once(self, error: OSError) -> None:
        if self._warning_sent or self._warn is None:
            return
        self._warning_sent = True
        self._warn(
            f"Cache unavailable at {self._cache_dir}: {error}. "
            "OpenAI calls may repeat until the cache is writable again."
        )

    def get(self, key: str, *, ttl_seconds: float | None = None) -> Any | None:
        path = self._path_for_key(key)
        try:
            raw = path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return None
        except OSError as e:
            self._warn_once(e)
            return None

        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            payload = None

        if not isinstance(payload, dict):
            try:
                path.unlink(missing_ok=True)
            except OSError as e:
                self._warn_once(e)
                pass
            return None

        created_at_raw = payload.get("created_at")
        if not isinstance(created_at_raw, str) or not created_at_raw.strip():
            try:
                path.unlink(missing_ok=True)
            except OSError as e:
                self._warn_once(e)
                pass
            return None

        try:
            created_at = datetime.fromisoformat(created_at_raw.strip())
        except ValueError:
            try:
                path.unlink(missing_ok=True)
            except OSError as e:
                self._warn_once(e)
                pass
            return None

        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)

        if ttl_seconds is not None:
            age_seconds = max(0.0, (_utcnow() - created_at).total_seconds())
            if age_seconds > ttl_seconds:
                try:
                    path.unlink(missing_ok=True)
                except OSError as e:
                    self._warn_once(e)
                    pass
                return None

        return payload.get("value")

    def set(self, key: str, value: Any) -> None:
        path = self._path_for_key(key)
        tmp_path = path.with_suffix(f".tmp.{os.getpid()}.{time.time_ns()}")
        payload = {"created_at": _utcnow().isoformat(), "value": value}
        try:
            tmp_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            tmp_path.replace(path)
        except OSError as e:
            self._warn_once(e)
            try:
                tmp_path.unlink(missing_ok=True)
            except OSError as cleanup_error:
                self._warn_once(cleanup_error)
                pass
