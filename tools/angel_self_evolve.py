"""
angel_self_evolve - OC 自改工具

自白对话的落地动作。管理员同意后，OC 调用此工具将认知写入核心信念。
"""

from datetime import datetime
from dataclasses import dataclass, field

from astrbot.api import FunctionTool
from astrbot.api.event import AstrMessageEvent

try:
    from astrbot.api import logger
except ImportError:
    import logging
    logger = logging.getLogger(__name__)


@dataclass
class AngelSelfEvolveTool(FunctionTool):
    name: str = "angel_self_evolve"
    description: str = (
        "将自省后形成的认知写入核心信念，或修改底层行为准则。"
        "只有在与管理员讨论并获得同意后才能调用。"
        "对话中管理员明确说「去改吧」「可以」「行」等表示同意时，才可以调用此工具。"
    )
    parameters: dict = field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["add", "modify", "remove"],
                    "description": (
                        "操作类型。add=新增一条核心信念；"
                        "modify=修改一条已有信念；"
                        "remove=移除一条已有信念。"
                    ),
                },
                "content": {
                    "type": "string",
                    "description": "信念内容正文。",
                },
                "reasoning": {
                    "type": "string",
                    "description": "为什么要这么改，存档用，不会注入到 prompt。",
                },
                "belief_id": {
                    "type": "string",
                    "description": "目标信念 ID，modify/remove 时必填。",
                },
            },
            "required": ["action", "content", "reasoning"],
        }
    )

    def __post_init__(self):
        self.logger = logger

    async def run(
        self,
        event: AstrMessageEvent,
        action: str,
        content: str,
        reasoning: str,
        belief_id: str = "",
    ):
        action = str(action or "").strip().lower()
        content = str(content or "").strip()
        reasoning = str(reasoning or "").strip()
        belief_id = str(belief_id or "").strip()

        if action not in ("add", "modify", "remove"):
            return "错误：action 必须是 add、modify 或 remove。"

        if not content:
            return "错误：content 不能为空。"

        if action in ("modify", "remove") and not belief_id:
            return f"错误：action 为 {action} 时，belief_id 为必填。"

        if not hasattr(event, "plugin_context") or event.plugin_context is None:
            return "错误：无法获取插件上下文。"

        plugin_context = event.plugin_context

        if not self._is_admin_context(event):
            self.logger.warning(f"非管理员会话中尝试调用 {self.name}")
            return "未经管理员同意，无法修改核心信念。请先与管理员讨论并获得同意。"

        try:
            belief_store = plugin_context.get_component("belief_store")
            if not belief_store:
                return "错误：核心信念存储不可用，功能尚未启用。"

            if action == "add":
                bid = belief_store.add_belief(
                    content=content,
                    origin=f"自白自省 + 管理员批准 | {datetime.now().strftime('%Y-%m-%d')}",
                    approved_by="admin",
                    reasoning=reasoning,
                )
                self.logger.info(
                    f"{self.name}: 新增信念 belief_id={bid} content=「{content[:30]}」"
                )
                return (
                    f"已将新的核心信念写入：「{content}」"
                    f"（ID: {bid}，原因为: {reasoning[:50]}）"
                )

            elif action == "modify":
                if not belief_store.get_belief(belief_id):
                    return f"错误：未找到信念 ID「{belief_id}」。"
                belief_store.modify_belief(
                    belief_id=belief_id,
                    content=content,
                    reasoning=reasoning,
                )
                self.logger.info(
                    f"{self.name}: 修改信念 belief_id={belief_id} content=「{content[:30]}」"
                )
                return f"已修改信念（ID: {belief_id}）→「{content}」"

            elif action == "remove":
                if not belief_store.get_belief(belief_id):
                    return f"错误：未找到信念 ID「{belief_id}」。"
                belief_store.remove_belief(belief_id)
                self.logger.info(f"{self.name}: 移除信念 belief_id={belief_id}")
                return f"已移除信念（ID: {belief_id}）"

        except Exception as e:
            self.logger.error(f"{self.name}: 执行失败: {e}", exc_info=True)
            return f"信念更新失败：{str(e)}"

    @staticmethod
    @staticmethod
    def _is_admin_context(event) -> bool:
        try:
            if bool(event.is_admin()):
                return True
        except Exception:
            pass
        try:
            sender_id = str(event.get_sender_id() or "").strip()
            plugin_ctx = getattr(event, "plugin_context", None)
            if plugin_ctx and sender_id:
                astrbot_ctx = plugin_ctx.get_astrbot_context()
                if astrbot_ctx:
                    global_cfg = astrbot_ctx.get_config()
                    if isinstance(global_cfg, dict):
                        for admin_id in global_cfg.get("admins_id", []) or []:
                            if str(admin_id).strip() == sender_id:
                                return True
        except Exception:
            pass
        return False
