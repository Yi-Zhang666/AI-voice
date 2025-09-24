# app/api/routes_audio.py
from __future__ import annotations

import os
import uuid
import pathlib
import requests
from typing import Optional

from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/v1", tags=["audio"])

# —— 环境变量 —— #
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://openai.qiniu.com/v1").rstrip("/")
OPENAI_API_KEY  = (os.getenv("OPENAI_API_KEY") or "").strip()
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "http://127.0.0.1:8000").rstrip("/")

# —— 本地保存目录（已在 main.py 挂载 /static）—— #
STATIC_DIR   = pathlib.Path("static"); STATIC_DIR.mkdir(exist_ok=True)
UPLOAD_DIR   = STATIC_DIR / "uploads";  UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# -------------------------
# 工具：统一解析 ASR 返回
# -------------------------
def _extract_text(payload: dict) -> str:
    """
    七牛网关不同版本可能返回：
      {"text":"..."}
      {"data":"..."}
      {"result":"..."}
      {"data":{"text":"..."}}
      {"data":{"result":{"text":"..."}}}
    这里做一个兜底解析。
    """
    if not isinstance(payload, dict):
        return ""
    for k in ("text", "data", "result"):
        v = payload.get(k)
        if isinstance(v, str):
            return v.strip()
        if isinstance(v, dict):
            # 递归向下找
            t = _extract_text(v)
            if t:
                return t
    return ""

def _qiniu_asr(audio_url: str, language: str = "auto") -> str:
    """
    调用七牛 ASR：优先用新格式 {"request":{"audio_url":...}}
    若你的网关是旧版，也尝试兼容 {"audio":{"url":...},"model":"asr"} 这种写法。
    """
    if not OPENAI_API_KEY:
        raise HTTPException(500, "ASR 未配置：缺少 OPENAI_API_KEY")

    url = f"{OPENAI_BASE_URL}/voice/asr"
    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"}

    # 1) 推荐的新格式
    try_payloads = [
        {"request": {"audio_url": audio_url, "language": language}},
        # 2) 兼容一些旧格式/示例
        {"audio": {"url": audio_url}, "model": "asr"},
    ]

    last_err: Optional[str] = None
    for payload in try_payloads:
        r = requests.post(url, json=payload, headers=headers, timeout=60)
        if r.status_code == 200:
            j = r.json()
            text = _extract_text(j)
            if text:
                return text
            # 某些网关直接把结果放在 "text"
            if "text" in j and isinstance(j["text"], str) and j["text"].strip():
                return j["text"].strip()
            last_err = f"ASR ok but no text in response: {str(j)[:200]}"
        else:
            last_err = f"HTTP {r.status_code}: {r.text[:200]}"

    raise HTTPException(502, last_err or "ASR 失败")

@router.post("/asr")
async def asr(file: UploadFile = File(...), language: str = Form("auto")):
    """
    接收语音文件，保存到 static/uploads，拼出可访问的 URL，然后调用七牛 ASR。
    返回 {"text": 识别文字, "audio_url": 你刚上传的可访问地址}
    """
    if not file.content_type.startswith("audio/"):
        raise HTTPException(400, "file 必须是音频类型 (content-type 需以 audio/ 开头)")

    # 根据原始文件名取后缀，默认 .wav
    suffix = os.path.splitext(file.filename or "")[1] or ".wav"
    name   = f"{uuid.uuid4().hex}{suffix}"
    path   = UPLOAD_DIR / name

    # 保存上传
    data = await file.read()
    path.write_bytes(data)

    # 拼出可访问 URL（main.py 已挂载 /static）
    audio_url = f"{PUBLIC_BASE_URL}/static/uploads/{name}"

    # 调七牛 ASR
    text = _qiniu_asr(audio_url, language=language)
    return {"text": text, "audio_url": audio_url}

@router.get("/voice/list")
def list_voices_proxy():
    """
    代理七牛 GET /voice/list，供前端做下拉框选择音色。
    """
    if not OPENAI_API_KEY:
        raise HTTPException(500, "缺少 OPENAI_API_KEY")

    url = f"{OPENAI_BASE_URL}/voice/list"
    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}"}
    r = requests.get(url, headers=headers, timeout=30)
    if r.status_code != 200:
        return JSONResponse(status_code=r.status_code, content={"error": r.text})
    return r.json()
