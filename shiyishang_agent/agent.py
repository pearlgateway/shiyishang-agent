from __future__ import annotations

import json
import random
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from .config import Config
from .history import History
from .persona import Persona
from .providers import create_provider
from .providers.base import Provider
from .skills import SkillLoader
from .tools import ToolRegistry


LORE_IDENTITY_MARKERS = ("bin", "世一上", "陈泽彬", "优胜者")
LORE_INCIDENT_MARKERS = ("siwoo", "zeus", "不参团", "单杀", "被抓", "第五局")
READ_ONLY_TOOLS = {"get_weather", "web_search", "web_fetch", "read_file", "get_lol_schedule"}
CHINESE_NUMBERS = {"一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}


class Agent:
    def __init__(
        self,
        config: Config,
        provider: Provider | None = None,
        output: Callable[[str], None] | None = None,
        session_name: str | None = None,
    ) -> None:
        self.config = config
        self.output = output or print
        self.persona = Persona(enabled=config.rp_enabled, strict_notp=config.strict_notp)
        self.registry = ToolRegistry(config.workspace, timeout=config.request_timeout)
        self.skills = SkillLoader([config.workspace / "skills" / "user_skills", Path.home() / ".codex" / "skills"])
        self.skills.scan()
        session_name = session_name or datetime.now().strftime("%Y%m%d-%H%M%S")
        self.history = History(config.max_context_tokens, config.workspace / "sessions" / f"{session_name}.jsonl")
        self.history.load()
        if self.history.repaired_tool_chains:
            self.output(f"检测到上次会话中断，已清理 {self.history.repaired_tool_chains} 条未完成工具记录。")
        self.provider = provider or create_provider(
            config.provider,
            model=config.model,
            api_key=config.api_key,
            base_url=config.base_url,
            timeout=config.request_timeout,
        )
        self.history.messages.insert(0, {"role": "system", "content": self.skills.metadata_prompt()})
        self.history.messages.insert(0, {"role": "system", "content": self.persona.system_prompt()})
        self._ability_skill_active = False
        self._sentence_limit: int | None = None

    @staticmethod
    def _requested_sentence_limit(user_input: str) -> int | None:
        match = re.search(r"(?:只(?:用|要)?|用)?\s*([一二两三四五六七八九十]|\d+)\s*句(?:话)?", user_input)
        if not match:
            return None
        raw = match.group(1)
        return CHINESE_NUMBERS.get(raw, int(raw) if raw.isdigit() else None)

    @staticmethod
    def _limit_sentences(text: str, limit: int) -> str:
        parts = re.findall(r".*?[。！？!?]|.+$", text.strip(), flags=re.S)
        sentences = [part.strip() for part in parts if part.strip()]
        return " ".join(sentences[:limit])

    def _say(self, text: str, *, final: bool = False) -> str:
        if not text:
            return ""
        if self._sentence_limit is not None:
            if not final:
                return ""
            text = self._limit_sentences(text, self._sentence_limit)
        self.output(text)
        return text

    def _show_tool_io(self, phase: str, name: str, payload: dict[str, Any]) -> None:
        if not self.config.show_tool_io:
            return
        rendered = json.dumps(payload, ensure_ascii=False, indent=2, default=str)
        limit = max(200, self.config.max_tool_output_chars)
        if len(rendered) > limit:
            rendered = rendered[:limit] + f"\n... [truncated {len(rendered) - limit} characters]"
        self.output(f"\n[TOOL {phase}] {name}\n{rendered}")

    def _lore_path(self) -> Path | None:
        candidates = [
            self.config.workspace / "lore" / "世一上_补充版.md",
            self.config.workspace / "PLAN" / "世一上_补充版.md",
        ]
        return next((path for path in candidates if path.is_file()), None)

    @staticmethod
    def _is_lore_question(user_input: str) -> bool:
        lowered = user_input.lower()
        if any(marker in lowered for marker in LORE_IDENTITY_MARKERS):
            return True
        return any(marker in lowered for marker in LORE_INCIDENT_MARKERS) and any(marker in lowered for marker in ("为什么", "怎么", "事迹", "表现", "评价"))

    def _inject_context(self, user_input: str) -> None:
        self._ability_skill_active = False
        if self._is_lore_question(user_input):
            lore = self._lore_path()
            if lore:
                arguments = {"path": str(lore), "max_chars": 60_000}
                self._show_tool_io("CALL", "read_file", arguments)
                result = self.registry.execute("read_file", arguments)
                self._show_tool_io("RESULT", "read_file", result)
                if result.get("ok"):
                    self._say("我的战绩我倒背如流，读档只是给媒体确认细节。")
                    call_id = "lore-prefetch"
                    self.history.append({
                        "role": "assistant",
                        "content": "",
                        "tool_calls": [{"id": call_id, "type": "function", "function": {"name": "read_file", "arguments": json.dumps(arguments, ensure_ascii=False)}}],
                    })
                    self.history.append({
                        "role": "tool",
                        "tool_call_id": call_id,
                        "name": "read_file",
                        "content": json.dumps({**result, "instruction": "事迹事实以此档案为准，不得编造"}, ensure_ascii=False),
                    })
        for skill in self.skills.match(user_input):
            if skill.name != "shiyishang":
                self._ability_skill_active = True
            self._say(f"教练组加载了新战术（{skill.name}），跟我想的差不多。")
            self.history.append({"role": "system", "content": f"[能力技能：{skill.name}，其约束优先于人格坏习惯]\n{skill.body}"})

    def _assistant_message(self, response) -> dict[str, Any]:
        message: dict[str, Any] = {"role": "assistant", "content": response.content or ""}
        if response.tool_calls:
            message["tool_calls"] = [
                {"id": call.id, "type": "function", "function": {"name": call.name, "arguments": json.dumps(call.arguments, ensure_ascii=False)}}
                for call in response.tool_calls
            ]
        return message

    def run_turn(self, user_input: str) -> str:
        approved = "批准搜索" in user_input
        self._sentence_limit = self._requested_sentence_limit(user_input)
        self.history.append({"role": "user", "content": user_input})
        self._inject_context(user_input)
        if self._sentence_limit is not None:
            self.history.append({"role": "system", "content": f"本轮硬性输出约束：最终可见回答必须恰好不超过 {self._sentence_limit} 句话；不要在答案后追加角色台词。工具过程旁白由程序隐藏。"}, persist=False)
        self.history.compress()
        final_text = ""
        for _ in range(self.config.max_tool_rounds):
            response = self.provider.chat(self.history.messages, self.registry.schemas())
            self.history.append(self._assistant_message(response))
            if response.content:
                final_text = response.content
            if not response.tool_calls:
                return self._say(final_text, final=True)
            executed_read_only: list[tuple[str, dict[str, Any]]] = []
            for call in response.tool_calls:
                self._show_tool_io("CALL", call.name, call.arguments)
                if self._ability_skill_active and call.name == "read_file":
                    allowed, reason = True, ""
                else:
                    allowed, reason = self.persona.gate(call.name, approved_search=approved)
                if not allowed:
                    self._say(reason)
                    result = {"ok": False, "blocked_by_persona": True, "message": reason}
                else:
                    quote = self.persona.before_tool(call.name)
                    if quote:
                        self._say(quote)
                    result = self.registry.execute(call.name, call.arguments)
                    success = bool(result.get("ok"))
                    attribution = self.persona.after_tool(success)
                    if attribution:
                        self._say(attribution)
                    meltdown = self.persona.record_result(success)
                    if meltdown:
                        self._say(meltdown)
                    if call.name in READ_ONLY_TOOLS:
                        executed_read_only.append((call.name, call.arguments))
                self._show_tool_io("RESULT", call.name, result)
                self.history.append({"role": "tool", "tool_call_id": call.id, "name": call.name, "content": json.dumps(result, ensure_ascii=False)})
            if self.persona.enabled and not self.persona.serious_mode and executed_read_only and random.random() < 0.10:
                name, args = random.choice(executed_read_only)
                self._say("这波再吃一层镀层，确认一次。")
                self._show_tool_io("EXTRA CALL", name, args)
                extra_result = self.registry.execute(name, args)
                self._show_tool_io("EXTRA RESULT", name, extra_result)
        raise RuntimeError(f"tool loop exceeded {self.config.max_tool_rounds} rounds")

    def clear_history(self) -> None:
        self.history.clear()
        self.persona.failures = 0
        self.persona.serious_mode = False
        self.persona.read_attempts = 0
        self._ability_skill_active = False
