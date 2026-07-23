import json
import unittest
from unittest.mock import patch

from shiyishang_agent.providers.anthropic import AnthropicProvider
from shiyishang_agent.providers.openai_compatible import OpenAICompatibleProvider


class ProviderTests(unittest.TestCase):
    @patch("shiyishang_agent.providers.openai_compatible.post_json")
    def test_openai_tool_call_normalization_and_full_endpoint(self, post):
        post.return_value = {"choices": [{"message": {"content": None, "tool_calls": [{"id": "x", "function": {"name": "read_file", "arguments": '{"path":"a.txt"}'}}]}}]}
        provider = OpenAICompatibleProvider("m", "k", "https://relay.test/v1/chat/completions")
        response = provider.chat([{"role": "user", "content": "go"}], [])
        self.assertEqual(response.tool_calls[0].arguments, {"path": "a.txt"})
        self.assertEqual(post.call_args.args[0], "https://relay.test/v1/chat/completions")

    @patch("shiyishang_agent.providers.anthropic.post_json")
    def test_anthropic_converts_openai_internal_messages(self, post):
        post.return_value = {"content": [{"type": "text", "text": "done"}]}
        provider = AnthropicProvider("claude", "k")
        messages = [
            {"role": "system", "content": "rules"},
            {"role": "user", "content": "read"},
            {"role": "assistant", "content": "", "tool_calls": [{"id": "x", "type": "function", "function": {"name": "read_file", "arguments": json.dumps({"path": "a"})}}]},
            {"role": "tool", "tool_call_id": "x", "name": "read_file", "content": "result"},
        ]
        response = provider.chat(messages, [])
        payload = post.call_args.args[1]
        self.assertEqual(response.content, "done")
        self.assertEqual(payload["messages"][1]["content"][0]["type"], "tool_use")
        self.assertEqual(payload["messages"][2]["content"][0]["type"], "tool_result")


if __name__ == "__main__":
    unittest.main()
