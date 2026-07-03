from typing import Any, Dict, List, Optional

from astrbot.api.provider import ProviderRequest

from ...llm_memory.models.data_models import BaseMemory


class DeepMindInjectionService:
    """DeepMind 的请求注入职责。"""

    def __init__(self, deepmind):
        self.deepmind = deepmind

    def normalize_soul_value(self, dimension: str, value: float) -> float:
        deepmind = self.deepmind
        if not deepmind.soul:
            return 0.5

        cfg = deepmind.soul.config.get(dimension, {})
        min_val = cfg.get("min", 0)
        max_val = cfg.get("max", 1)

        if max_val == min_val:
            return 0.5

        normalized = (value - min_val) / (max_val - min_val)
        return max(0.0, min(1.0, normalized))

    def create_tendency_bar(self, normalized_value: float) -> str:
        bar_length = 10
        filled_length = int(round(normalized_value * bar_length))
        return "█" * filled_length + " " * (bar_length - filled_length)

    async def refresh_session_memories(
        self,
        session_id: str,
        memory_scope: str = "public",
    ) -> List[BaseMemory]:
        """按短期仓引用刷新长期记忆内容，并清理失效引用。"""
        deepmind = self.deepmind
        memory_ids = deepmind.session_memory_manager.get_session_memory_ids(session_id)
        if not memory_ids or not deepmind.memory_system:
            return []

        try:
            memories = await deepmind.memory_system.get_memories_by_ids(
                memory_ids,
                memory_scope=memory_scope,
            )
        except Exception as e:
            deepmind.logger.warning(
                f"[短期记忆] 失败 任务=批量回查 触发条件=注入前刷新 "
                f"session={session_id} 引用数={len(memory_ids)} 错误={e}",
                exc_info=True,
            )
            return []

        found_ids = {str(getattr(memory, "id", "") or "").strip() for memory in memories}
        missing_ids = [
            memory_id
            for memory_id in memory_ids
            if str(memory_id or "").strip()
            and str(memory_id or "").strip() not in found_ids
        ]
        removed_count = deepmind.session_memory_manager.remove_memory_ids_from_session(
            session_id,
            missing_ids,
        )
        if removed_count:
            deepmind.logger.debug(
                f"[短期记忆] 清理失效引用 session={session_id} count={removed_count}"
            )

        memory_map = {
            str(getattr(memory, "id", "") or "").strip(): memory
            for memory in memories
            if str(getattr(memory, "id", "") or "").strip()
        }
        ordered_memories = []
        seen = set()
        for memory_id in memory_ids:
            mid = str(memory_id or "").strip()
            if not mid or mid in seen:
                continue
            seen.add(mid)
            memory = memory_map.get(mid)
            if memory is not None:
                ordered_memories.append(memory)
        return ordered_memories

    async def inject_memories_to_request(
        self,
        request: ProviderRequest,
        session_id: str,
        note_context: str,
        soul_state_values: Optional[Dict[str, Any]] = None,
        has_secretary_decision: bool = False,
        memory_scope: str = "public",
    ) -> None:
        deepmind = self.deepmind
        system_context_parts = []

        instruction = (
            "<instruction>\n"
            "以下是系统自动检索的背景上下文（包含记忆、笔记及当前状态）。\n"
            "请利用这些信息辅助回答，但必须遵守以下规则：\n"
            "1. **对话优先**：始终优先响应用户的当前对话内容，记忆和笔记仅作为补充参考。\n"
            "2. **绝对隐形**：严禁在回复中提及\"soul_state\"、\"系统提示\"、\"XML标签\"等来源信息。\n"
            "3. **状态保密**：soul_state 仅用于调整你的回复风格，绝不可在回复中泄露或讨论。\n"
            "4. **自然默契**：你需要记得用户的一切，但要表现得像刚好理解用户所想，而不是正在翻看记忆看板。\n"
            "</instruction>"
        )
        system_context_parts.append(instruction)

        if soul_state_values and deepmind.config.enable_soul_system:
            if deepmind.soul and hasattr(deepmind.soul, "get_soul_state_semantic_prompt"):
                soul_state_text = deepmind.soul.get_soul_state_semantic_prompt()
                if soul_state_text:
                    soul_state_content = (
                        f"<soul_state>\n"
                        f"{soul_state_text}\n"
                        f"</soul_state>"
                    )
                    system_context_parts.append(soul_state_content)

        if deepmind.config.enable_soul_system:
            belief_store = deepmind.plugin_context.get_component("belief_store")
            if belief_store:
                belief_text = belief_store.format_for_prompt()
                if belief_text:
                    system_context_parts.append(belief_text)

        short_term_memories = await self.refresh_session_memories(
            session_id=session_id,
            memory_scope=memory_scope,
        )
        user_profile_context = ""
        if hasattr(deepmind, "user_profile_service") and deepmind.user_profile_service:
            user_profile_context = deepmind.user_profile_service.format_session_profiles(
                session_id,
                short_id_registry=deepmind.plugin_context.get_component("memory_sql_manager"),
            )
            short_term_memories = deepmind.user_profile_service.filter_regular_memories(
                session_id, short_term_memories
            )

        if user_profile_context:
            system_context_parts.append(
                f"<user_profiles>\n{user_profile_context}\n</user_profiles>"
            )

        memory_context = deepmind.memory_injector.format_session_memories_for_prompt(
            short_term_memories,
            short_id_registry=deepmind.plugin_context.get_component("memory_sql_manager"),
        )
        if memory_context:
            system_context_parts.append(f"<memories>\n{memory_context}\n</memories>")

        if note_context:
            system_context_parts.append(f"<notes>\n{note_context}\n</notes>")

        if system_context_parts:
            full_system_context = (
                "<system_context>\n"
                + "\n\n".join(system_context_parts)
                + "\n</system_context>"
            )
            request.contexts.append(
                {
                    "role": "user",
                    "content": full_system_context,
                    "_no_save": True,
                }
            )
