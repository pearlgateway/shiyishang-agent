import tempfile
import unittest
from pathlib import Path

from shiyishang_agent.tools import ToolRegistry
from shiyishang_agent.tools.files import read_file, safe_path, write_file
from shiyishang_agent.tools.python_run import run_python
from shiyishang_agent.tools.web import web_fetch


class ToolTests(unittest.TestCase):
    def test_registry_has_exactly_seven_tools(self):
        with tempfile.TemporaryDirectory() as directory:
            registry = ToolRegistry(Path(directory))
            self.assertEqual(len(registry.schemas()), 7)
            self.assertEqual(set(registry.tools), {"get_weather", "web_search", "web_fetch", "read_file", "write_file", "get_lol_schedule", "run_python"})

    def test_file_roundtrip_and_traversal_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            written = write_file("nested/中文.txt", "hello\n世界", root)
            self.assertTrue(written["ok"])
            self.assertEqual(read_file("nested/中文.txt", root)["content"], "hello\n世界")
            with self.assertRaises(ValueError):
                safe_path(root, "../outside.txt")

    def test_write_requires_explicit_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertTrue(write_file("a.txt", "one", root)["ok"])
            self.assertFalse(write_file("a.txt", "two", root)["ok"])
            self.assertTrue(write_file("a.txt", "two", root, overwrite=True)["ok"])

    def test_python_uses_current_interpreter_and_utf8(self):
        with tempfile.TemporaryDirectory() as directory:
            result = run_python("print('世一上')", Path(directory))
            self.assertTrue(result["ok"], result)
            self.assertEqual(result["stdout"].strip(), "世一上")

    def test_python_timeout(self):
        with tempfile.TemporaryDirectory() as directory:
            result = run_python("while True: pass", Path(directory), timeout=0.2)
            self.assertFalse(result["ok"])
            self.assertIn("timed out", result["error"])

    def test_fetch_rejects_non_http(self):
        self.assertFalse(web_fetch("file:///etc/passwd")["ok"])


if __name__ == "__main__":
    unittest.main()
