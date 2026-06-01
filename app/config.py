"""应用级配置：路径、端口与运行参数。"""
from __future__ import annotations

from pathlib import Path

from book2skill_agent.config import OUTPUT_DIR as BOOK_OUTPUTS_DIR

# ── 基础路径 ──────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
SKILLS_ROOT = BASE_DIR / "skills"
UPLOADS_DIR = DATA_DIR / "uploads"
ARCHIVES_DIR = DATA_DIR / "archives"
BOOK_OUTPUTS_ROOT = Path(BOOK_OUTPUTS_DIR).resolve()

# ── 前端构建产物 ──────────────────────────────────────────
WEB_DIST = BASE_DIR / "web"
WEB_INDEX = WEB_DIST / "index.html"

# ── 服务器 ────────────────────────────────────────────────
DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 8000
