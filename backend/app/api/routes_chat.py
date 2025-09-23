import base64
from fastapi import APIRouter, HTTPException
from ..models.schemas import StartSessionReq, StartSessionResp, ChatReq, ChatResp
from ..core.session_store import create_session, get_session
from ..services.role import build_role_card
from ..services import llm, tts

router = APIRouter(prefix="/v1")

@router.post("/session/start", response_model=StartSessionResp)
def start_session(req: StartSessionReq):
    rn = req.role_name.strip()
    if not rn:
        raise HTTPException(400, "role_name 不能为空")
    role_card = build_role_card(rn)
    sid = create_session(rn, role_card, req.memory_limit)
    return StartSessionResp(session_id=sid, role_name=rn)

@router.post("/chat", response_model=ChatResp)
async def chat(req: ChatReq):
    sess = get_session(req.session_id)
    if not sess:
        raise HTTPException(404, "session 不存在")

    reply = await llm.chat(sess["role_name"], sess["role_card"], sess["history"], req.text, req.skill)
    sess["history"].append({"user": req.text, "assistant": reply})
    if len(sess["history"]) > sess["limit"]:
        del sess["history"][0]

    audio_bytes = await tts.synth(reply)
    audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")
    return ChatResp(session_id=req.session_id, role_name=sess["role_name"], reply_text=reply, tts_b64=audio_b64)
