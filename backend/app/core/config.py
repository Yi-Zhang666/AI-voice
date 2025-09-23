# backend/app/core/config.py
import os
from functools import lru_cache
from typing import Optional

try:
    from openai import OpenAI
except Exception:
    OpenAI = None  # 便于无 SDK 环境下导入

# ========== 环境变量 ==========
# 直连 OpenAI 可用 https://api.openai.com/v1
# 走七牛网关用 https://openai.qiniu.com/v1
OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_BASE_URL: str = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").strip()

# 模型 ID 从 .env 读取（例如：deepseek-v3 / deepseek-r1 / qwen2.5-72b-instruct 等）
OPENAI_CHAT_MODEL: str = os.getenv("OPENAI_CHAT_MODEL", "gpt-4o-mini").strip()

# 超时（可选）
OPENAI_TIMEOUT: float = float(os.getenv("OPENAI_TIMEOUT", "60"))

# 是否启用 OpenAI 客户端（有 key 且安装了 SDK）
USE_OPENAI: bool = bool(OPENAI_API_KEY) and OpenAI is not None


def get_chat_model() -> str:
    """统一提供给 llm.py 使用的模型 ID。"""
    return OPENAI_CHAT_MODEL


@lru_cache(maxsize=1)
def get_openai_client() -> Optional["OpenAI"]:
    """
    生成一个可复用的 OpenAI 客户端：
    - 支持设置 base_url 指向七牛网关
    - 只要 .env 里配好 OPENAI_API_KEY / OPENAI_BASE_URL / OPENAI_CHAT_MODEL
    """
    if not USE_OPENAI:
        return None
    return OpenAI(
        api_key=OPENAI_API_KEY,
        base_url=OPENAI_BASE_URL,
        timeout=OPENAI_TIMEOUT,
    )
