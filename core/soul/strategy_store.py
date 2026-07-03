"""
strategy_store - 相处策略 & 亲密度存储

独立存储，不依赖 DeepMind 初始化，注册为 PluginContext 的额外组件，
确保工具、WebUI、注入服务都能随时访问。

数据持久化到 plugin_data 目录下的 JSON 文件，重启不丢失。
"""

import json
import os
import time
from pathlib import Path
from typing import Dict, Optional

try:
    from astrbot.api import logger
except ImportError:
    import logging
    logger = logging.getLogger(__name__)


class StrategyStore:
    def __init__(self, data_dir: Optional[str] = None):
        self._strategies: Dict[str, dict] = {}
        self._intimacies: Dict[str, float] = {}
        self._aliases: Dict[str, str] = {}
        self._data_dir = data_dir
        self.logger = logger
        if data_dir:
            self._load_from_file()

    def _file_path(self) -> Optional[Path]:
        if not self._data_dir:
            return None
        return Path(self._data_dir) / "strategy_store.json"

    def _save_to_file(self) -> None:
        path = self._file_path()
        if not path:
            return
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "strategies": self._strategies,
                "intimacies": self._intimacies,
                "aliases": self._aliases,
            }
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self.logger.warning(f"[策略存储] 持久化失败: {e}")

    def _load_from_file(self) -> None:
        path = self._file_path()
        if not path or not path.exists():
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                self._strategies = data.get("strategies", {}) or {}
                self._intimacies = data.get("intimacies", {}) or {}
                self._aliases = data.get("aliases", {}) or {}
                self.logger.info(
                    f"[策略存储] 已加载 策略数={len(self._strategies)} 亲密度数={len(self._intimacies)}"
                )
        except Exception as e:
            self.logger.warning(f"[策略存储] 加载失败: {e}")

    def set_strategy(self, user_id: str, strategy: str, source: str = "", alias_for: str = "") -> None:
        self._strategies[user_id] = {
            "strategy": strategy,
            "source": source,
            "updated_at": str(int(time.time())),
        }
        if alias_for:
            self._aliases[user_id] = alias_for
        self._save_to_file()
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
        self._save_to_file()

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
