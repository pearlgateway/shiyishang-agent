from __future__ import annotations

import json
from typing import Any

from ..models import ProviderResponse, ToolCall
from .base import Provider
from .http import post_json


DEFAULT_URLS = {
    "openai": "https://api.openai.com/v1",
    "deepseek": "https://api.deepseek.com/v1",
    "kimi": "https://api.moonshot.cn/v1",
    "grok": "https://api.x.ai/v1",
}


class OpenAICompatibleProvider(Provider):
    def __init__(self, model: str, api_key: str, base_url: str = "", timeout: float = 60, provider_name: str = "relay") -> None:
        self.model = model
        self.api_key = api_key
        self.base_url = (base_url or DEFAULT_URLS.get(provider_name, "")).rstrip("/")
        self.timeout = timeout

    def chat(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> ProviderResponse:
        payload: dict[str, Any] = {"model": self.model, "messages": messages}
        if tools:
            payload["tools"] = [{"type": "function", "function": tool} for tool in tools]
            payload["tool_choice"] = "auto"
        url = self.base_url if self.base_url.endswith("/chat/completions") else f"{self.base_url}/chat/completions"
        data = post_json(url, payload, {"Authorization": f"Bearer {self.api_key}"}, self.timeout)
        message = data["choices"][0]["message"]
        calls = []
        for item in message.get("tool_calls") or []:
            function = item.get("function", {})
            raw_args = function.get("arguments", "{}")
            try:
                arguments = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
            except json.JSONDecodeError:
                arguments = {"_raw": raw_args}
            calls.append(ToolCall(id=item.get("id", "call"), name=function.get("name", ""), arguments=arguments))
        return ProviderResponse(content=message.get("content") or "", tool_calls=calls, raw=data)
