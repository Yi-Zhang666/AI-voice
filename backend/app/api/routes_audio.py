from fastapi import APIRouter, UploadFile, File
from ..services import asr, tts
from ..models.schemas import TTSReq, TTSResp
import base64

router = APIRouter(prefix="/v1")

@router.post("/asr")
async def transcribe(file: UploadFile = File(...)):
    data = await file.read()
    text = await asr.transcribe(data)
    return {"text": text}

@router.post("/tts", response_model=TTSResp)
async def synth(req: TTSReq):
    audio = await tts.synth(req.text, req.voice)
    return TTSResp(audio_b64=base64.b64encode(audio).decode("utf-8"))
