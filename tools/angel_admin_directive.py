"""
angel_admin_directive - 管理员指令工具

管理员在对话中直接下达指令，OC 当场调用工具执行策略/画像/信念的修改。
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
class AngelAdminDirectiveTool(FunctionTool):
    name: str = "angel_admin_directive"
    description: str = (
        "根据管理员的直接指示，更新对某个用户的相处策略、用户画像，或直接写入一条核心信念。"
        "仅管理员有权调用，非管理员调用将返回权限不足。"
    )
    parameters: dict = field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "target_type": {
                    "type": "string",
                    "enum": ["strategy", "profile", "belief"],
                    "description": (
                        "指令类型。strategy=修改对某用户的相处策略；"
                        "profile=补充某用户的画像信息；"
                        "belief=直接写入一条核心信念。"
                    ),
                },
                "target_user": {
                    "type": "string",
                    "description": "目标用户名或昵称。target_type 为 strategy/profile 时必填。",
                },
                "content": {
                    "type": "string",
                    "description": "要写入的具体内容。",
                },
            },
            "required": ["target_type", "content"],
        }
    )

    def __post_init__(self):
        self.logger = logger

    async def run(
        self,
        event: AstrMessageEvent,
        target_type: str,
        content: str,
        target_user: str = "",
    ):
        target_type = str(target_type or "").strip().lower()
        content = str(content or "").strip()
        target_user = str(target_user or "").strip()

        if not content:
            return "错误：content 不能为空。"

        if target_type in ("strategy", "profile") and not target_user:
            return f"错误：target_type 为 {target_type} 时，target_user 为必填。"

        if not hasattr(event, "plugin_context") or event.plugin_context is None:
            return "错误：无法获取插件上下文。"

        plugin_context = event.plugin_context

        if not self._is_admin(event):
            self.logger.warning(f"非管理员用户尝试调用 {self.name}")
            return "权限不足：此工具仅供管理员使用。"

        resolved_id = target_user
        if target_type in ("strategy", "profile") and target_user:
            resolved_id = self._resolve_user_id(plugin_context, target_user)
            if resolved_id != target_user:
                self.logger.info(f"{self.name}: target_user={target_user} → resolved_id={resolved_id}")

        try:
            if target_type == "strategy":
                store = plugin_context.get_component("strategy_store")
                if not store:
                    return "错误：策略卡存储不可用。"
                store.set_strategy(
                    user_id=resolved_id,
                    strategy=content,
                    source=f"管理员指令 | {datetime.now().strftime('%Y-%m-%d')}",
                )
                self.logger.info(
                    f"{self.name}: 已更新策略 target_user={resolved_id} content=「{content[:30]}」"
                )
                return f"已更新对 {resolved_id} 的相处策略：「{content}」"

            elif target_type == "profile":
                memory_runtime = plugin_context.get_component("memory_runtime")
                if not memory_runtime:
                    return "错误：记忆服务不可用。"
                memory_scope = await plugin_context.resolve_memory_scope_from_event(event)
                mid = await memory_runtime.remember(
                    memory_type="knowledge",
                    judgment=f"{target_user}: {content}",
                    reasoning=f"管理员手动补充用户画像 ({datetime.now().strftime('%Y-%m-%d')})",
                    tags=[f"profile_attribute:{target_user}", "画像"],
                    strength=60,
                    is_active=True,
                    memory_scope=memory_scope,
                )
                self.logger.info(
                    f"{self.name}: 已补充画像 target_user={target_user} memory_id={mid}"
                )
                return f"已补充 {target_user} 的画像：「{content}」"

            elif target_type == "belief":
                belief_store = plugin_context.get_component("belief_store")
                if not belief_store:
                    return "错误：核心信念存储不可用。"
                belief_store.add_belief(
                    content=content,
                    origin=f"管理员直接指令 | {datetime.now().strftime('%Y-%m-%d')}",
                    approved_by="admin",
                )
                self.logger.info(f"{self.name}: 已写入核心信念 content=「{content[:30]}」")
                return f"已写入核心信念：「{content}」"

            else:
                return f"错误：不支持 target_type「{target_type}」。"

        except Exception as e:
            self.logger.error(f"{self.name}: 执行失败: {e}", exc_info=True)
            return f"指令执行失败：{str(e)}"

    @staticmethod
    def _is_admin(event) -> bool:
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

    @staticmethod
    def _resolve_user_id(plugin_context, target_name: str) -> str:
        """将昵称/用户名映射到实际 user_id，如无法解析则返回原名。"""
        deepmind = plugin_context.get_component("deepmind")
        if not deepmind or not hasattr(deepmind, "user_profile_service"):
            return target_name
        profile_service = deepmind.user_profile_service
        for session_id, name_map in profile_service._session_user_names.items():
            for uid, nickname in name_map.items():
                if nickname and nickname.lower() == target_name.lower():
                    return uid
        for session_id, name_map in profile_service._session_user_names.items():
            for uid, nickname in name_map.items():
                if nickname and target_name.lower() in nickname.lower():
                    return uid
        return target_name
