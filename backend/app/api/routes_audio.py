# backend/app/api/routes_audio.py
"""
Audio APIs
- POST /v1/asr : 语音识别（上传音频 -> 本地保存 -> base64 直传七牛 ASR）
- GET  /v1/voice/list : 代理七牛音色列表（给前端下拉用）

需要的环境变量 (.env)：
  OPENAI_API_KEY=sk-xxxx                # 七牛 AI 网关密钥
  OPENAI_BASE_URL=https://openai.qiniu.com/v1
  PUBLIC_BASE_URL=http://localhost:8000  # 你的后端可访问地址（用于返回可预览的本地上传音频）
"""

from __future__ import annotations
import os
import uuid
import base64
import pathlib
import requests
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/v1", tags=["audio"])

# ------- 环境配置 -------
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://openai.qiniu.com/v1").rstrip("/")
OPENAI_API_KEY = (os.getenv("OPENAI_API_KEY") or "").strip()
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "http://localhost:8000").rstrip("/")

# ------- 本地静态目录（上传文件会保存在这里，便于回放/调试）-------
STATIC_DIR = pathlib.Path("static")
STATIC_DIR.mkdir(exist_ok=True)
UPLOAD_DIR = STATIC_DIR / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


@router.post("/asr")
async def asr(
    file: UploadFile = File(...),
    fmt: str = Form("mp3"),
    language: str = Form("auto"),  # 也可传 "zh", "en" 等
):
    """
    语音识别（ASR）：
    - 接收 multipart 上传的音频
    - 将音频保存到 static/uploads/ 并返回可访问的 audio_url
    - 将音频转为 base64 后直传七牛 ASR
    """
    if not OPENAI_API_KEY:
        raise HTTPException(500, "ASR 未配置：缺少 OPENAI_API_KEY")

    # 1) 保存上传音频到本地，便于你回放或前端预览
    name = f"{uuid.uuid4().hex}.{fmt}"
    path = UPLOAD_DIR / name
    raw = await file.read()
    path.write_bytes(raw)
    audio_url = f"{PUBLIC_BASE_URL}/static/uploads/{name}"

    # 2) 构造 base64 并调七牛 /voice/asr
    try:
        b64 = base64.b64encode(raw).decode("utf-8")
        url = f"{OPENAI_BASE_URL}/voice/asr"
        headers = {
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": "asr",
            "audio": {
                "format": fmt,   # 常见: mp3 / wav / m4a / webm
                "b64": b64,      # 直传 base64，避免公网可达 URL 的麻烦
            },
            "request": {
                "language": language  # 'auto' / 'zh' / 'en' 等
            },
        }

        r = requests.post(url, json=payload, headers=headers, timeout=90)
        if r.status_code != 200:
            # 透出网关的错误信息，方便定位
            return JSONResponse(status_code=r.status_code, content={"error": r.text})

        j = r.json()
        # 七牛返回结构容错解析
        data = j.get("data") or {}
        text = (
            (data.get("result") or {}).get("text")
            or data.get("text")
            or ""
        )
        return {"text": text, "audio_url": audio_url}

    except Exception as e:
        # 捕获所有异常，避免直接 500 但保留错误信息
        return JSONResponse(status_code=500, content={"error": f"ASR failed: {e}"})


@router.get("/voice/list")
def list_voices_proxy():
    """
    代理七牛 GET /voice/list：
    - 返回可用音色列表，前端可以做下拉选择
    """
    if not OPENAI_API_KEY:
        raise HTTPException(500, "缺少 OPENAI_API_KEY")
    try:
        url = f"{OPENAI_BASE_URL}/voice/list"
        headers = {"Authorization": f"Bearer {OPENAI_API_KEY}"}
        r = requests.get(url, headers=headers, timeout=30)
        if r.status_code != 200:
            return JSONResponse(status_code=r.status_code, content={"error": r.text})
        return r.json()
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": f"list_voices failed: {e}"})
