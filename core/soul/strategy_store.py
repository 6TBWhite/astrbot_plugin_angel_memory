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
        self.logger = logger

    def set_strategy(self, user_id: str, strategy: str, source: str = "") -> None:
        self._strategies[user_id] = {
            "strategy": strategy,
            "source": source,
            "updated_at": str(int(time.time())),
        }
        self.logger.info(f"[策略卡] 已设置 user_id={user_id} strategy=「{strategy[:30]}」")

    def get_strategy(self, user_id: str) -> dict:
        return self._strategies.get(user_id, {})

    def set_intimacy(self, user_id: str, score: float) -> None:
        self._intimacies[user_id] = max(0.0, min(1.0, score))

    def get_intimacy(self, user_id: str) -> float:
        return self._intimacies.get(user_id, 0.0)

    def get_all_strategies(self) -> dict:
        return dict(self._strategies)

    def get_all_intimacies(self) -> dict:
        return dict(self._intimacies)
