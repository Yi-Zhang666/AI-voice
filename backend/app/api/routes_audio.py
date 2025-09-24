# app/api/routes_audio.py
import os, uuid, pathlib, base64, requests
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/v1", tags=["audio"])

OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://openai.qiniu.com/v1").rstrip("/")
OPENAI_API_KEY  = (os.getenv("OPENAI_API_KEY") or "").strip()
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "http://localhost:8000").rstrip("/")

STATIC = pathlib.Path("static"); STATIC.mkdir(exist_ok=True)
UPLOAD_DIR = STATIC / "uploads"; UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

def _is_public(url: str) -> bool:
    return not ("localhost" in url or "127.0.0.1" in url)

@router.post("/asr")
async def asr(
    file: UploadFile = File(...),
    fmt: str = Form("mp3"),
    language: str = Form("auto"),
    transport: str = Form("auto"),  # auto | url | base64
):
    """
    - transport=auto：如果 PUBLIC_BASE_URL 是公网，就走 url；否则走 base64
    - fmt: mp3 / wav / m4a / webm
    - language: auto / zh / en ...
    """
    if not OPENAI_API_KEY:
        raise HTTPException(500, "ASR 未配置 OPENAI_API_KEY")

    raw = await file.read()
    used = "base64"
    audio_url = None

    # 是否可以用公网 URL
    can_use_url = _is_public(PUBLIC_BASE_URL)
    if transport == "url" or (transport == "auto" and can_use_url):
        name = f"{uuid.uuid4().hex}.{fmt}"
        path = UPLOAD_DIR / name
        path.write_bytes(raw)
        audio_url = f"{PUBLIC_BASE_URL}/static/uploads/{name}"
        payload = {
            "audio": {"format": fmt, "url": audio_url},
            "request": {"language": language},
        }
        used = "url"
    else:
        b64 = base64.b64encode(raw).decode("utf-8")
        payload = {
            "audio": {"format": fmt, "data": b64},
            "request": {"language": language},
        }
        used = "base64"

    url = f"{OPENAI_BASE_URL}/voice/asr"
    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"}
    r = requests.post(url, json=payload, headers=headers, timeout=120)

    if r.status_code != 200:
        return JSONResponse(status_code=r.status_code, content={"error": r.text})

    j = r.json()
    # 七牛返回通常形如 {"data":{"result":{"text":"...","segments":[...]}}}
    text = (j.get("data") or {}).get("result", {}).get("text") or j.get("data") or ""
    return {"text": text, "audio_url": audio_url, "transport": used}
