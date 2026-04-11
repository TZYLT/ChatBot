# config_manager.py
import json
import logger
from typing import Dict, Any


class ConfigManager:
    # 统一默认配置（所有配置项集中管理）
    DEFAULT_CONFIG: Dict[str, Any] = {
        "apikey": "",
        "temperature": 0.5,
        "base_max_context": 10,
        "now_max_context": 10,
        "system_prompt": "",
        "instant_memory": {},
        "model": 'deepseek_chat'
    }

    def __init__(self):
        self._config: Dict[str, Any] = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        """加载配置文件，异常时返回默认配置"""
        try:
            with open('config.json', 'r', encoding='utf-8') as f:
                logger.logger.debug("重新读取配置文件成功")
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            logger.logger.warning("配置文件不存在或格式错误，使用默认配置")
            return self.DEFAULT_CONFIG.copy()

    def _save_config(self) -> None:
        """保存当前配置到文件"""
        with open('config.json', 'w', encoding='utf-8') as f:
            json.dump(self._config, f, ensure_ascii=False, indent=4)
        logger.logger.debug("配置文件已保存")

    def reload(self) -> None:
        """重新从磁盘加载配置（用于配置文件外部修改后刷新）"""
        self._config = self._load_config()

    def get(self, key: str) -> Any:
        """
        【核心统一方法】获取配置项
        :param key: 配置字段名
        :return: 配置值
        :raises KeyError: 字段不存在时抛出错误（满足需求）
        """
        if key not in self._config:
            raise KeyError(f"配置字段 [{key}] 不存在，请检查配置项！")
        return self._config[key]

    def set(self, key: str, value: Any) -> None:
        """
        【核心统一方法】设置配置项并自动保存
        :param key: 配置字段名
        :param value: 配置值
        :raises KeyError: 字段不存在时抛出错误
        """
        if key not in self._config:
            raise KeyError(f"配置字段 [{key}] 不存在，无法设置！")
        self._config[key] = value
        self._save_config()

    def get_all(self) -> Dict[str, Any]:
        """获取完整配置字典（兼容原有批量读取逻辑）"""
        return self._config.copy()