from __future__ import annotations

import gzip
import json
import random
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from stock_sentiment import __version__
from stock_sentiment.errors import RemoteApiError


@dataclass(frozen=True)
class HttpResponse:
    status: int
    headers: dict[str, str]
    body: bytes


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


_DEFAULT_USER_AGENT = f"stock-sentiment/{__version__}"
_REDACTED_QUERY_KEYS = {
    "apikey",
    "api_key",
    "access_token",
    "auth",
    "authorization",
    "key",
    "token",
}
_INLINE_WHITESPACE_RE = re.compile(r"\s+")


def _redact_url(url: str) -> str:
    """
    Best-effort redaction for common secret query params (e.g., apiKey=...).

    This is defensive: callers should prefer sending secrets via headers.
    """

    try:
        split = urlsplit(url)
    except ValueError:
        return url

    if not split.query:
        return url

    updated: list[tuple[str, str]] = []
    changed = False
    for key, value in parse_qsl(split.query, keep_blank_values=True):
        if key.lower() in _REDACTED_QUERY_KEYS:
            updated.append((key, "REDACTED"))
            changed = True
        else:
            updated.append((key, value))

    if not changed:
        return url

    return urlunsplit(split._replace(query=urlencode(updated, doseq=True)))


def _truncate_for_error(text: str, limit: int = 1200) -> str:
    """
    Keep error messages compact and readable.
    """

    if not text:
        return ""
    cleaned = _INLINE_WHITESPACE_RE.sub(" ", text).strip()
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: max(0, limit - 1)].rstrip() + "…"


def _extract_error_detail(body: bytes) -> str:
    if not body:
        return ""

    text = body.decode("utf-8", errors="replace").strip()
    if not text:
        return ""

    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return _truncate_for_error(text)

    if not isinstance(payload, dict):
        return _truncate_for_error(text)

    # OpenAI style: {"error": {"message": "...", "type": "...", "code": "..."}}
    error_obj = payload.get("error")
    if isinstance(error_obj, dict):
        message = error_obj.get("message")
        code = error_obj.get("code") or error_obj.get("type")
        if isinstance(message, str) and message.strip():
            if isinstance(code, str) and code.strip():
                return _truncate_for_error(f"{message.strip()} ({code.strip()})")
            return _truncate_for_error(message.strip())

    # NewsAPI style: {"status":"error","code":"...","message":"..."}
    message = payload.get("message")
    if isinstance(message, str) and message.strip():
        code = payload.get("code")
        if isinstance(code, str) and code.strip():
            return _truncate_for_error(f"{message.strip()} ({code.strip()})")
        return _truncate_for_error(message.strip())

    return _truncate_for_error(text)


def _read_http_response(response: Any) -> HttpResponse:
    status = int(getattr(response, "status", 0) or 0)
    headers_obj = getattr(response, "headers", None)
    headers: dict[str, str] = {}
    if headers_obj is not None:
        try:
            headers = {k.lower(): v for k, v in dict(headers_obj).items()}
        except Exception:
            headers = {}
    body = response.read()
    return HttpResponse(status=status, headers=headers, body=body)


def _parse_retry_after_seconds(headers: dict[str, str]) -> float | None:
    value = headers.get("retry-after")
    if not value:
        return None
    raw = value.strip()
    if not raw:
        return None

    if raw.isdigit():
        return float(raw)

    try:
        dt = parsedate_to_datetime(raw)
    except (TypeError, ValueError):
        return None

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    seconds = (dt - _utcnow()).total_seconds()
    return max(0.0, seconds)


def _maybe_decompress(response: HttpResponse) -> HttpResponse:
    encoding = (response.headers.get("content-encoding") or "").lower().strip()
    if encoding != "gzip":
        return response

    try:
        decompressed = gzip.decompress(response.body)
    except OSError:
        return response

    headers = dict(response.headers)
    headers.pop("content-encoding", None)
    headers.pop("content-length", None)
    return HttpResponse(status=response.status, headers=headers, body=decompressed)


def _request(
    *,
    method: str,
    url: str,
    headers: dict[str, str],
    data: bytes | None,
    timeout_seconds: float,
) -> tuple[HttpResponse, Exception | None]:
    last_error: Exception | None = None
    try:
        request = urllib.request.Request(url=url, data=data, method=method.upper(), headers=headers)
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            http_response = _read_http_response(response)
    except urllib.error.HTTPError as e:
        http_response = HttpResponse(
            status=int(getattr(e, "code", 0) or 0),
            headers={k.lower(): v for k, v in dict(getattr(e, "headers", {})).items()},
            body=e.read() if getattr(e, "fp", None) is not None else b"",
        )
    except (urllib.error.URLError, TimeoutError) as e:
        last_error = e
        http_response = HttpResponse(status=0, headers={}, body=b"")

    return _maybe_decompress(http_response), last_error


def http_request_json(
    *,
    method: str,
    url: str,
    headers: dict[str, str] | None = None,
    json_body: dict[str, Any] | None = None,
    timeout_seconds: float = 30.0,
    max_retries: int = 5,
    retry_backoff_base_seconds: float = 0.75,
    max_retry_after_seconds: float = 60.0,
) -> dict[str, Any]:
    """
    Make an HTTP request and return a parsed JSON object.

    Retries on common transient failures (429/5xx and network errors).
    """

    normalized_headers = {
        "accept": "application/json",
        "user-agent": _DEFAULT_USER_AGENT,
        "accept-encoding": "gzip",
    }
    if headers:
        normalized_headers.update({k.lower(): v for k, v in headers.items()})

    data = None
    if json_body is not None:
        data = json.dumps(json_body).encode("utf-8")
        normalized_headers.setdefault("content-type", "application/json")

    last_error: Exception | None = None
    for attempt in range(max_retries + 1):
        http_response, last_error = _request(
            method=method,
            url=url,
            headers=normalized_headers,
            data=data,
            timeout_seconds=timeout_seconds,
        )

        is_transient = http_response.status in {0, 429, 500, 502, 503, 504}
        if is_transient and attempt < max_retries:
            retry_after = _parse_retry_after_seconds(http_response.headers)
            sleep_s = retry_backoff_base_seconds * (2**attempt) + random.random() * 0.25
            if retry_after is not None:
                sleep_s = max(sleep_s, min(float(retry_after), max_retry_after_seconds))
            time.sleep(sleep_s)
            continue

        if http_response.status < 200 or http_response.status >= 300:
            message = _extract_error_detail(http_response.body)
            if not message and last_error is not None:
                message = str(last_error)
            safe_url = _redact_url(url)
            if message:
                raise RemoteApiError(
                    f"{method.upper()} {safe_url} failed ({http_response.status}): {message}"
                )
            raise RemoteApiError(f"{method.upper()} {safe_url} failed ({http_response.status})")

        try:
            parsed = json.loads(http_response.body.decode("utf-8", errors="replace"))
        except json.JSONDecodeError as e:
            safe_url = _redact_url(url)
            raise RemoteApiError(f"{method.upper()} {safe_url} returned invalid JSON: {e}") from e
        if not isinstance(parsed, dict):
            safe_url = _redact_url(url)
            raise RemoteApiError(
                f"{method.upper()} {safe_url} returned unexpected JSON type: {type(parsed).__name__}"
            )
        return parsed

    safe_url = _redact_url(url)
    raise RemoteApiError(f"{method.upper()} {safe_url} failed after retries: {last_error}")


def http_request_bytes(
    *,
    method: str,
    url: str,
    headers: dict[str, str] | None = None,
    timeout_seconds: float = 30.0,
    max_retries: int = 5,
    retry_backoff_base_seconds: float = 0.75,
    max_retry_after_seconds: float = 60.0,
) -> bytes:
    """
    Make an HTTP request and return the raw response body.

    Retries on common transient failures (429/5xx and network errors).
    """

    normalized_headers = {"accept": "*/*", "user-agent": _DEFAULT_USER_AGENT, "accept-encoding": "gzip"}
    if headers:
        normalized_headers.update({k.lower(): v for k, v in headers.items()})

    last_error: Exception | None = None
    for attempt in range(max_retries + 1):
        http_response, last_error = _request(
            method=method,
            url=url,
            headers=normalized_headers,
            data=None,
            timeout_seconds=timeout_seconds,
        )

        is_transient = http_response.status in {0, 429, 500, 502, 503, 504}
        if is_transient and attempt < max_retries:
            retry_after = _parse_retry_after_seconds(http_response.headers)
            sleep_s = retry_backoff_base_seconds * (2**attempt) + random.random() * 0.25
            if retry_after is not None:
                sleep_s = max(sleep_s, min(float(retry_after), max_retry_after_seconds))
            time.sleep(sleep_s)
            continue

        if http_response.status < 200 or http_response.status >= 300:
            message = _extract_error_detail(http_response.body)
            if not message and last_error is not None:
                message = str(last_error)
            safe_url = _redact_url(url)
            if message:
                raise RemoteApiError(
                    f"{method.upper()} {safe_url} failed ({http_response.status}): {message}"
                )
            raise RemoteApiError(f"{method.upper()} {safe_url} failed ({http_response.status})")

        return http_response.body

    safe_url = _redact_url(url)
    raise RemoteApiError(f"{method.upper()} {safe_url} failed after retries: {last_error}")
