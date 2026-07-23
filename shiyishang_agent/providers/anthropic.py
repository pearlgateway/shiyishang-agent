from __future__ import annotations

from typing import Any

from ..models import ProviderResponse, ToolCall
from .base import Provider
from .http import post_json


class AnthropicProvider(Provider):
    def __init__(self, model: str, api_key: str, base_url: str = "https://api.anthropic.com/v1", timeout: float = 60, **_: Any) -> None:
        self.model = model
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def chat(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> ProviderResponse:
        system = "\n".join(str(m.get("content", "")) for m in messages if m.get("role") == "system")
        conversation: list[dict[str, Any]] = []
        for message in messages:
            role = message.get("role")
            if role == "system":
                continue
            if role == "assistant":
                blocks: list[dict[str, Any]] = []
                if message.get("content"):
                    blocks.append({"type": "text", "text": message["content"]})
                for call in message.get("tool_calls") or []:
                    function = call.get("function", {})
                    arguments = function.get("arguments", "{}")
                    if isinstance(arguments, str):
                        import json
                        try:
                            arguments = json.loads(arguments)
                        except json.JSONDecodeError:
                            arguments = {"_raw": arguments}
                    blocks.append({"type": "tool_use", "id": call.get("id"), "name": function.get("name"), "input": arguments})
                conversation.append({"role": "assistant", "content": blocks or [{"type": "text", "text": ""}]})
            elif role == "tool":
                block = {"type": "tool_result", "tool_use_id": message.get("tool_call_id"), "content": str(message.get("content", ""))}
                if conversation and conversation[-1]["role"] == "user" and isinstance(conversation[-1]["content"], list):
                    conversation[-1]["content"].append(block)
                else:
                    conversation.append({"role": "user", "content": [block]})
            else:
                conversation.append({"role": "user", "content": message.get("content", "")})
        payload: dict[str, Any] = {"model": self.model, "max_tokens": 4096, "system": system, "messages": conversation}
        if tools:
            payload["tools"] = [{"name": t["name"], "description": t.get("description", ""), "input_schema": t["parameters"]} for t in tools]
        url = self.base_url if self.base_url.endswith("/messages") else f"{self.base_url}/messages"
        data = post_json(
            url,
            payload,
            {"x-api-key": self.api_key, "anthropic-version": "2023-06-01"},
            self.timeout,
        )
        texts, calls = [], []
        for block in data.get("content", []):
            if block.get("type") == "text":
                texts.append(block.get("text", ""))
            elif block.get("type") == "tool_use":
                calls.append(ToolCall(id=block["id"], name=block["name"], arguments=block.get("input", {})))
        return ProviderResponse(content="\n".join(texts), tool_calls=calls, raw=data)
