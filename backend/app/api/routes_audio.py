# app/api/routes_audio.py
import os, uuid, pathlib, base64, requests
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/v1", tags=["audio"])

OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL","https://openai.qiniu.com/v1").rstrip("/")
OPENAI_API_KEY  = (os.getenv("OPENAI_API_KEY") or "").strip()
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL","http://localhost:8000").rstrip("/")

STATIC = pathlib.Path("static"); STATIC.mkdir(exist_ok=True)
UPLOAD_DIR = STATIC / "uploads"; UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

@router.post("/asr")
async def asr(file: UploadFile = File(...), fmt: str = Form("mp3")):
    if not OPENAI_API_KEY:
        raise HTTPException(500, "ASR 未配置 OPENAI_API_KEY")

    # 保存上传音频到本地，暴露为静态资源
    name = f"{uuid.uuid4().hex}.{fmt}"
    path = UPLOAD_DIR / name
    data = await file.read()
    path.write_bytes(data)
    audio_url = f"{PUBLIC_BASE_URL}/static/uploads/{name}"

    # 调七牛 ASR
    url = f"{OPENAI_BASE_URL}/voice/asr"
    payload = {"model":"asr","audio":{"format": fmt, "url": audio_url}}
    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type":"application/json"}
    r = requests.post(url, json=payload, headers=headers, timeout=60)
    if r.status_code != 200:
        return JSONResponse(status_code=r.status_code, content={"error": r.text})

    j = r.json()
    text = (j.get("data") or {}).get("result",{}).get("text")
    return {"text": text or "", "audio_url": audio_url}

@router.get("/voice/list")
def list_voices_proxy():
    url = f"{OPENAI_BASE_URL}/voice/list"
    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}"}
    r = requests.get(url, headers=headers, timeout=30)
    if r.status_code != 200:
        return JSONResponse(status_code=r.status_code, content={"error": r.text})
    return r.json()
