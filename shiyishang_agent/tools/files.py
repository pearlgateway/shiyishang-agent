from __future__ import annotations

from pathlib import Path


def safe_path(workspace: Path, raw_path: str) -> Path:
    root = workspace.resolve()
    candidate = Path(raw_path)
    target = candidate.resolve() if candidate.is_absolute() else (root / candidate).resolve()
    if target != root and root not in target.parents:
        raise ValueError("path escapes the configured workspace")
    return target


def read_file(path: str, workspace: Path, max_chars: int = 100_000) -> dict:
    target = safe_path(workspace, path)
    if not target.is_file():
        return {"ok": False, "error": "file does not exist", "path": str(target)}
    content = target.read_text(encoding="utf-8-sig", errors="replace")
    truncated = len(content) > max_chars
    return {"ok": True, "path": str(target), "content": content[:max_chars], "truncated": truncated}


def write_file(path: str, content: str, workspace: Path, overwrite: bool = False) -> dict:
    target = safe_path(workspace, path)
    if target.exists() and not overwrite:
        return {"ok": False, "error": "file already exists; pass overwrite=true", "path": str(target)}
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8", newline="\n")
    return {"ok": True, "path": str(target), "characters": len(content)}
