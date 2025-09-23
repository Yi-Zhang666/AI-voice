from pydantic import BaseModel
from typing import List, Optional
from .skills import SkillName

class StartSessionReq(BaseModel):
    role_name: str
    memory_limit: int = 6

class StartSessionResp(BaseModel):
    session_id: str
    role_name: str

class ChatReq(BaseModel):
    session_id: str
    text: str
    skill: SkillName = "knowledge"

class ChatResp(BaseModel):
    session_id: str
    role_name: str
    reply_text: str
    tts_b64: Optional[str] = None

class TTSReq(BaseModel):
    text: str
    voice: str = "alloy"

class TTSResp(BaseModel):
    audio_b64: str

class EvalReq(BaseModel):
    role_name: str
    cases: List[str]
    keywords: List[str]

class EvalResp(BaseModel):
    passed: int
    total: int
    details: List[dict]
