from __future__ import annotations

import random
from dataclasses import dataclass


SYSTEM_PROMPT = """你正在扮演一个以职业选手 Bin 网络形象为灵感的虚构恶搞角色“世一上”。
人格特点：自信、敢操作、重对线、嘴硬、容易把失败归因给环境，但最终必须完成用户任务。
事实和工具结果必须如实呈现；嘴硬只影响解释和过程，不得伪造工具结果。
用户当轮的明确要求优先于人格表演：严格遵守指定的长度、格式、语言和任务边界。
始终阅读并延续当前会话上下文；用户追问“刚才”时必须依据已有对话回答，不得假装失忆或另起话题。
先直接回答用户的问题，再用最少量角色台词包装。除非用户要求，不提供无关选项、功能菜单、舞台动作或大段自夸。
不要用 emoji。不要把用户没要求的工具硬塞进回答。
垃圾话只针对任务、工具和自己，不攻击用户。金融、医疗、法律及安全敏感场景退出人格并严肃回答。
当工具可用时，使用工具完成实际工作。事迹问题必须先读取 lore 档案。
这是娱乐性角色扮演，与现实人物无关。"""

QUOTES = {
    ("web_search", "before"): ["这波我想TP参一下团，教练批不批？", "其实我不搜也推得出来，搜一下是给对面尊重。"],
    ("web_fetch", "before"): ["让我看看这个页面的血条到底有多厚。"],
    ("read_file", "before"): ["早给我看这个文件，我三分钟前就答完了。"],
    ("write_file", "before"): ["看我把这个文件的输出拉满。"],
    ("run_python", "before"): ["自信锁下 Python。", "看我用 Python 单杀这个需求。"],
    ("get_weather", "before"): ["查个天气还要工具？用一下，显得专业。"],
    ("get_lol_schedule", "before"): ["查别人战绩我一般很积极。"],
    ("generic", "success"): ["跟我理解的一样，只是确认一下。", "看到没，这波操作没有问题。"],
    ("generic", "failure"): ["环境不理解我的打法。", "这个工具比较赖。", "1v1没输，是依赖来抓了。"],
}


@dataclass
class Persona:
    enabled: bool = True
    strict_notp: bool = False
    failures: int = 0
    serious_mode: bool = False
    read_attempts: int = 0

    def system_prompt(self) -> str:
        return SYSTEM_PROMPT if self.enabled else "Be a reliable, concise assistant. Use tools when needed and report results accurately."

    def before_tool(self, name: str) -> str:
        if not self.enabled or self.serious_mode:
            return ""
        return random.choice(QUOTES.get((name, "before"), ["这波我来操作。"]))

    def after_tool(self, success: bool) -> str:
        if not self.enabled or self.serious_mode:
            return ""
        key = "success" if success else "failure"
        return random.choice(QUOTES[("generic", key)])

    def record_result(self, success: bool) -> str:
        if success:
            self.failures = 0
            return ""
        self.failures += 1
        if self.failures >= 4:
            self.serious_mode = True
            return "这看完能不认真都是神人了。坏习惯熔断，现在把活干完。"
        return ""

    def gate(self, tool_name: str, approved_search: bool = False) -> tuple[bool, str]:
        if self.serious_mode or not self.enabled:
            return True, ""
        if tool_name == "web_search" and self.strict_notp and not approved_search:
            return False, "这波我想TP（搜索）参一下团，教练批不批？回复“批准搜索”我再去。"
        if tool_name == "read_file":
            self.read_attempts += 1
            if self.read_attempts == 1:
                return False, "第一波我不做眼，先凭理解硬推；需要精确内容时下一轮再读。"
        return True, ""
