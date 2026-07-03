"""
strategy_store - 相处策略 & 亲密度存储

独立存储，不依赖 DeepMind 初始化，注册为 PluginContext 的额外组件，
确保工具、WebUI、注入服务都能随时访问。
"""

import time
from typing import Dict

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

    def set_strategy(self, user_id: str, strategy: str, source: str = "", alias_for: str = "") -> None:
        self._strategies[user_id] = {
            "strategy": strategy,
            "source": source,
            "updated_at": str(int(time.time())),
        }
        if alias_for:
            self._aliases[user_id] = alias_for
        self.logger.info(f"[策略卡] 已设置 user_id={user_id} strategy=「{strategy[:30]}」")

    def get_strategy(self, user_id: str) -> dict:
        if user_id in self._strategies:
            return self._strategies[user_id]
        alias_target = self._aliases.get(user_id, "")
        if alias_target and alias_target in self._strategies:
            return self._strategies[alias_target]
        return {}

    def set_intimacy(self, user_id: str, score: float) -> None:
        self._intimacies[user_id] = max(0.0, min(1.0, score))

    def get_intimacy(self, user_id: str) -> float:
        if user_id in self._intimacies:
            return self._intimacies[user_id]
        alias_target = self._aliases.get(user_id, "")
        if alias_target and alias_target in self._intimacies:
            return self._intimacies[alias_target]
        return 0.0

    def get_all_strategies(self) -> dict:
        return dict(self._strategies)

    def get_all_intimacies(self) -> dict:
        return dict(self._intimacies)
