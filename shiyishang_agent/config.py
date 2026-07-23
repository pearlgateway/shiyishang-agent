from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


ENV_PATTERN = re.compile(r"^\$\{([A-Za-z_][A-Za-z0-9_]*)\}$")


def load_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        value = value.strip().strip('"').strip("'")
        values[name.strip()] = value
    return values


def _expand(value: Any, env: dict[str, str]) -> Any:
    if isinstance(value, dict):
        return {key: _expand(child, env) for key, child in value.items()}
    if isinstance(value, list):
        return [_expand(child, env) for child in value]
    if not isinstance(value, str):
        return value
    match = ENV_PATTERN.match(value)
    if not match:
        return value
    name = match.group(1)
    return os.environ.get(name, env.get(name, ""))


@dataclass(slots=True)
class Config:
    provider: str = "relay"
    model: str = ""
    api_key: str = ""
    base_url: str = ""
    workspace: Path = Path.cwd()
    strict_notp: bool = False
    rp_enabled: bool = True
    max_context_tokens: int = 128_000
    request_timeout: float = 60.0
    max_tool_rounds: int = 12
    show_tool_io: bool = True
    max_tool_output_chars: int = 12_000

    @classmethod
    def load(cls, path: Path | None = None, env_path: Path | None = None, profile: str | None = None) -> "Config":
        project = Path.cwd()
        if path is None:
            path = next((candidate for candidate in (project / "config.yaml", project / "config.yml", project / "config.json") if candidate.is_file()), project / "config.yaml")
        env_path = env_path or project / "KEYS" / "APIKEY.env"
        env = load_env_file(env_path)
        data: dict[str, Any] = {}
        if path.is_file():
            raw = path.read_text(encoding="utf-8-sig")
            data = json.loads(raw) if path.suffix.lower() == ".json" else (yaml.safe_load(raw) or {})
        profiles = data.pop("profiles", {}) or {}
        if profile:
            if profile not in profiles:
                raise ValueError(f"unknown profile: {profile}")
            data.update(profiles[profile] or {})
        data = _expand(data, env)
        aliases = {
            "api_key": os.environ.get("SHIYISHANG_API_KEY", env.get("key", "")),
            "base_url": os.environ.get("SHIYISHANG_BASE_URL", env.get("endpoint", "")),
            "model": os.environ.get("SHIYISHANG_MODEL", env.get("model", "")),
        }
        for key, fallback in aliases.items():
            if not data.get(key):
                data[key] = fallback
        if "workspace" in data:
            workspace = Path(data["workspace"])
            data["workspace"] = (path.parent / workspace).resolve() if not workspace.is_absolute() else workspace.resolve()
        else:
            data["workspace"] = project.resolve()
        valid = set(cls.__dataclass_fields__)
        return cls(**{key: value for key, value in data.items() if key in valid})

    def validate(self) -> None:
        if not self.model:
            raise ValueError("model is not configured")
        if not self.api_key:
            raise ValueError("api_key is not configured")
        if self.provider == "relay" and not self.base_url:
            raise ValueError("relay provider requires base_url")
