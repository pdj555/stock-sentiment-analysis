"""Vercel Serverless Function backing the ``POST /api/analyze`` endpoint.

Vercel maps files in ``api/`` to routes by path, so this module is served at
``/api/analyze`` with no rewrite rules required. It reuses the dependency-free
WSGI application from :mod:`stock_sentiment.ui` and pins ``PATH_INFO`` so the
WSGI router dispatches correctly regardless of how the platform populates it.
"""

from __future__ import annotations

import sys
from collections.abc import Callable, Iterable
from pathlib import Path

# The stock_sentiment package lives at the repo root, one level above api/.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from stock_sentiment.ui import app as _wsgi_app

StartResponse = Callable[[str, list[tuple[str, str]]], object]


def app(environ: dict[str, object], start_response: StartResponse) -> Iterable[bytes]:
    """WSGI entrypoint Vercel invokes for the /api/analyze route."""

    environ["PATH_INFO"] = "/api/analyze"
    return _wsgi_app(environ, start_response)
