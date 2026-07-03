from __future__ import annotations

from collections import defaultdict
import time
from typing import Any, Dict, Iterable, List, Sequence, Tuple

from ...llm_memory.models.data_models import BaseMemory
from ...llm_memory.utils.user_profile import (
    PROFILE_ATTRIBUTE_TAGS,
    extract_profile_attribute_from_tags,
    extract_user_id_from_tags,
    is_user_id_tag,
    normalize_judgment,
)
from ..utils.memory_formatter import MemoryFormatter


class UserProfileService:
    """维护会话当前批次用户画像上下文。"""

    def __init__(self, memory_sql_manager=None, logger=None):
        self.memory_sql_manager = memory_sql_manager
        self.logger = logger
        self._session_user_ids: Dict[str, List[str]] = {}
        self._session_user_names: Dict[str, Dict[str, str]] = {}
        self._session_profiles: Dict[str, List[BaseMemory]] = {}
        self._session_strategies: Dict[str, Dict[str, Dict[str, str]]] = {}
        self._session_intimacies: Dict[str, Dict[str, float]] = {}

    def set_memory_sql_manager(self, memory_sql_manager) -> None:
        self.memory_sql_manager = memory_sql_manager

    @staticmethod
    def extract_current_user_ids(
        chat_records: Sequence[Dict[str, Any]] | None,
        fallback_sender_id: str = "",
    ) -> List[str]:
        user_ids, _ = UserProfileService.extract_current_users(
            chat_records=chat_records,
            fallback_sender_id=fallback_sender_id,
        )
        return user_ids

    @staticmethod
    def extract_current_users(
        chat_records: Sequence[Dict[str, Any]] | None,
        fallback_sender_id: str = "",
        fallback_sender_name: str = "",
    ) -> Tuple[List[str], Dict[str, str]]:
        seen = set()
        user_ids: List[str] = []
        user_names: Dict[str, str] = {}

        for msg in chat_records or []:
            if not isinstance(msg, dict):
                continue
            role = str(msg.get("role", "") or "").strip()
            if role != "user":
                continue
            sender_id = str(msg.get("sender_id", "") or "").strip()
            if not UserProfileService._is_valid_user_id(sender_id):
                continue
            sender_name = str(msg.get("sender_name", "") or "").strip()
            if sender_id not in seen:
                seen.add(sender_id)
                user_ids.append(sender_id)
            if sender_name:
                user_names[sender_id] = sender_name

        fallback = str(fallback_sender_id or "").strip()
        if not user_ids and UserProfileService._is_valid_user_id(fallback):
            user_ids.append(fallback)
            fallback_name = str(fallback_sender_name or "").strip()
            if fallback_name:
                user_names[fallback] = fallback_name

        return user_ids, user_names

    @staticmethod
    def _is_valid_user_id(user_id: str) -> bool:
        text = str(user_id or "").strip()
        if not text or text in {"Unknown", "unknown", "assistant", "user"}:
            return False
        return is_user_id_tag(text)

    async def refresh_session_profiles(
        self,
        session_id: str,
        chat_records: Sequence[Dict[str, Any]] | None,
        fallback_sender_id: str = "",
        fallback_sender_name: str = "",
        memory_scope: str = "public",
    ) -> List[BaseMemory]:
        sid = str(session_id or "").strip()
        if not sid:
            return []

        user_ids, user_names = self.extract_current_users(
            chat_records=chat_records,
            fallback_sender_id=fallback_sender_id,
            fallback_sender_name=fallback_sender_name,
        )
        self._session_user_ids[sid] = user_ids
        self._session_user_names[sid] = user_names

        if not user_ids or self.memory_sql_manager is None:
            self._session_profiles[sid] = []
            return []

        started_at = time.time()
        try:
            profiles = await self.memory_sql_manager.recall_user_profiles(
                user_ids=user_ids,
                memory_scope=memory_scope,
            )
        except Exception as e:
            if self.logger:
                self.logger.warning(
                    f"[用户画像] 失败 任务=画像召回 触发条件=刷新当前批次画像 "
                    f"session={sid} 用户数={len(user_ids)} "
                    f"耗时毫秒={int((time.time() - started_at) * 1000)} 错误={e}",
                    exc_info=True,
                )
            profiles = []

        profiles = self._deduplicate_profiles(profiles)
        self._session_profiles[sid] = profiles
        return profiles

    def get_session_profile_memories(self, session_id: str) -> List[BaseMemory]:
        return list(self._session_profiles.get(str(session_id or "").strip(), []))

    def get_profile_dedupe_keys(self, session_id: str) -> Tuple[set[str], set[str]]:
        profile_ids = set()
        judgments = set()
        for memory in self.get_session_profile_memories(session_id):
            memory_id = str(getattr(memory, "id", "") or "").strip()
            if memory_id:
                profile_ids.add(memory_id)
            normalized = normalize_judgment(getattr(memory, "judgment", ""))
            if normalized:
                judgments.add(normalized)
        return profile_ids, judgments

    def filter_regular_memories(
        self, session_id: str, memories: Iterable[Any]
    ) -> List[Any]:
        profile_ids, judgments = self.get_profile_dedupe_keys(session_id)
        if not profile_ids and not judgments:
            return list(memories or [])

        filtered = []
        for memory in memories or []:
            memory_id = str(getattr(memory, "id", "") or "").strip()
            if memory_id and memory_id in profile_ids:
                continue
            normalized = normalize_judgment(getattr(memory, "judgment", ""))
            if normalized and normalized in judgments:
                continue
            filtered.append(memory)
        return filtered

    def format_session_profiles(self, session_id: str, short_id_registry=None) -> str:
        profiles = self.get_session_profile_memories(session_id)
        if not profiles:
            return ""

        grouped: Dict[str, List[BaseMemory]] = defaultdict(list)
        user_names = self._session_user_names.get(
            str(session_id or "").strip(), {}
        )
        for memory in profiles:
            user_id = extract_user_id_from_tags(getattr(memory, "tags", []))
            if not user_id or not extract_profile_attribute_from_tags(getattr(memory, "tags", [])):
                continue
            grouped[user_id].append(memory)

        lines = ["[用户画像]"]
        for user_id in self._session_user_ids.get(str(session_id or "").strip(), []):
            if user_id not in grouped:
                continue
            nickname = user_names.get(user_id, "")
            header = f"{nickname}（{user_id}）" if nickname else user_id
            lines.append(f"\n[{header}]")
            for memory in grouped[user_id]:
                short_id = ""
                if short_id_registry is not None:
                    mem_id = str(getattr(memory, "id", "") or "").strip()
                    if mem_id:
                        short_id = short_id_registry.get_short_id(mem_id)
                lines.append(f"\n{MemoryFormatter.format_single_memory(memory, short_id=short_id)}")
            strategy_text = self._format_user_strategy(user_id)
            if strategy_text:
                lines.append(strategy_text)
            intimacy_text = self._format_user_intimacy(user_id)
            if intimacy_text:
                lines.append(intimacy_text)
        return "".join(lines)

    def set_user_strategy(
        self,
        user_id: str,
        strategy: str,
        source: str = "",
    ) -> None:
        sid = "global"
        if sid not in self._session_strategies:
            self._session_strategies[sid] = {}
        self._session_strategies[sid][user_id] = {
            "strategy": strategy,
            "source": source,
            "updated_at": str(int(time.time())),
        }

    def get_user_strategy(self, user_id: str) -> Dict[str, str]:
        sid = "global"
        return self._session_strategies.get(sid, {}).get(user_id, {})

    def set_user_intimacy(self, user_id: str, score: float) -> None:
        sid = "global"
        if sid not in self._session_intimacies:
            self._session_intimacies[sid] = {}
        self._session_intimacies[sid][user_id] = max(0.0, min(1.0, score))

    def get_user_intimacy(self, user_id: str) -> float:
        sid = "global"
        return self._session_intimacies.get(sid, {}).get(user_id, 0.0)

    def _format_user_strategy(self, user_id: str) -> str:
        strategy = self.get_user_strategy(user_id)
        if not strategy or not strategy.get("strategy"):
            return ""
        parts = [f"\n策略: {strategy['strategy']}"]
        if strategy.get("source"):
            parts.append(f"来源: {strategy['source']}")
        if strategy.get("updated_at"):
            try:
                ts = int(strategy["updated_at"])
                date_str = time.strftime("%Y-%m-%d", time.localtime(ts))
                parts.append(f"更新: {date_str}")
            except (ValueError, TypeError, OSError):
                pass
        return "  ".join(parts)

    def _format_user_intimacy(self, user_id: str) -> str:
        score = self.get_user_intimacy(user_id)
        if score == 0.0:
            return ""
        level = "很熟"
        if score < 0.3:
            level = "不太熟"
        elif score < 0.6:
            level = "一般"
        elif score < 0.8:
            level = "比较熟"
        return f"\n亲密度: {score:.2f}（{level}）"

    @staticmethod
    def _deduplicate_profiles(memories: Iterable[BaseMemory]) -> List[BaseMemory]:
        seen_ids = set()
        seen_judgments = set()
        result: List[BaseMemory] = []
        for memory in memories or []:
            memory_id = str(getattr(memory, "id", "") or "").strip()
            normalized = normalize_judgment(getattr(memory, "judgment", ""))
            if memory_id and memory_id in seen_ids:
                continue
            if normalized and normalized in seen_judgments:
                continue
            if memory_id:
                seen_ids.add(memory_id)
            if normalized:
                seen_judgments.add(normalized)
            result.append(memory)
        return result
