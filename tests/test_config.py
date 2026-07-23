import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from shiyishang_agent.config import Config, load_env_file


class ConfigTests(unittest.TestCase):
    def test_env_and_relative_workspace(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "keys.env").write_text("endpoint=https://relay.test/v1\nkey=secret\nmodel=test-model\n", encoding="utf-8")
            (root / "config.json").write_text(json.dumps({"workspace": "work"}), encoding="utf-8")
            config = Config.load(root / "config.json", root / "keys.env")
            self.assertEqual(config.model, "test-model")
            self.assertEqual(config.workspace, (root / "work").resolve())

    def test_environment_overrides_env_file(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {"SHIYISHANG_MODEL": "override"}):
            path = Path(directory) / "keys.env"
            path.write_text("model=file-model\n", encoding="utf-8")
            self.assertEqual(Config.load(Path(directory) / "missing.json", path).model, "override")

    def test_utf8_bom_env(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "x.env"
            path.write_text("\ufeffkey=value\n", encoding="utf-8")
            self.assertEqual(load_env_file(path)["key"], "value")

    def test_yaml_profile_and_environment_expansion(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config_path = root / "config.yaml"
            config_path.write_text("provider: relay\nmodel: base\nprofiles:\n  rank:\n    provider: deepseek\n    model: ${MODEL_FROM_ENV}\n", encoding="utf-8")
            with patch.dict(os.environ, {"MODEL_FROM_ENV": "profile-model"}):
                config = Config.load(config_path, root / "missing.env", "rank")
            self.assertEqual(config.provider, "deepseek")
            self.assertEqual(config.model, "profile-model")


if __name__ == "__main__":
    unittest.main()
