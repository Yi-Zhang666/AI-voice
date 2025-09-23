# app/services/tts.py
import os, uuid, base64, requests, pathlib

USE_TTS = os.getenv("USE_TTS", "0") == "1"
OPENAI_TTS_MODE = os.getenv("OPENAI_TTS_MODE", "qiniu").lower()
BASE_URL = os.getenv("OPENAI_BASE_URL", "https://openai.qiniu.com/v1").rstrip("/")
API_KEY  = os.getenv("OPENAI_API_KEY", "").strip()
DEFAULT_VOICE = os.getenv("QINIU_TTS_VOICE", "qiniu_zh_female_tmjxxy")
SPEED = float(os.getenv("QINIU_TTS_SPEED", "1.0"))
PUBLIC_BASE = os.getenv("PUBLIC_BASE_URL", "http://localhost:8000").rstrip("/")

AUDIO_DIR = pathlib.Path("static/audio")
AUDIO_DIR.mkdir(parents=True, exist_ok=True)

# 角色 -> 音色 映射（可按需补充/调整）
ROLE_VOICE_MAP = {
    "socrates": "qiniu_zh_male_lpsmtb",
    "confucius": "qiniu_zh_male_deep",
    "lin_daiyu": "qiniu_zh_female_tmjxxy",
    "sun_wukong": "qiniu_zh_male_yzcs",
    "shakespeare": "qiniu_en_male_std",
    "sherlock": "qiniu_en_male_british",
    "newton": "qiniu_en_male_calm",
    "harry_potter": "qiniu_en_male_boyish",
}

def pick_voice(role_name: str) -> str:
    if not role_name:
        return DEFAULT_VOICE
    key = role_name.strip().lower()
    return ROLE_VOICE_MAP.get(key, DEFAULT_VOICE)

def synthesize(text: str, role_name: str | None = None):
    """
    返回 (audio_url, tts_b64)
    - 成功：保存 mp3 到 static/audio/.. 并返回可访问的 URL；同时也返回 base64
    - 失败或未开启：返回 (None, None)
    """
    if not USE_TTS:
        return None, None

    if OPENAI_TTS_MODE != "qiniu":
        # 当前项目只接了七牛 TTS；其它模式直接跳过
        return None, None

    if not API_KEY:
        print("[TTS] 缺少 OPENAI_API_KEY")
        return None, None

    voice = pick_voice(role_name or "")
    url = f"{BASE_URL}/voice/tts"
    payload = {
        "audio": {"voice_type": voice, "encoding": "mp3", "speed_ratio": SPEED},
        "request": {"text": text[:800]}  # 防止超长
    }
    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}

    try:
        r = requests.post(url, json=payload, headers=headers, timeout=60)
        if r.status_code != 200:
            print("[TTS] HTTP", r.status_code, r.text)
            return None, None

        data = r.json()
        b64 = data.get("data")
        if not b64:
            print("[TTS] no data field in response")
            return None, None

        audio_bytes = base64.b64decode(b64)
        name = f"{uuid.uuid4().hex}.mp3"
        path = AUDIO_DIR / name
        path.write_bytes(audio_bytes)

        audio_url = f"{PUBLIC_BASE}/static/audio/{name}"
        return audio_url, b64
    except Exception as e:
        print("[TTS] 调用失败：", e)
        return None, None
