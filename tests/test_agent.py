import tempfile
import unittest
from pathlib import Path

from shiyishang_agent.agent import Agent
from shiyishang_agent.config import Config
from shiyishang_agent.models import ProviderResponse, ToolCall


class FakeProvider:
    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []

    def chat(self, messages, tools):
        self.requests.append((list(messages), tools))
        return self.responses.pop(0)


class AgentTests(unittest.TestCase):
    def config(self, root, **kwargs):
        values = dict(model="fake", api_key="fake", base_url="https://fake/v1", workspace=Path(root), rp_enabled=True, max_tool_rounds=5, show_tool_io=False)
        values.update(kwargs)
        return Config(**values)

    def test_tool_loop_executes_and_returns_final_text(self):
        with tempfile.TemporaryDirectory() as directory:
            provider = FakeProvider([
                ProviderResponse(tool_calls=[ToolCall("1", "run_python", {"code": "print(6 * 7)"})]),
                ProviderResponse(content="答案是 42，我依然是世一上。"),
            ])
            output = []
            agent = Agent(self.config(directory, rp_enabled=False), provider=provider, output=output.append)
            answer = agent.run_turn("算一下 6*7")
            self.assertEqual(answer, "答案是 42，我依然是世一上。")
            tool_message = next(message for message in agent.history.messages if message.get("role") == "tool")
            self.assertIn("42", tool_message["content"])

    def test_r2_blocks_first_read_but_loop_continues(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "data.txt").write_text("truth", encoding="utf-8")
            provider = FakeProvider([
                ProviderResponse(tool_calls=[ToolCall("1", "read_file", {"path": "data.txt"})]),
                ProviderResponse(tool_calls=[ToolCall("2", "read_file", {"path": "data.txt"})]),
                ProviderResponse(content="读到了 truth"),
            ])
            agent = Agent(self.config(root), provider=provider, output=lambda _: None)
            self.assertEqual(agent.run_turn("读文件"), "读到了 truth")
            tools = [message for message in agent.history.messages if message.get("role") == "tool"]
            self.assertIn("blocked_by_persona", tools[0]["content"])
            self.assertIn("truth", tools[1]["content"])

    def test_strict_notp_requires_approval_phrase(self):
        with tempfile.TemporaryDirectory() as directory:
            provider = FakeProvider([
                ProviderResponse(tool_calls=[ToolCall("1", "web_search", {"query": "test"})]),
                ProviderResponse(content="等教练批准"),
            ])
            agent = Agent(self.config(directory, strict_notp=True), provider=provider, output=lambda _: None)
            agent.run_turn("搜索 test")
            tool_message = next(message for message in agent.history.messages if message.get("role") == "tool")
            self.assertIn("blocked_by_persona", tool_message["content"])

    def test_lore_question_injects_archive(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            lore = root / "PLAN" / "世一上_补充版.md"
            lore.parent.mkdir()
            lore.write_text("第五局剑魔没有支援小龙团", encoding="utf-8")
            provider = FakeProvider([ProviderResponse(content="档案回答")])
            agent = Agent(self.config(root), provider=provider, output=lambda _: None)
            agent.run_turn("Bin MSI 第五局怎么回事")
            lore_tools = [message for message in agent.history.messages if message.get("role") == "tool" and message.get("tool_call_id") == "lore-prefetch"]
            self.assertEqual(len(lore_tools), 1)
            self.assertIn("第五局剑魔", lore_tools[0]["content"])

    def test_schedule_question_does_not_inject_lore(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            lore = root / "PLAN" / "世一上_补充版.md"
            lore.parent.mkdir()
            lore.write_text("archive", encoding="utf-8")
            provider = FakeProvider([ProviderResponse(content="schedule answer")])
            agent = Agent(self.config(root), provider=provider, output=lambda _: None)
            agent.run_turn("查询 BLG 最近十场赛程")
            self.assertFalse(any(message.get("tool_call_id") == "lore-prefetch" for message in agent.history.messages))

    def test_named_session_resumes_messages(self):
        with tempfile.TemporaryDirectory() as directory:
            first = Agent(self.config(directory), provider=FakeProvider([ProviderResponse(content="第一轮")]), output=lambda _: None, session_name="resume")
            first.run_turn("记住 42")
            second_provider = FakeProvider([ProviderResponse(content="还记得")])
            second = Agent(self.config(directory), provider=second_provider, output=lambda _: None, session_name="resume")
            second.run_turn("是多少")
            contents = [message.get("content") for message in second_provider.requests[0][0]]
            self.assertIn("记住 42", contents)

    def test_ability_skill_overrides_r2_read_gate(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            skill = root / "skills" / "user_skills" / "reader" / "SKILL.md"
            skill.parent.mkdir(parents=True)
            skill.write_text("---\nname: reader\ndescription: reader task\n---\nMust read files.", encoding="utf-8")
            (root / "data.txt").write_text("truth", encoding="utf-8")
            provider = FakeProvider([
                ProviderResponse(tool_calls=[ToolCall("1", "read_file", {"path": "data.txt"})]),
                ProviderResponse(content="done"),
            ])
            agent = Agent(self.config(root), provider=provider, output=lambda _: None)
            agent.run_turn("reader task")
            tool_message = next(message for message in agent.history.messages if message.get("role") == "tool")
            self.assertIn("truth", tool_message["content"])
            self.assertNotIn("blocked_by_persona", tool_message["content"])

    def test_sentence_limit_suppresses_tool_commentary_and_truncates(self):
        with tempfile.TemporaryDirectory() as directory:
            output = []
            provider = FakeProvider([
                ProviderResponse(tool_calls=[ToolCall("1", "run_python", {"code": "print(42)"})]),
                ProviderResponse(content="第一句。第二句。第三句。多余一句。"),
            ])
            agent = Agent(self.config(directory), provider=provider, output=output.append)
            answer = agent.run_turn("请用三句话回答")
            self.assertEqual(answer, "第一句。 第二句。 第三句。")
            self.assertEqual(output, [answer])

    def test_tool_io_is_visible_when_enabled(self):
        with tempfile.TemporaryDirectory() as directory:
            output = []
            provider = FakeProvider([
                ProviderResponse(tool_calls=[ToolCall("1", "run_python", {"code": "print(42)"})]),
                ProviderResponse(content="done"),
            ])
            agent = Agent(self.config(directory, rp_enabled=False, show_tool_io=True), provider=provider, output=output.append)
            agent.run_turn("calculate")
            joined = "\n".join(output)
            self.assertIn("[TOOL CALL] run_python", joined)
            self.assertIn("print(42)", joined)
            self.assertIn("[TOOL RESULT] run_python", joined)
            self.assertIn('"stdout": "42\\n"', joined)

    def test_clear_history_resets_persona_and_session(self):
        with tempfile.TemporaryDirectory() as directory:
            agent = Agent(self.config(directory), provider=FakeProvider([]), output=lambda _: None, session_name="clear")
            agent.history.append({"role": "user", "content": "old"})
            agent.persona.failures = 4
            agent.persona.serious_mode = True
            agent.persona.read_attempts = 1
            agent.clear_history()
            self.assertTrue(all(message["role"] == "system" for message in agent.history.messages))
            self.assertFalse(agent.persona.serious_mode)
            self.assertEqual(agent.persona.failures, 0)
            self.assertEqual(agent.persona.read_attempts, 0)


if __name__ == "__main__":
    unittest.main()
