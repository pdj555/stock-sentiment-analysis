"""
Backward-compatible entrypoint.

Prefer running the module directly:

  python3 -m stock_sentiment analyze TSLA
"""

from __future__ import annotations

from stock_sentiment.cli import _entrypoint


if __name__ == "__main__":
    _entrypoint()
