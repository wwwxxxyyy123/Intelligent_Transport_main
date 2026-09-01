"""配置加载模块：读取 config.yaml 并提供全局访问。

使用单例模式，保证整个程序共享同一份配置：
    from app.config import Config
    weights = Config().get('model', 'weights')
"""
import os

import yaml


class Config:
    """单例式配置类，从 yaml 加载系统参数。"""

    _instance = None
    _data = None  # 解析后的字典

    def __new__(cls, *args, **kwargs):
        # 全局唯一实例
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, config_path=None):
        # 仅首次加载文件，避免重复 IO
        if self._data is None:
            # 默认指向项目根目录下的 config.yaml
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            path = config_path or os.path.join(project_root, 'config.yaml')
            with open(path, 'r', encoding='utf-8') as f:
                self._data = yaml.safe_load(f)

    def get(self, *keys, default=None):
        """按层级获取配置值，例如 get('model', 'weights')。"""
        val = self._data
        for k in keys:
            if not isinstance(val, dict) or k not in val:
                return default
            val = val[k]
        return val

    @property
    def data(self):
        """返回完整配置字典。"""
        return self._data
