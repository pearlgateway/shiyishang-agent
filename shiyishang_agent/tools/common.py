from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any


USER_AGENT = "shiyishang-agent/0.1 (+cross-platform CLI)"


def get_bytes(url: str, timeout: float = 20, headers: dict[str, str] | None = None) -> tuple[bytes, str]:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, **(headers or {})})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read(), response.headers.get("Content-Type", "")
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"HTTP {exc.code} for {url}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"network error: {exc.reason}") from exc


def get_json(url: str, timeout: float = 20, headers: dict[str, str] | None = None) -> Any:
    payload, _ = get_bytes(url, timeout, headers)
    return json.loads(payload.decode("utf-8-sig"))
