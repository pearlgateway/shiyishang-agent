from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class History:
    def __init__(self, max_tokens: int = 128_000, session_path: Path | None = None) -> None:
        self.messages: list[dict[str, Any]] = []
        self.max_tokens = max_tokens
        self.session_path = session_path
        self.repaired_tool_chains = 0

    def append(self, message: dict[str, Any], persist: bool = True) -> None:
        self.messages.append(message)
        if persist and self.session_path:
            self.session_path.parent.mkdir(parents=True, exist_ok=True)
            with self.session_path.open("a", encoding="utf-8", newline="\n") as handle:
                handle.write(json.dumps(message, ensure_ascii=False) + "\n")

    def load(self) -> None:
        if not self.session_path or not self.session_path.is_file():
            return
        self.messages = [json.loads(line) for line in self.session_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        self.repaired_tool_chains = self.repair_tool_chains()

    def repair_tool_chains(self) -> int:
        """Drop interrupted tool calls so providers receive a valid message chain.

        A process can stop after an assistant asks for a tool but before its
        result is persisted. OpenAI-compatible and Anthropic APIs reject that
        incomplete sequence on the next resumed turn.
        """
        repaired: list[dict[str, Any]] = []
        index = 0
        removed = 0
        while index < len(self.messages):
            message = self.messages[index]
            if message.get("role") != "assistant" or not message.get("tool_calls"):
                if message.get("role") != "tool":
                    repaired.append(message)
                else:
                    removed += 1
                index += 1
                continue

            calls = message.get("tool_calls") or []
            expected = {call.get("id") for call in calls if call.get("id")}
            results: list[dict[str, Any]] = []
            cursor = index + 1
            while cursor < len(self.messages) and self.messages[cursor].get("role") == "tool":
                results.append(self.messages[cursor])
                cursor += 1
            received = {result.get("tool_call_id") for result in results}
            if expected and expected.issubset(received):
                repaired.append(message)
                repaired.extend(result for result in results if result.get("tool_call_id") in expected)
                removed += len(results) - len(expected)
            else:
                content = message.get("content")
                if content:
                    repaired.append({"role": "assistant", "content": content})
                removed += 1 + len(results)
            index = cursor
        self.messages = repaired
        return removed

    def token_count(self) -> int:
        serialized = json.dumps(self.messages, ensure_ascii=False, separators=(",", ":"))
        return max(1, (len(serialized) + 2) // 3)

    def compress(self) -> bool:
        if self.token_count() <= int(self.max_tokens * 0.9) or len(self.messages) < 8:
            return False
        keep = max(6, len(self.messages) // 3)
        old, recent = self.messages[:-keep], self.messages[-keep:]
        snippets: list[str] = []
        for message in old:
            content = str(message.get("content", "")).replace("\n", " ")
            if content:
                snippets.append(f"{message.get('role', '?')}: {content[:240]}")
        summary = "[早期战报摘要]\n" + "\n".join(snippets[-24:])
        self.messages = [{"role": "system", "content": summary}, *recent]
        return True

    def clear(self) -> None:
        """Clear persisted conversation while keeping in-memory system messages."""
        self.messages = [message for message in self.messages if message.get("role") == "system"]
        if self.session_path:
            self.session_path.parent.mkdir(parents=True, exist_ok=True)
            self.session_path.write_text("", encoding="utf-8", newline="\n")
