"""Vercel serverless entrypoint.

Vercel only treats files inside ``api/`` as Serverless Functions, so this
module exposes the WSGI ``app`` for the platform. All routes are sent here via
the ``rewrites`` rule in ``vercel.json``; the WSGI app itself handles path
dispatch (``/``, ``/api/analyze``, ``/health``).
"""

from __future__ import annotations

import sys
from pathlib import Path

# The stock_sentiment package lives at the repo root, one level above api/.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from stock_sentiment.ui import app

__all__ = ["app"]
