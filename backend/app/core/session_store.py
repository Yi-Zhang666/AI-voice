import time, uuid
from typing import Dict

SESSIONS: Dict[str, Dict] = {}

def create_session(role_name: str, role_card: dict, memory_limit: int) -> str:
    sid = str(uuid.uuid4())
    SESSIONS[sid] = {
        "role_name": role_name,
        "role_card": role_card,
        "history": [],
        "limit": max(2, min(20, memory_limit)),
        "created_at": time.time(),
    }
    return sid

def get_session(session_id: str) -> dict | None:
    return SESSIONS.get(session_id)
