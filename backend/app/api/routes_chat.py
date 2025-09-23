# backend/app/routes/chat.py
from fastapi import APIRouter, HTTPException
from ..models.schemas import StartSessionReq, StartSessionResp, ChatReq, ChatResp
from ..core.session_store import create_session, get_session
from ..services.role import build_role_card
from ..services import llm
from ..services.tts import synthesize  

router = APIRouter(prefix="/v1")

@router.post("/session/start", response_model=StartSessionResp)
def start_session(req: StartSessionReq):
    rn = (req.role_name or "").strip()
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

    # 1) 先让 LLM 生成文本
    reply = await llm.chat(
        sess["role_name"],
        sess["role_card"],
        sess["history"],
        req.text,
        req.skill,
    )

    # 滚动对话历史
    sess["history"].append({"user": req.text, "assistant": reply})
    if len(sess["history"]) > sess["limit"]:
        del sess["history"][0]

    # 2) 语音合成（根据角色名自动挑音色）
    # 如果你的请求体/会话里有手动指定的音色，可作为 voice_override 传入
    audio_url, tts_b64 = synthesize(
        reply,
        role_name=sess["role_name"],
        reply_text=reply,
        # voice_override=sess.get("voice_type")  # 可选
    )

    # 3) 返回
    return ChatResp(
        session_id=req.session_id,
        role_name=sess["role_name"],
        reply_text=reply,
        audio_url=audio_url,   # ← 新增：可直接播放
        tts_b64=tts_b64,       # 备用
    )
