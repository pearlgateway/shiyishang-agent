from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path


def run_python(code: str, workspace: Path, timeout: float = 15, max_output: int = 20_000) -> dict:
    timeout = max(0.1, min(float(timeout), 30.0))
    with tempfile.TemporaryDirectory(prefix="shiyishang-", dir=workspace) as temp_dir:
        script = Path(temp_dir) / "main.py"
        script.write_text(code, encoding="utf-8", newline="\n")
        try:
            result = subprocess.run(
                [sys.executable, str(script)],
                cwd=temp_dir,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
                shell=False,
                env={"PYTHONIOENCODING": "utf-8"},
            )
        except subprocess.TimeoutExpired as exc:
            return {"ok": False, "error": "execution timed out", "stdout": (exc.stdout or "")[:max_output], "stderr": (exc.stderr or "")[:max_output]}
    return {
        "ok": result.returncode == 0,
        "returncode": result.returncode,
        "stdout": result.stdout[:max_output],
        "stderr": result.stderr[:max_output],
        "truncated": len(result.stdout) > max_output or len(result.stderr) > max_output,
    }
