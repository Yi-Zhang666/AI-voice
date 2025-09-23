import io, wave, struct
from ..core.config import USE_OPENAI, get_openai_client

def _silent_wav(duration_sec=1, sr=16000) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, 'wb') as wf:
        wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(sr)
        for _ in range(sr*duration_sec):
            wf.writeframes(struct.pack('<h', 0))
    return buf.getvalue()

async def synth(text: str, voice: str="alloy") -> bytes:
    if USE_OPENAI:
        try:
            client = get_openai_client()
            r = client.audio.speech.create(model="gpt-4o-mini-tts", voice=voice, input=text, format="wav")
            return r.read()
        except Exception as e:
            print("[WARN] TTS 失败：", e)
    return _silent_wav()
