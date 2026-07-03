"""
belief_store - 核心信念存储

管理 OC 的核心信念列表，提供 CRUD 接口和注入格式化。
信念仅在内存中维护，重启后丢失（同 Soul State 策略）。
"""

import uuid
import time
from typing import Dict, List, Optional

try:
    from astrbot.api import logger
except ImportError:
    import logging
    logger = logging.getLogger(__name__)


class BeliefStore:
    def __init__(self, max_beliefs: int = 20):
        self._beliefs: Dict[str, dict] = {}
        self._order: List[str] = []
        self._max_beliefs = max_beliefs
        self.logger = logger

    def add_belief(
        self,
        content: str,
        origin: str = "",
        approved_by: str = "",
        reasoning: str = "",
    ) -> str:
        bid = f"belief_{uuid.uuid4().hex[:8]}"
        now = int(time.time())
        self._beliefs[bid] = {
            "id": bid,
            "content": content,
            "origin": origin,
            "created_at": now,
            "approved_by": approved_by,
            "reasoning": reasoning,
            "active": True,
        }
        self._order.append(bid)
        self.logger.info(f"[核心信念] 新增 belief_id={bid} content=「{content[:30]}」")
        self._trim_if_needed()
        return bid

    def get_belief(self, belief_id: str) -> Optional[dict]:
        return self._beliefs.get(belief_id)

    def modify_belief(self, belief_id: str, content: str, reasoning: str = "") -> None:
        if belief_id not in self._beliefs:
            raise ValueError(f"信念 {belief_id} 不存在")
        self._beliefs[belief_id]["content"] = content
        self._beliefs[belief_id]["reasoning"] = reasoning
        self._beliefs[belief_id]["updated_at"] = int(time.time())
        self.logger.info(f"[核心信念] 修改 belief_id={belief_id} content=「{content[:30]}」")

    def remove_belief(self, belief_id: str) -> None:
        if belief_id in self._beliefs:
            self._beliefs.pop(belief_id, None)
            if belief_id in self._order:
                self._order.remove(belief_id)
            self.logger.info(f"[核心信念] 移除 belief_id={belief_id}")

    def get_active_beliefs(self) -> List[dict]:
        return [
            self._beliefs[bid]
            for bid in self._order
            if bid in self._beliefs and self._beliefs[bid].get("active", True)
        ]

    def format_for_prompt(self) -> str:
        active = self.get_active_beliefs()
        if not active:
            return ""
        lines = [
            "<core_beliefs>",
            "以下是你在成长过程中形成的核心认知，它们是你性格的一部分：",
        ]
        for belief in active:
            lines.append(f"• {belief['content']}")
        lines.append("</core_beliefs>")
        return "\n".join(lines)

    def _trim_if_needed(self) -> None:
        active = self.get_active_beliefs()
        if len(active) <= self._max_beliefs:
            return
        excess = len(active) - self._max_beliefs
        for belief in active[:excess]:
            bid = belief["id"]
            self._beliefs[bid]["active"] = False
            self.logger.info(f"[核心信念] 自动归档 belief_id={bid} 超出上限 {self._max_beliefs}")
