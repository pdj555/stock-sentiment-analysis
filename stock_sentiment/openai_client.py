from __future__ import annotations

from typing import Any

from stock_sentiment.http import http_request_json


def create_response(
    *,
    api_key: str,
    model: str,
    input_payload: Any,
    response_format: dict[str, Any] | None = None,
    temperature: float | None = 0.2,
    max_output_tokens: int | None = 800,
    base_url: str = "https://api.openai.com/v1",
    timeout_seconds: float = 45.0,
    max_retries: int = 6,
) -> dict[str, Any]:
    headers = {"authorization": f"Bearer {api_key}"}
    body: dict[str, Any] = {"model": model, "input": input_payload}
    if response_format is not None:
        body["response_format"] = response_format
    if temperature is not None:
        body["temperature"] = float(temperature)
    if max_output_tokens is not None:
        body["max_output_tokens"] = int(max_output_tokens)

    return http_request_json(
        method="POST",
        url=f"{base_url.rstrip('/')}/responses",
        headers=headers,
        json_body=body,
        timeout_seconds=timeout_seconds,
        max_retries=max_retries,
    )


def extract_output_text(response: dict[str, Any]) -> str:
    """
    Best-effort extraction of assistant text from a Responses API payload.
    """

    output_text = response.get("output_text")
    if isinstance(output_text, str) and output_text.strip():
        return output_text

    chunks: list[str] = []
    for item in response.get("output", []) or []:
        if not isinstance(item, dict) or item.get("type") != "message":
            continue
        for content in item.get("content", []) or []:
            if not isinstance(content, dict):
                continue
            if content.get("type") == "output_text" and isinstance(content.get("text"), str):
                chunks.append(content["text"])

    return "\n".join(chunks).strip()
