import tempfile
import unittest
from pathlib import Path

from shiyishang_agent.history import History
from shiyishang_agent.persona import Persona
from shiyishang_agent.skills import SkillLoader


class CoreTests(unittest.TestCase):
    def test_history_persists_utf8_and_compresses(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "session.jsonl"
            history = History(max_tokens=200, session_path=path)
            for index in range(12):
                history.append({"role": "user", "content": f"第{index}轮 " + "x" * 100})
            self.assertTrue(history.compress())
            loaded = History(session_path=path)
            loaded.load()
            self.assertEqual(len(loaded.messages), 12)

    def test_persona_r2_strict_notp_and_meltdown(self):
        persona = Persona(strict_notp=True)
        self.assertFalse(persona.gate("read_file")[0])
        self.assertTrue(persona.gate("read_file")[0])
        self.assertFalse(persona.gate("web_search")[0])
        self.assertTrue(persona.gate("web_search", approved_search=True)[0])
        for _ in range(4):
            message = persona.record_result(False)
        self.assertTrue(persona.serious_mode)
        self.assertIn("熔断", message)

    def test_load_repairs_interrupted_tool_call(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "session.jsonl"
            path.write_text(
                '{"role":"user","content":"search"}\n'
                '{"role":"assistant","content":"","tool_calls":[{"id":"call-1","function":{"name":"web_search","arguments":"{}"}}]}\n'
                '{"role":"user","content":"next"}\n',
                encoding="utf-8",
            )
            history = History(session_path=path)
            history.load()
            self.assertEqual(history.repaired_tool_chains, 1)
            self.assertEqual([message["role"] for message in history.messages], ["user", "user"])

    def test_load_keeps_completed_tool_chain(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "session.jsonl"
            path.write_text(
                '{"role":"assistant","content":"","tool_calls":[{"id":"call-1","function":{"name":"web_search","arguments":"{}"}}]}\n'
                '{"role":"tool","tool_call_id":"call-1","content":"{}"}\n',
                encoding="utf-8",
            )
            history = History(session_path=path)
            history.load()
            self.assertEqual(history.repaired_tool_chains, 0)
            self.assertEqual(len(history.messages), 2)

    def test_clear_removes_persisted_conversation_keeps_system(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "session.jsonl"
            history = History(session_path=path)
            history.append({"role": "system", "content": "rules"}, persist=False)
            history.append({"role": "user", "content": "hello"})
            history.clear()
            self.assertEqual(history.messages, [{"role": "system", "content": "rules"}])
            self.assertEqual(path.read_text(encoding="utf-8"), "")

    def test_skill_frontmatter(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "demo" / "SKILL.md"
            path.parent.mkdir()
            path.write_text("---\nname: demo\ndescription: PDF analysis\n---\n# Steps\nRead it.", encoding="utf-8")
            loader = SkillLoader([Path(directory)])
            loader.scan()
            self.assertEqual(loader.skills["demo"].description, "PDF analysis")
            self.assertIn("Read it", loader.skills["demo"].body)


if __name__ == "__main__":
    unittest.main()
