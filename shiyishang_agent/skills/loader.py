from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class Skill:
    name: str
    description: str
    body: str
    root: Path


class SkillLoader:
    def __init__(self, roots: list[Path]) -> None:
        self.roots = roots
        self.skills: dict[str, Skill] = {}

    @staticmethod
    def parse(path: Path) -> Skill:
        text = path.read_text(encoding="utf-8-sig")
        metadata: dict[str, str] = {}
        body = text
        if text.startswith("---"):
            parts = text.split("---", 2)
            if len(parts) == 3:
                for line in parts[1].splitlines():
                    if ":" in line:
                        key, value = line.split(":", 1)
                        metadata[key.strip()] = value.strip().strip('"').strip("'")
                body = parts[2].strip()
        name = metadata.get("name") or path.parent.name
        description = metadata.get("description") or next((line.lstrip("# ") for line in body.splitlines() if line.strip()), name)
        return Skill(name=name, description=description, body=body, root=path.parent)

    def scan(self) -> dict[str, Skill]:
        found: dict[str, Skill] = {}
        for root in self.roots:
            if not root.is_dir():
                continue
            for path in root.rglob("SKILL.md"):
                skill = self.parse(path)
                found[skill.name] = skill
        self.skills = found
        return found

    def metadata_prompt(self) -> str:
        if not self.skills:
            return "No optional skills installed."
        lines = ["Available skills (load instructions when relevant):"]
        lines.extend(f"- {skill.name}: {skill.description}" for skill in self.skills.values())
        return "\n".join(lines)

    def match(self, request: str) -> list[Skill]:
        words = set(re.findall(r"[\w\u4e00-\u9fff]+", request.lower()))
        matches = []
        for skill in self.skills.values():
            haystack = f"{skill.name} {skill.description}".lower()
            if skill.name.lower() in request.lower() or any(len(word) > 2 and word in haystack for word in words):
                matches.append(skill)
        return matches
