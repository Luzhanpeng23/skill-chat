"""应用入口：统一导出应用实例与运行配置。"""
from .config import DEFAULT_HOST, DEFAULT_PORT
from .server import app

__all__ = ["app", "DEFAULT_HOST", "DEFAULT_PORT"]
