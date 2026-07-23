from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .agent import Agent
from .config import Config
from .tools import ToolRegistry


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="shiyishang", description="世一上 RP Agent")
    parser.add_argument("--config", type=Path, help="JSON config path")
    parser.add_argument("--env", type=Path, help="env file path")
    parser.add_argument("--session", help="session name")
    parser.add_argument("--profile", help="configuration profile")
    parser.add_argument("--once", help="run one prompt and exit")
    parser.add_argument("--no-rp", action="store_true", help="disable role-play")
    parser.add_argument("--quiet-tools", action="store_true", help="hide tool arguments and results")
    parser.add_argument("--list-tools", action="store_true", help="print tool schemas")
    return parser


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    args = build_parser().parse_args(argv)
    try:
        config = Config.load(args.config, args.env, args.profile)
        if args.no_rp:
            config.rp_enabled = False
        if args.quiet_tools:
            config.show_tool_io = False
        if args.list_tools:
            print(json.dumps(ToolRegistry(config.workspace).schemas(), ensure_ascii=False, indent=2))
            return 0
        config.validate()
        agent = Agent(config, session_name=args.session)
        if args.once:
            agent.run_turn(args.once)
            return 0
        print("世一上已上线。输入 /exit 结束比赛，/clear 清除当前会话历史。")
        while True:
            try:
                prompt = input("你> ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                return 0
            if prompt.lower() in {"/exit", "/quit", "exit", "quit"}:
                return 0
            if prompt.lower() == "/clear":
                agent.clear_history()
                print("历史记录已清除。这把重开，我还是世一上。")
                continue
            if prompt:
                agent.run_turn(prompt)
    except (ValueError, RuntimeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
