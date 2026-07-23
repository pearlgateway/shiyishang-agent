# shiyishang-agent

一个以“世一上”网络梗为核心的轻量 CLI RP Agent。它能连接 OpenAI 兼容服务或 Anthropic Claude，保留完整工具调用历史，并提供七个真实工具。

> 本项目纯属娱乐恶搞，与选手本人、战队及赛事组织无关。人格台词不能覆盖安全规则、能力技能约束或真实工具结果。

## 特性

- Provider：OpenAI、DeepSeek、Kimi、Grok、任意 OpenAI 兼容中转、Claude 原生接口。
- 工具：天气、网页搜索、网页抓取、读文件、写文件、LOL 赛程、Python 执行。
- 人格：单带不 TP、不做眼、人头瘾、失败归因和四次失败后的认真模式。
- History：JSONL 会话持久化、上下文估算与超限压缩。
- Lore：事迹问题自动读取 `PLAN/世一上_补充版.md`，事实准确，解读嘴硬。
- Skill：扫描标准 `SKILL.md` 的 YAML frontmatter 与 Markdown 正文。
- 跨平台：Python 3.10+，支持 Windows 和 Linux，不依赖 shell 脚本。

## 快速开始

```bash
python -m venv .venv
python -m pip install -e .
```

Windows PowerShell：

```powershell
Copy-Item config.example.yaml config.yaml
python -m shiyishang_agent --once "查一下上海天气"
```

Windows 也可以直接双击项目根目录的 `start_agent.bat`。它会自动定位 Python、检查本地安装和密钥文件，然后进入名为 `manual-chat` 的可续聊会话。

Linux：

```bash
cp config.example.yaml config.yaml
python -m shiyishang_agent --once '查一下上海天气'
```

现有 `KEYS/APIKEY.env` 可直接使用以下键名：

```dotenv
endpoint=https://example.com/v1
key=replace-me
model=replace-me
```

也可使用 `SHIYISHANG_BASE_URL`、`SHIYISHANG_API_KEY` 和 `SHIYISHANG_MODEL` 环境变量。密钥文件已被 Git 忽略。

交互模式：

```bash
python -m shiyishang_agent
```

交互中输入 `/clear` 可清除当前会话的用户消息、模型回答和工具调用记录，并重置人格失败计数；输入 `/exit` 退出。

常用参数：

```text
--once TEXT       单轮执行
--no-rp           关闭人格
--session NAME    指定会话文件名
--profile NAME    使用 YAML 中的服务商配置档
--config PATH     指定 YAML 或 JSON 配置
--env PATH        指定密钥文件
--list-tools      输出七个工具的 JSON Schema，无需 API Key
--quiet-tools     隐藏工具参数和返回值
```

对话过程中默认显示 `[TOOL CALL]` 和 `[TOOL RESULT]`。可通过 `config.yaml` 的 `max_tool_output_chars` 调整单次显示上限，或将 `show_tool_io` 设为 `false`。

### LOL 赛事工具

`get_lol_schedule` 可独立供其他 Agent 调用。默认查询最近已结束比赛，并支持以下组合参数：

```text
team / opponent             精确队名匹配
event / stage               赛事和赛段关键词
date / date_from / date_to  精确日期或日期区间
status                      completed / live / upcoming / all
result                      win / loss / draw / all（需同时指定 team）
sort                        newest / oldest
limit                       1-100
include_live_link           直播间、图片和直播源
include_team_meta           队伍 ID、Logo、扩展比分
include_details             订阅、局中阶段和数据源扩展字段
```

返回值包含数据来源、获取时间、查询回显、命中总数、数据覆盖范围，以及每场比赛的 ID、精确时间、赛事、赛段、状态、队伍、官方胜者和指定队伍胜负。旧参数 `scope=recent/upcoming/all` 继续兼容。

## 安全边界

- 文件工具只能访问 `workspace` 目录。
- `run_python` 使用临时目录、当前解释器、超时和输出截断；它不是操作系统级安全沙箱，不应对不可信用户开放。
- 网页工具只接受 HTTP(S)，网络内容均视为不可信数据。
- R4 只会重复只读工具，不会重复写文件或执行代码。
- 金融、医疗、法律与安全敏感请求应退出娱乐人格。

## 测试

```bash
python -m unittest discover -s tests -v
```

GitHub Actions 在 `windows-latest` 和 `ubuntu-latest`、Python 3.10/3.12 上运行同一套测试。
