import io
from ..core.config import USE_OPENAI, get_openai_client

async def transcribe(wav_bytes: bytes) -> str:
    if USE_OPENAI:
        try:
            client = get_openai_client()
            f = io.BytesIO(wav_bytes); f.name = "audio.wav"
            r = client.audio.transcriptions.create(model="whisper-1", file=f)
            return r.text
        except Exception as e:
            print("[WARN] Whisper 失败：", e)
    return "请用哈利波特的口吻教我一个咒语"
