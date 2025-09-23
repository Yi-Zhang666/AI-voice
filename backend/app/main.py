from dotenv import load_dotenv
load_dotenv()
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .api.routes_chat import router as chat_router
from .api.routes_audio import router as audio_router
from .api.routes_eval import router as eval_router
from .core.config import USE_OPENAI, OPENAI_BASE_URL

app = FastAPI(title="AI 角色扮演平台 - 后端")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"]
)

@app.get("/healthz")
def healthz():
    return {"ok": True, "use_openai": USE_OPENAI, "base_url": OPENAI_BASE_URL or "official"}

app.include_router(chat_router)
app.include_router(audio_router)
app.include_router(eval_router)
