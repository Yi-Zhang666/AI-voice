import os
from typing import Optional
try:
    from openai import OpenAI
except Exception:
    OpenAI = None  # 便于无 SDK 环境下导入

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL")  # e.g. https://openai.qiniu.com/v1
USE_OPENAI = bool(OPENAI_API_KEY) and OpenAI is not None

def get_openai_client() -> Optional["OpenAI"]:
    if not USE_OPENAI:
        return None
    if OPENAI_BASE_URL:
        return OpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL)
    return OpenAI(api_key=OPENAI_API_KEY)
