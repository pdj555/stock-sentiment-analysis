from __future__ import annotations

import unittest
from unittest.mock import patch

from stock_sentiment.errors import ConfigurationError
from stock_sentiment.openai_client import create_response, extract_output_text


class TestOpenAIClient(unittest.TestCase):
    def test_create_response_builds_responses_api_request(self) -> None:
        with patch(
            "stock_sentiment.openai_client.http_request_json",
            return_value={"id": "resp_123"},
        ) as mock_http_request_json:
            payload = create_response(
                api_key="test-key",
                model="gpt-test",
                input_payload=[{"role": "user", "content": [{"type": "text", "text": "hi"}]}],
                response_format={"type": "json_schema"},
                temperature=0.4,
                max_output_tokens=321,
                base_url="https://api.openai.com/v1/",
                timeout_seconds=12.5,
                max_retries=2,
            )

        self.assertEqual(payload, {"id": "resp_123"})
        self.assertEqual(mock_http_request_json.call_args.kwargs["method"], "POST")
        self.assertEqual(
            mock_http_request_json.call_args.kwargs["url"],
            "https://api.openai.com/v1/responses",
        )
        self.assertEqual(
            mock_http_request_json.call_args.kwargs["headers"],
            {"authorization": "Bearer test-key"},
        )
        self.assertEqual(
            mock_http_request_json.call_args.kwargs["json_body"]["model"],
            "gpt-test",
        )
        self.assertEqual(
            mock_http_request_json.call_args.kwargs["json_body"]["temperature"],
            0.4,
        )
        self.assertEqual(
            mock_http_request_json.call_args.kwargs["json_body"]["max_output_tokens"],
            321,
        )

    def test_create_response_rejects_invalid_temperature(self) -> None:
        with self.assertRaisesRegex(ConfigurationError, r"Temperature must be a number\."):
            create_response(
                api_key="test-key",
                model="gpt-test",
                input_payload=[],
                temperature="warm",  # type: ignore[arg-type]
            )

    def test_create_response_rejects_invalid_max_output_tokens(self) -> None:
        with self.assertRaisesRegex(
            ConfigurationError,
            r"Max output tokens must be an integer >= 1\.",
        ):
            create_response(
                api_key="test-key",
                model="gpt-test",
                input_payload=[],
                max_output_tokens=0,
            )

    def test_extract_output_text_prefers_output_text_field(self) -> None:
        response = {"output_text": "hello"}
        self.assertEqual(extract_output_text(response), "hello")

    def test_extract_output_text_from_output_messages(self) -> None:
        response = {
            "output": [
                {
                    "type": "message",
                    "role": "assistant",
                    "content": [{"type": "output_text", "text": "hi"}],
                }
            ]
        }
        self.assertEqual(extract_output_text(response), "hi")
