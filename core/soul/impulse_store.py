"""
impulse_store - 触动记录 & 自省提案存储

管理 OC 的信念摩擦触动记录和自省提案。
数据持久化到 plugin_data 目录下的 JSON 文件，重启不丢失。
支持被拒提案缓冲区（30天保留，防重复打扰）。
"""

import json
import time
import uuid
from pathlib import Path
from typing import Dict, List, Optional

try:
    from astrbot.api import logger
except ImportError:
    import logging
    logger = logging.getLogger(__name__)


class ImpulseStore:
    def __init__(
        self,
        data_dir: Optional[str] = None,
        threshold: float = 3.0,
        confidence_threshold: float = 0.4,
        rejection_buffer_days: int = 30,
    ):
        self._impulses: List[dict] = []
        self._pending_confessions: List[dict] = []
        self._rejected_confessions: List[dict] = []
        self._threshold = threshold
        self._confidence_threshold = confidence_threshold
        self._rejection_buffer_days = rejection_buffer_days
        self._data_dir = data_dir
        self.logger = logger
        if data_dir:
            self._load_from_file()
            self._clean_expired_rejections()

    def _file_path(self) -> Optional[Path]:
        if not self._data_dir:
            return None
        return Path(self._data_dir) / "impulse_store.json"

    def _save_to_file(self) -> None:
        path = self._file_path()
        if not path:
            return
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "impulses": self._impulses,
                "pending_confessions": self._pending_confessions,
                "rejected_confessions": self._rejected_confessions,
            }
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self.logger.warning(f"[触动存储] 持久化失败: {e}")

    def _load_from_file(self) -> None:
        path = self._file_path()
        if not path or not path.exists():
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                self._impulses = data.get("impulses", []) or []
                self._pending_confessions = data.get("pending_confessions", []) or []
                self._rejected_confessions = data.get("rejected_confessions", []) or []
                total_weight = self.get_pending_total_weight()
                self.logger.info(
                    f"[触动存储] 已加载 触动={len(self._impulses)} "
                    f"待自白={len(self._pending_confessions)} 被拒={len(self._rejected_confessions)} "
                    f"当前权重={total_weight:.1f}"
                )
        except Exception as e:
            self.logger.warning(f"[触动存储] 加载失败: {e}")

    def add_impulse(
        self,
        content: str,
        direction: str = "",
        trust_weight: float = 0.3,
        source_users: Optional[List[str]] = None,
        source_memories: Optional[List[str]] = None,
    ) -> dict:
        impulse = {
            "id": f"impulse_{uuid.uuid4().hex[:8]}",
            "content": content,
            "direction": direction,
            "trust_weight": round(trust_weight, 2),
            "source_users": source_users or [],
            "source_memories": source_memories or [],
            "created_at": int(time.time()),
            "processed": False,
        }
        self._impulses.append(impulse)
        self._save_to_file()
        self.logger.info(
            f"[触动积累] 新增 impulse_id={impulse['id']} "
            f"weight={trust_weight} content=「{content[:40]}」"
        )
        return impulse

    def get_pending_total_weight(self) -> float:
        total = 0.0
        for imp in self._impulses:
            if not imp.get("processed", False):
                total += float(imp.get("trust_weight", 0))
        return round(total, 2)

    def get_pending_impulses(self) -> List[dict]:
        return [imp for imp in self._impulses if not imp.get("processed", False)]

    def mark_processed(self) -> None:
        for imp in self._impulses:
            if not imp.get("processed", False):
                imp["processed"] = True
        self._save_to_file()

    def is_threshold_reached(self) -> bool:
        return self.get_pending_total_weight() >= self._threshold

    def add_confession(self, proposal: dict) -> None:
        confession = {
            "id": f"confession_{uuid.uuid4().hex[:8]}",
            "proposal": proposal.get("proposal", ""),
            "reasoning": proposal.get("reasoning", ""),
            "confidence": proposal.get("confidence", 0),
            "suggested_belief_text": proposal.get("suggested_belief_text", ""),
            "created_at": int(time.time()),
        }
        self._pending_confessions.append(confession)
        self._save_to_file()
        self.logger.info(
            f"[自省] 提案通过 confession_id={confession['id']} "
            f"confidence={confession['confidence']} "
            f"proposal=「{confession['proposal'][:40]}」"
        )

    def get_pending_confessions(self) -> List[dict]:
        return list(self._pending_confessions)

    def dismiss_confession(self, confession_id: str) -> None:
        for conf in self._pending_confessions:
            if conf.get("id") == confession_id:
                rejected = {
                    **conf,
                    "dismissed_at": int(time.time()),
                    "expires_at": int(time.time()) + self._rejection_buffer_days * 86400,
                }
                self._rejected_confessions.append(rejected)
                self.logger.info(
                    f"[缓冲区] 提案进入缓冲区 confession_id={confession_id} "
                    f"保留{self._rejection_buffer_days}天"
                )
                break
        self._pending_confessions = [
            c for c in self._pending_confessions if c.get("id") != confession_id
        ]
        self._save_to_file()

    def get_active_rejected(self) -> List[dict]:
        now = int(time.time())
        return [
            r for r in self._rejected_confessions
            if r.get("expires_at", 0) > now
        ]

    def _clean_expired_rejections(self) -> None:
        now = int(time.time())
        before = len(self._rejected_confessions)
        self._rejected_confessions = [
            r for r in self._rejected_confessions
            if r.get("expires_at", 0) > now
        ]
        removed = before - len(self._rejected_confessions)
        if removed:
            self._save_to_file()
            self.logger.info(f"[缓冲区] 清理过期提案 {removed} 条")

    def get_rejected_context_text(self) -> str:
        """生成供自省 prompt 使用的被拒提案参考文本"""
        active = self.get_active_rejected()
        self.logger.info(
            f"[缓冲区] get_rejected_context_text 调用 _rejected总={len(self._rejected_confessions)} 活跃={len(active)}"
        )
        if not active:
            return ""
        lines = ["最近被拒绝的提案（可作为参考，避免重复提议）："]
        for r in active[-5:]:
            lines.append(
                f"- 提案: {r.get('proposal', '')} "
                f"(理由: {r.get('reasoning', '')[:50]})"
            )
        return "\n".join(lines)
