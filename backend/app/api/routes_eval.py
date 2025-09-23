from fastapi import APIRouter
from ..models.schemas import EvalReq, EvalResp
from ..services.role import build_role_card
from ..services.llm import chat as llm_chat

router = APIRouter(prefix="/v1")

@router.post("/eval", response_model=EvalResp)
async def eval_role(req: EvalReq):
    role_card = build_role_card(req.role_name)
    passed, details = 0, []
    for q in req.cases:
        reply = await llm_chat(req.role_name, role_card, [], q, "knowledge")
        ok = all(k in reply for k in req.keywords)
        passed += int(ok)
        details.append({"q": q, "reply": reply, "ok": ok})
    return EvalResp(passed=passed, total=len(req.cases), details=details)
