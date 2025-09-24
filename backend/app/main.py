# backend/app/main.py
from dotenv import load_dotenv
load_dotenv()

from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from .api.routes_chat import router as chat_router
from .api.routes_audio import router as audio_router
from .api.routes_eval import router as eval_router
from .core.config import USE_OPENAI, OPENAI_BASE_URL

app = FastAPI(title="AI 角色扮演平台 - 后端")
from .api.routes_roles import router as roles_router
# ...
app.include_router(roles_router)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# —— 挂载静态目录 /static —— #
# backend/ 作为基准目录，static/audio 放 mp3
BASE_DIR = Path(__file__).resolve().parent.parent  # app/ 的上一级 => backend/
STATIC_DIR = BASE_DIR / "static"
(STATIC_DIR / "audio").mkdir(parents=True, exist_ok=True)

# 例如：/static/audio/xxx.mp3
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

@app.get("/healthz")
def healthz():
    return {
        "ok": True,
        "use_openai": USE_OPENAI,
        "base_url": OPENAI_BASE_URL or "official",
        "static_dir": str(STATIC_DIR),
    }

@app.get("/asr-test")
async def asr_test_page():
    return FileResponse("static/asr-test.html")

@app.get("/roleplay")
async def roleplay_page():
    return FileResponse("static/roleplay.html")
# 路由
app.include_router(chat_router)
app.include_router(audio_router)
app.include_router(eval_router)
