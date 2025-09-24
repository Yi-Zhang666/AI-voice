# app/api/routes_audio.py
import os
import uuid
import pathlib
import requests
import mimetypes
from typing import Optional

from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/v1", tags=["audio"])

# === 环境变量 ===
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://openai.qiniu.com/v1").rstrip("/")
OPENAI_API_KEY = (os.getenv("OPENAI_API_KEY") or "").strip()
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "http://localhost:8000").rstrip("/")

# === 本地静态目录（确保 main.py 已 mount /static） ===
STATIC_DIR = pathlib.Path("static")
STATIC_DIR.mkdir(exist_ok=True)

UPLOAD_DIR = STATIC_DIR / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# === 小工具 ===
def _guess_fmt(filename: Optional[str], content_type: Optional[str], fallback: str = "mp3") -> str:
    """优先用文件扩展名，其次用 content-type，最后用 fallback。"""
    if filename and "." in filename:
        ext = filename.rsplit(".", 1)[-1].lower()
        if ext in {"mp3", "wav", "m4a", "webm", "ogg"}:
            return ext
    if content_type:
        guessed = mimetypes.guess_extension(content_type) or ""
        guessed = guessed.lstrip(".").lower()
        if guessed in {"mp3", "wav", "m4a", "webm", "ogg"}:
            return guessed
    return fallback

def _need_public_base() -> None:
    """
    七牛 ASR 会回源拉取你上传的音频文件，所以必须提供公网可访问的 URL。
    如果还是 localhost，就直接报错，避免 4xx。
    """
    if PUBLIC_BASE_URL.startswith("http://localhost") or PUBLIC_BASE_URL.startswith("http://127.0.0.1"):
        raise HTTPException(
            status_code=500,
            detail=(
                "ASR 需要公网可访问的音频 URL。请将 .env 中的 PUBLIC_BASE_URL "
                "改为你的公网地址（例如 cloudflared 输出的 https://xxxxx.trycloudflare.com）。"
            ),
        )

def _qiniu_asr(audio_url: str, fmt: str) -> JSONResponse:
    """调用七牛 /voice/asr 接口并把结果返回给前端。"""
    if not OPENAI_API_KEY:
        raise HTTPException(500, "ASR 未配置 OPENAI_API_KEY")
    url = f"{OPENAI_BASE_URL}/voice/asr"
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {"model": "asr", "audio": {"format": fmt, "url": audio_url}}
    # 调试用：确认我们真的传了 url 给七牛
    print("[ASR] payload ->", payload)

    r = requests.post(url, json=payload, headers=headers, timeout=90)
    if r.status_code != 200:
        # 直接把七牛返回透传给前端，便于定位
        return JSONResponse(status_code=r.status_code, content={"error": r.text})

    j = r.json()
    # 文档结构：data.result.text
    text = (j.get("data") or {}).get("result", {}).get("text", "") or ""
    duration_ms = (
        (j.get("data") or {}).get("audio_info", {}) or {}
    ).get("duration") or (j.get("data") or {}).get("result", {}).get("additions", {}).get("duration")

    return JSONResponse(
        content={
            "text": text,
            "audio_url": audio_url,
            "qiniu_reqid": j.get("reqid"),
            "duration_ms": duration_ms,
        }
    )

# === 接口：上传音频文件并识别 ===
@router.post("/asr")
async def asr(file: UploadFile = File(...), fmt: Optional[str] = Form(None)):
    """
    multipart 上传音频 → 保存到 static/uploads/ → 生成公网 URL → 调七牛 ASR → 返回识别文本
    支持格式：mp3 / wav / m4a / webm / ogg
    """
    _need_public_base()

    # 猜测/确定音频格式
    _fmt = (fmt or "").strip().lower() or _guess_fmt(file.filename, file.content_type, "mp3")
    if _fmt not in {"mp3", "wav", "m4a", "webm", "ogg"}:
        raise HTTPException(400, f"不支持的音频格式：{_fmt}")

    # 保存到本地静态目录
    filename = f"{uuid.uuid4().hex}.{_fmt}"
    path = UPLOAD_DIR / filename
    data = await file.read()
    path.write_bytes(data)

    # 拼接公网访问 URL（供七牛拉取）
    audio_url = f"{PUBLIC_BASE_URL}/static/uploads/{filename}"

    # 调七牛 ASR
    return _qiniu_asr(audio_url, _fmt)

# === 接口：代理列出可用音色（前端可做下拉选择） ===
@router.get("/voice/list")
def list_voices_proxy():
    if not OPENAI_API_KEY:
        raise HTTPException(500, "未配置 OPENAI_API_KEY")
    url = f"{OPENAI_BASE_URL}/voice/list"
    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}"}
    r = requests.get(url, headers=headers, timeout=30)
    if r.status_code != 200:
        return JSONResponse(status_code=r.status_code, content={"error": r.text})
    return r.json()

# ===（可选）直接用远程 URL 做 ASR（不上传文件）===
@router.post("/asr/url")
def asr_by_url(audio_url: str, fmt: str = "mp3"):
    """
    如果你的音频已经在公网（CDN/OSS），可直接用这个接口。
    """
    _need_public_base()
    if fmt not in {"mp3", "wav", "m4a", "webm", "ogg"}:
        raise HTTPException(400, f"不支持的音频格式：{fmt}")
    return _qiniu_asr(audio_url, fmt)
