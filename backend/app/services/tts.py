# backend/app/services/tts.py
"""
TTS 服务（Qiniu 网关版）
- 角色名规范化 + 同义词映射，中文/英文名都能命中
- 调用 https://openai.qiniu.com/v1/voice/tts
- 保存 mp3 到 static/audio/，返回 (audio_url, tts_b64)

需要的环境变量 (.env)：
  OPENAI_API_KEY=sk-七牛AI密钥
  OPENAI_BASE_URL=https://openai.qiniu.com/v1
  USE_TTS=1
  OPENAI_TTS_MODE=qiniu
  QINIU_TTS_VOICE=qiniu_zh_male_ybxknjs   # 默认兜底音色（可改）
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

DEFAULT_VOICE = os.getenv("QINIU_TTS_VOICE", "qiniu_zh_male_ybxknjs")
SPEED = float(os.getenv("QINIU_TTS_SPEED", "1.0"))
PUBLIC_BASE = os.getenv("PUBLIC_BASE_URL", "http://localhost:8000").rstrip("/")

# —— 本地音频目录 —— #
STATIC_DIR = pathlib.Path("static")
AUDIO_DIR = STATIC_DIR / "audio"
AUDIO_DIR.mkdir(parents=True, exist_ok=True)

# =========================
#  角色名规范化与同义词映射
# =========================
_SEP = r"[·•・\s\._．-]+"

def _norm(name: str) -> str:
    """规范化角色名：去空白/中点/下划线/点号，统一小写"""
    s = (name or "").strip().lower()
    return re.sub(_SEP, "", s)

# 你账号 voice/list 中存在的 voice_type 映射（安全可用）
ROLE_VOICE_MAP_RAW = {
    # —— 中文角色 —— #
    # 渊博学科男教师（沉稳学术）
    "socrates": "qiniu_zh_male_ybxknjs",
    "苏格拉底": "qiniu_zh_male_ybxknjs",

    # 磁性课件男声（庄重）
    "confucius": "qiniu_zh_male_cxkjns",
    "孔子": "qiniu_zh_male_cxkjns",

    # 温婉学科讲师（温柔）
    "lin dai yu": "qiniu_zh_female_wwxkjx",
    "lin_daiyu": "qiniu_zh_female_wwxkjx",
    "林黛玉": "qiniu_zh_female_wwxkjx",

    # 名著角色猴哥（最贴脸）
    "sun wukong": "qiniu_zh_male_mzjsxg",
    "sun_wukong": "qiniu_zh_male_mzjsxg",
    "孙悟空": "qiniu_zh_male_mzjsxg",
    "齐天大圣": "qiniu_zh_male_mzjsxg",
    "孙行者": "qiniu_zh_male_mzjsxg",

    # —— 英文/英式角色 —— #
    # 英式英语男（莎士比亚/福尔摩斯/牛顿/哈利）
    "shakespeare": "qiniu_en_male_ysyyn",
    "莎士比亚": "qiniu_en_male_ysyyn",

    "sherlock": "qiniu_en_male_ysyyn",
    "sherlock holmes": "qiniu_en_male_ysyyn",
    "福尔摩斯": "qiniu_en_male_ysyyn",

    "newton": "qiniu_en_male_ysyyn",
    "isaac newton": "qiniu_en_male_ysyyn",
    "牛顿": "qiniu_en_male_ysyyn",

    "harry potter": "qiniu_en_male_ysyyn",
    "harry_potter": "qiniu_en_male_ysyyn",
    "哈利波特": "qiniu_en_male_ysyyn",
    "哈利·波特": "qiniu_en_male_ysyyn",
}

# 规范化后的映射表（查表用）
ROLE_VOICE_MAP = {_norm(k): v for k, v in ROLE_VOICE_MAP_RAW.items()}

# 兜底音色（中文/英文）
FALLBACK_ZH = "qiniu_zh_male_ybxknjs"
FALLBACK_EN = "qiniu_en_male_ysyyn"

def _looks_chinese(s: str) -> bool:
    return bool(s and re.search(r"[\u4e00-\u9fff]", s))

def pick_voice(role_name: Optional[str], reply_text: Optional[str] = None, voice_override: Optional[str] = None) -> str:
    """
    选音优先级：
      1) voice_override（前端明确指定）
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
            "text": text[:800],
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

def list_voices() -> Optional[list]:
    """代理七牛 GET /voice/list，返回列表（失败返回 None）"""
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
