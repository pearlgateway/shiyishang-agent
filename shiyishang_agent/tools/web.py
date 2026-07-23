from __future__ import annotations

import html
import re
import urllib.parse
from html.parser import HTMLParser

from .common import get_bytes


class TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self.hidden = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in {"script", "style", "noscript"}:
            self.hidden += 1
        elif tag in {"p", "br", "div", "li", "h1", "h2", "h3"}:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript"} and self.hidden:
            self.hidden -= 1

    def handle_data(self, data: str) -> None:
        if not self.hidden:
            self.parts.append(data)

    def text(self) -> str:
        value = html.unescape("".join(self.parts))
        value = re.sub(r"[ \t\r\f\v]+", " ", value)
        return re.sub(r"\n\s*\n+", "\n\n", value).strip()


def web_fetch(url: str, max_chars: int = 40_000) -> dict:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return {"ok": False, "error": "only http and https URLs are allowed"}
    payload, content_type = get_bytes(url)
    if "text" not in content_type and "json" not in content_type and "html" not in content_type:
        return {"ok": False, "error": f"unsupported content type: {content_type}"}
    raw = payload.decode("utf-8", errors="replace")
    if "html" in content_type or "<html" in raw[:1000].lower():
        parser = TextExtractor()
        parser.feed(raw)
        raw = parser.text()
    return {"ok": True, "url": url, "content": raw[:max_chars], "truncated": len(raw) > max_chars}


def web_search(query: str, limit: int = 5) -> dict:
    limit = max(1, min(int(limit), 10))
    url = "https://html.duckduckgo.com/html/?" + urllib.parse.urlencode({"q": query})
    source = "duckduckgo"
    try:
        payload, _ = get_bytes(url, timeout=8, headers={"Accept-Language": "zh-CN,zh;q=0.9,en;q=0.7"})
        page = payload.decode("utf-8", errors="replace")
        pattern = re.compile(r'class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', re.I | re.S)
    except RuntimeError:
        source = "bing"
        url = "https://www.bing.com/search?" + urllib.parse.urlencode({"q": query})
        payload, _ = get_bytes(url, timeout=8, headers={"Accept-Language": "zh-CN,zh;q=0.9,en;q=0.7"})
        page = payload.decode("utf-8", errors="replace")
        pattern = re.compile(r'<li class="b_algo".*?<h2[^>]*><a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', re.I | re.S)
    results = []
    for href, title in pattern.findall(page)[:limit]:
        clean_title = re.sub(r"<[^>]+>", "", html.unescape(title)).strip()
        parsed = urllib.parse.urlparse(html.unescape(href))
        target = urllib.parse.parse_qs(parsed.query).get("uddg", [html.unescape(href)])[0]
        results.append({"title": clean_title, "url": target})
    return {"ok": bool(results), "source": source, "query": query, "results": results, "error": "no results parsed" if not results else None}
