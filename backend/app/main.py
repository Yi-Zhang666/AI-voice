# backend/app/main.py
from dotenv import load_dotenv
load_dotenv()

from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse  # 需要用到测试页面

from .api.routes_chat import router as chat_router
from .api.routes_audio import router as audio_router
from .api.routes_eval import router as eval_router
from .api.routes_roles import router as roles_router   # 若没有该文件，可先注释掉
from .core.config import USE_OPENAI, OPENAI_BASE_URL

app = FastAPI(title="AI 角色扮演平台 - 后端")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ----- 挂载静态目录 -----
ROOT_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = ROOT_DIR / "static"
STATIC_DIR.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# 健康检查
@app.get("/healthz")
def healthz():
    return {
        "ok": True,
        "use_openai": USE_OPENAI,
        "base_url": OPENAI_BASE_URL or "official",
        "static_dir": str(STATIC_DIR),
    }

# 可选：两个简单的静态测试页（没有文件也不影响后端接口）
@app.get("/asr-test")
async def asr_test_page():
    return FileResponse(STATIC_DIR / "asr-test.html")

@app.get("/roleplay")
async def roleplay_page():
    return FileResponse(STATIC_DIR / "roleplay.html")

# ----- 路由 -----
app.include_router(chat_router)
app.include_router(audio_router)
app.include_router(eval_router)
app.include_router(roles_router)  # 若没有 routes_roles.py，可注释掉
