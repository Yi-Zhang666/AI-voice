# backend/app/services/tts.py
"""
TTS 服务（Qiniu 网关版）
- 角色名规范化 + 同义词映射，中文/英文名都能命中
- 调用 https://openai.qiniu.com/v1/voice/tts
- 保存 mp3 到 static/audio/，返回 (audio_url, tts_b64)

需要的环境变量 (.env)：
  OPENAI_API_KEY=sk-你的七牛AI密钥
  OPENAI_BASE_URL=https://openai.qiniu.com/v1
  OPENAI_CHAT_MODEL=deepseek-v3   # LLM 用，不影响本文件
  USE_TTS=1
  OPENAI_TTS_MODE=qiniu
  QINIU_TTS_VOICE=qiniu_zh_female_tmjxxy
  QINIU_TTS_SPEED=1.0
  PUBLIC_BASE_URL=http://localhost:8000
"""
from __future__ import annotations
import os
import re
import uuid
import base64
import pathlib
import requests
from typing import Optional, Tuple

# —— 环境配置 —— #
USE_TTS = os.getenv("USE_TTS", "0") == "1"
OPENAI_TTS_MODE = os.getenv("OPENAI_TTS_MODE", "qiniu").lower()
BASE_URL = os.getenv("OPENAI_BASE_URL", "https://openai.qiniu.com/v1").rstrip("/")
API_KEY = (os.getenv("OPENAI_API_KEY") or "").strip()

DEFAULT_VOICE = os.getenv("QINIU_TTS_VOICE", "qiniu_zh_female_tmjxxy")
SPEED = float(os.getenv("QINIU_TTS_SPEED", "1.0"))
PUBLIC_BASE = os.getenv("PUBLIC_BASE_URL", "http://localhost:8000").rstrip("/")

# —— 本地音频目录 —— #
STATIC_DIR = pathlib.Path("static")
AUDIO_DIR = STATIC_DIR / "audio"
AUDIO_DIR.mkdir(parents=True, exist_ok=True)

# =========================
#  角色名规范化与同义词映射
# =========================
# 允许的分隔符（空格、下划线、点号、中点等）
_SEP = r"[·•・\s\._．-]+"

def _norm(name: str) -> str:
    """规范化角色名：去空白/中点/下划线/点号，统一小写"""
    s = (name or "").strip().lower()
    return re.sub(_SEP, "", s)

# 原始别名映射：随时按需增删
ROLE_VOICE_MAP_RAW = {
    # 苏格拉底
    "socrates": "qiniu_zh_male_lpsmtb",
    "苏格拉底": "qiniu_zh_male_lpsmtb",

    # 孔子
    "confucius": "qiniu_zh_male_deep",
    "孔子": "qiniu_zh_male_deep",

    # 林黛玉
    "lin dai yu": "qiniu_zh_female_tmjxxy",
    "lin_daiyu": "qiniu_zh_female_tmjxxy",
    "林黛玉": "qiniu_zh_female_tmjxxy",

    # 孙悟空（齐天大圣/孙行者）
    "sun wukong": "qiniu_zh_male_yzcs",
    "sun_wukong": "qiniu_zh_male_yzcs",
    "孙悟空": "qiniu_zh_male_yzcs",
    "齐天大圣": "qiniu_zh_male_yzcs",
    "孙行者": "qiniu_zh_male_yzcs",

    # 莎士比亚
    "shakespeare": "qiniu_en_male_std",
    "莎士比亚": "qiniu_en_male_std",

    # 福尔摩斯
    "sherlock": "qiniu_en_male_british",
    "sherlock holmes": "qiniu_en_male_british",
    "福尔摩斯": "qiniu_en_male_british",

    # 牛顿
    "newton": "qiniu_en_male_calm",
    "isaac newton": "qiniu_en_male_calm",
    "牛顿": "qiniu_en_male_calm",

    # 哈利·波特（含不同写法）
    "harry potter": "qiniu_en_male_boyish",
    "harry_potter": "qiniu_en_male_boyish",
    "哈利波特": "qiniu_en_male_boyish",
    "哈利·波特": "qiniu_en_male_boyish",
}

# 规范化后的映射表（查表用）
ROLE_VOICE_MAP = { _norm(k): v for k, v in ROLE_VOICE_MAP_RAW.items() }

# 兜底音色
FALLBACK_ZH = "qiniu_zh_female_tmjxxy"
FALLBACK_EN = "qiniu_en_male_std"

def _looks_chinese(s: str) -> bool:
    return bool(s and re.search(r"[\u4e00-\u9fff]", s))

def pick_voice(role_name: Optional[str], reply_text: Optional[str] = None, voice_override: Optional[str] = None) -> str:
    """
    选音逻辑优先级：
      1) voice_override（前端/会话中明确指定）
      2) 命中同义词映射（中英文/别名均可）
      3) 角色名或回复文本含中文 → 中文兜底
      4) 英文兜底
    """
    if voice_override:
        return voice_override

    key = _norm(role_name or "")
    if key in ROLE_VOICE_MAP:
        return ROLE_VOICE_MAP[key]

    if _looks_chinese(role_name) or _looks_chinese(reply_text):
        return FALLBACK_ZH

    return FALLBACK_EN

# =========================
#  七牛 TTS 调用
# =========================
def _qiniu_tts_request(text: str, voice_type: str) -> Optional[str]:
    """
    调用七牛 /voice/tts，成功返回 base64 音频串，否则 None
    """
    url = f"{BASE_URL}/voice/tts"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "audio": {
            "voice_type": voice_type or DEFAULT_VOICE,
            "encoding": "mp3",
            "speed_ratio": SPEED,
        },
        "request": {
            "text": text[:800],  # 防止极长文本
        },
    }
    resp = requests.post(url, json=payload, headers=headers, timeout=60)
    if resp.status_code != 200:
        print(f"[TTS] HTTP {resp.status_code}: {resp.text[:200]}")
        return None
    data = resp.json()
    b64 = data.get("data")
    if not b64:
        print("[TTS] no 'data' in response")
        return None
    return b64

def tts_available() -> bool:
    """快速判断 TTS 配置是否可用"""
    return USE_TTS and OPENAI_TTS_MODE == "qiniu" and bool(API_KEY) and bool(BASE_URL)

def synthesize(
    text: str,
    role_name: Optional[str] = None,
    reply_text: Optional[str] = None,
    voice_override: Optional[str] = None,
) -> Tuple[Optional[str], Optional[str]]:
    """
    返回 (audio_url, tts_b64)
      - 成功：audio_url 为可播放链接，tts_b64 为 base64 音频
      - 失败或未启用：返回 (None, None)
    """
    if not tts_available():
        # 未启用或缺少配置
        return None, None

    try:
        voice = pick_voice(role_name, reply_text, voice_override)
        b64 = _qiniu_tts_request(text, voice)
        if not b64:
            return None, None

        audio_bytes = base64.b64decode(b64)
        name = f"{uuid.uuid4().hex}.mp3"
        path = AUDIO_DIR / name
        path.write_bytes(audio_bytes)

        audio_url = f"{PUBLIC_BASE}/static/audio/{name}"
        return audio_url, b64
    except Exception as e:
        print("[TTS] synthesize failed:", e)
        return None, None

# =========================
#  可选：列出可用音色（前端下拉）
# =========================
def list_voices() -> Optional[list]:
    """
    代理七牛 GET /voice/list，返回列表（失败返回 None）
    """
    try:
        url = f"{BASE_URL}/voice/list"
        headers = {"Authorization": f"Bearer {API_KEY}"}
        resp = requests.get(url, headers=headers, timeout=30)
        if resp.status_code != 200:
            print(f"[TTS] list voices HTTP {resp.status_code}: {resp.text[:200]}")
            return None
        return resp.json()
    except Exception as e:
        print("[TTS] list_voices error:", e)
        return None
