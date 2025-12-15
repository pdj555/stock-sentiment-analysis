from __future__ import annotations

import unittest

from stock_sentiment.openai_client import extract_output_text


class TestOpenAIClient(unittest.TestCase):
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

