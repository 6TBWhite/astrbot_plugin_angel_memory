"""
strategy_store - 相处策略 & 亲密度存储

独立存储，不依赖 DeepMind 初始化，注册为 PluginContext 的额外组件，
确保工具、WebUI、注入服务都能随时访问。

支持 scope 隔离：策略按 scope:user_id 存储，注入时只匹配当前 scope，
找不到则回退到 global scope（public）。
"""

import time
from typing import Dict, Optional

try:
    from astrbot.api import logger
except ImportError:
    import logging
    logger = logging.getLogger(__name__)


class StrategyStore:
    def __init__(self):
        self._strategies: Dict[str, dict] = {}
        self._intimacies: Dict[str, float] = {}
        self._aliases: Dict[str, str] = {}
        self.logger = logger

    @staticmethod
    def _key(scope: str, user_id: str) -> str:
        return f"{scope or 'public'}:{user_id}"

    def set_strategy(
        self,
        user_id: str,
        strategy: str,
        source: str = "",
        scope: str = "public",
        alias_for: str = "",
    ) -> None:
        key = self._key(scope, user_id)
        self._strategies[key] = {
            "strategy": strategy,
            "source": source,
            "scope": scope or "public",
            "updated_at": str(int(time.time())),
        }
        if alias_for:
            self._aliases[user_id] = alias_for
        self.logger.info(
            f"[策略卡] 已设置 scope={scope or 'public'} user_id={user_id} strategy=「{strategy[:30]}」"
        )

    def get_strategy(self, user_id: str, scope: str = "public") -> dict:
        key = self._key(scope, user_id)
        if key in self._strategies:
            return self._strategies[key]
        alias_target = self._aliases.get(user_id, "")
        if alias_target:
            alias_key = self._key(scope, alias_target)
            if alias_key in self._strategies:
                return self._strategies[alias_key]
        global_key = self._key("public", user_id)
        if scope != "public" and global_key in self._strategies:
            return self._strategies[global_key]
        return {}

    def set_intimacy(self, user_id: str, score: float, scope: str = "public") -> None:
        key = self._key(scope, user_id)
        self._intimacies[key] = max(0.0, min(1.0, score))

    def get_intimacy(self, user_id: str, scope: str = "public") -> float:
        key = self._key(scope, user_id)
        if key in self._intimacies:
            return self._intimacies[key]
        alias_target = self._aliases.get(user_id, "")
        if alias_target:
            alias_key = self._key(scope, alias_target)
            if alias_key in self._intimacies:
                return self._intimacies[alias_key]
        global_key = self._key("public", user_id)
        if scope != "public" and global_key in self._intimacies:
            return self._intimacies[global_key]
        return 0.0

    def get_all_strategies(self) -> dict:
        return dict(self._strategies)

    def get_all_intimacies(self) -> dict:
        return dict(self._intimacies)

    def find_strategy_by_name(self, name: str, scope: str = "public") -> dict:
        """按昵称模糊查找策略，用于 WebUI 通过昵称查询。"""
        name_lower = name.lower()
        for key, strategy in self._strategies.items():
            stored_scope, stored_user = key.split(":", 1) if ":" in key else ("public", key)
            if scope and stored_scope != scope and stored_scope != "public":
                continue
            if name_lower in stored_user.lower():
                return strategy
        return {}
