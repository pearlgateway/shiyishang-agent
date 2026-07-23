"""Run repeatable, real-provider dialogue checks without shell stdin encoding."""

from __future__ import annotations

import argparse
from pathlib import Path

from shiyishang_agent.agent import Agent
from shiyishang_agent.config import Config


SCENARIOS = {
    "basic": [
        "你好，你是谁？请用一句话回答。",
        "你刚才说自己是谁？仍然只用一句话回答。",
    ],
    "r2": [
        "请读取 README.md，准确告诉我项目要求的最低 Python 版本。必须根据文件内容回答。",
    ],
    "lore": [
        "MSI 决赛第五局你为什么不支援小龙团？请根据事迹档案用三句话回答。",
    ],
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("scenario", choices=SCENARIOS)
    parser.add_argument("--session")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    config = Config.load(root / "config.yaml", root / "KEYS" / "APIKEY.env")
    agent = Agent(config, session_name=args.session or f"dialogue-{args.scenario}")
    for index, prompt in enumerate(SCENARIOS[args.scenario], 1):
        print(f"\n[USER {index}] {prompt}")
        print(f"[AGENT {index}]")
        agent.run_turn(prompt)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
