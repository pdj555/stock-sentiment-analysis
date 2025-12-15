from __future__ import annotations

import os
import re
from pathlib import Path


_ENV_KEY_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def load_dotenv(dotenv_path: Path) -> None:
    """
    Load environment variables from a .env file if it exists.

    Rules:
    - Ignores blank lines and comments starting with '#'
    - Supports optional 'export ' prefix
    - Uses KEY=VALUE pairs; quoted values are unwrapped
    - For unquoted values, strips trailing inline comments starting with ' #'
    - Does not overwrite existing environment variables
    """

    if not dotenv_path.exists() or not dotenv_path.is_file():
        return

    for raw_line in dotenv_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        if line.lower().startswith("export "):
            line = line[len("export ") :].lstrip()

        if "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        if not key or not _ENV_KEY_RE.match(key):
            continue

        value = value.strip()
        if value.startswith(("'", '"')):
            quote = value[0]
            inner, sep, _ = value[1:].partition(quote)
            value = inner if sep else value[1:]
        else:
            value = re.split(r"\s+#", value, maxsplit=1)[0].rstrip()

        os.environ.setdefault(key, value)
