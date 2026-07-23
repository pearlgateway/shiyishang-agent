from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from .esports import get_lol_schedule
from .files import read_file, write_file
from .python_run import run_python
from .weather import get_weather
from .web import web_fetch, web_search


@dataclass(slots=True)
class Tool:
    name: str
    description: str
    parameters: dict[str, Any]
    handler: Callable[..., dict[str, Any]]

    def schema(self) -> dict[str, Any]:
        return {"name": self.name, "description": self.description, "parameters": self.parameters}


class ToolRegistry:
    def __init__(self, workspace: Path, timeout: float = 30) -> None:
        self.workspace = workspace.resolve()
        self.timeout = timeout
        obj = {"type": "object", "properties": {}}
        self.tools = {
            "get_weather": Tool("get_weather", "查询城市当前天气", {"type": "object", "properties": {"city": {"type": "string"}}, "required": ["city"]}, get_weather),
            "web_search": Tool("web_search", "搜索公开网页", {"type": "object", "properties": {"query": {"type": "string"}, "limit": {"type": "integer", "minimum": 1, "maximum": 10}}, "required": ["query"]}, web_search),
            "web_fetch": Tool("web_fetch", "读取网页正文", {"type": "object", "properties": {"url": {"type": "string"}, "max_chars": {"type": "integer"}}, "required": ["url"]}, web_fetch),
            "read_file": Tool("read_file", "读取工作区内的文本文件", {"type": "object", "properties": {"path": {"type": "string"}, "max_chars": {"type": "integer"}}, "required": ["path"]}, read_file),
            "write_file": Tool("write_file", "写入工作区内的文本文件", {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}, "overwrite": {"type": "boolean"}}, "required": ["path", "content"]}, write_file),
            "get_lol_schedule": Tool("get_lol_schedule", "查询英雄联盟赛果、进行中比赛和未来赛程，支持队伍、对手、赛事、赛段、日期区间、状态和胜负组合筛选；默认返回最近已结束比赛", {"type": "object", "properties": {
                "team": {"type": "string", "description": "队伍全名，大小写不敏感且精确匹配，如 BLG"},
                "opponent": {"type": "string", "description": "对手全名，精确匹配"},
                "event": {"type": "string", "description": "赛事名称关键词，如 EWC、季中冠军赛"},
                "stage": {"type": "string", "description": "具体赛段关键词"},
                "date": {"type": "string", "description": "精确日期 YYYY-MM-DD"},
                "date_from": {"type": "string", "description": "起始日期 YYYY-MM-DD，包含当天"},
                "date_to": {"type": "string", "description": "结束日期 YYYY-MM-DD，包含当天"},
                "status": {"type": "string", "enum": ["completed", "live", "upcoming", "all"], "description": "比赛状态，默认 completed"},
                "result": {"type": "string", "enum": ["win", "loss", "draw", "all"], "description": "指定队伍的赛果；使用 win/loss/draw 时必须提供 team"},
                "sort": {"type": "string", "enum": ["newest", "oldest"], "description": "排序；已结束比赛默认 newest，其他默认 oldest"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 100},
                "include_live_link": {"type": "boolean", "description": "返回直播间、图片和直播源信息"},
                "include_team_meta": {"type": "boolean", "description": "返回队伍 ID、Logo 和扩展比分，默认 true"},
                "include_details": {"type": "boolean", "description": "返回订阅、局中阶段、评分业务键和数据源扩展字段"},
                "scope": {"type": "string", "enum": ["recent", "upcoming", "all"], "description": "旧版兼容参数；新调用请使用 status"}
            }}, get_lol_schedule),
            "run_python": Tool("run_python", "在隔离临时目录运行 Python 代码", {"type": "object", "properties": {"code": {"type": "string"}, "timeout": {"type": "number"}}, "required": ["code"]}, run_python),
        }

    def schemas(self) -> list[dict[str, Any]]:
        return [tool.schema() for tool in self.tools.values()]

    def execute(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        tool = self.tools.get(name)
        if not tool:
            return {"ok": False, "error": f"unknown tool: {name}"}
        try:
            kwargs = dict(arguments)
            if name in {"read_file", "write_file"}:
                kwargs["workspace"] = self.workspace
            if name == "run_python":
                kwargs["workspace"] = self.workspace
                kwargs.setdefault("timeout", min(self.timeout, 15))
            return tool.handler(**kwargs)
        except TypeError as exc:
            return {"ok": False, "error": f"invalid arguments: {exc}"}
        except Exception as exc:
            return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}

    def execute_json(self, name: str, arguments: dict[str, Any]) -> str:
        return json.dumps(self.execute(name, arguments), ensure_ascii=False)
