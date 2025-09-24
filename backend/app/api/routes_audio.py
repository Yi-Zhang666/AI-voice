# app/api/routes_audio.py
import os
import uuid
import pathlib
import requests
import mimetypes
from typing import Optional

from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/v1", tags=["audio"])

# === 环境变量 ===
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://openai.qiniu.com/v1").rstrip("/")
OPENAI_API_KEY = (os.getenv("OPENAI_API_KEY") or "").strip()
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "http://localhost:8000").rstrip("/")

# === 本地静态目录 ===
STATIC_DIR = pathlib.Path("static")
STATIC_DIR.mkdir(exist_ok=True)

UPLOAD_DIR = STATIC_DIR / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# === 工具函数 ===
def _guess_audio_format(filename: Optional[str], content_type: Optional[str], fallback: str = "mp3") -> str:
    """智能猜测音频格式"""
    if filename and "." in filename:
        ext = filename.rsplit(".", 1)[-1].lower()
        if ext in {"mp3", "wav", "m4a", "webm", "ogg", "flac"}:
            return ext
    
    if content_type:
        type_map = {
            "audio/mpeg": "mp3",
            "audio/wav": "wav",
            "audio/wave": "wav", 
            "audio/x-wav": "wav",
            "audio/mp4": "m4a",
            "audio/x-m4a": "m4a",
            "audio/webm": "webm",
            "audio/ogg": "ogg",
            "audio/flac": "flac"
        }
        return type_map.get(content_type, fallback)
    
    return fallback

def _check_public_url():
    """检查公网URL配置 - ASR必需"""
    if PUBLIC_BASE_URL.startswith(("http://localhost", "http://127.0.0.1")):
        raise HTTPException(
            status_code=500,
            detail={
                "error": "ASR_REQUIRES_PUBLIC_URL",
                "message": (
                    "语音识别功能需要公网可访问的音频URL。"
                    "请设置环境变量 PUBLIC_BASE_URL 为你的公网地址。"
                ),
                "solutions": [
                    "使用 cloudflared: cloudflared tunnel --url http://localhost:8000",
                    "使用 ngrok: ngrok http 8000", 
                    "部署到云服务器使用真实域名"
                ]
            }
        )

def _call_qiniu_asr(audio_url: str, audio_format: str) -> dict:
    """调用七牛云ASR接口 - 按官方文档格式"""
    if not OPENAI_API_KEY:
        raise HTTPException(500, {
            "error": "MISSING_API_KEY", 
            "message": "ASR服务未配置，缺少 OPENAI_API_KEY"
        })
    
    url = f"{OPENAI_BASE_URL}/voice/asr"
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }
    
    # 按照官方文档格式构建请求
    payload = {
        "model": "asr",
        "audio": {
            "format": audio_format,
            "url": audio_url
        }
    }
    
    print(f"[ASR] 请求URL: {audio_url}")
    print(f"[ASR] 音频格式: {audio_format}")
    print(f"[ASR] 请求数据: {payload}")
    
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=90)
        
        print(f"[ASR] 响应状态: {response.status_code}")
        print(f"[ASR] 响应头: {dict(response.headers)}")
        
        if response.status_code != 200:
            error_detail = {
                "error": "ASR_API_ERROR",
                "status_code": response.status_code,
                "response": response.text,
                "message": f"七牛云ASR接口返回错误: {response.status_code}"
            }
            raise HTTPException(response.status_code, error_detail)
        
        result = response.json()
        print(f"[ASR] 原始响应: {result}")
        
        return result
        
    except requests.RequestException as e:
        error_detail = {
            "error": "ASR_REQUEST_FAILED",
            "message": f"ASR请求失败: {str(e)}",
            "audio_url": audio_url
        }
        raise HTTPException(500, error_detail)

def _extract_text_from_asr_result(result: dict) -> str:
    """从ASR结果中提取识别文本"""
    try:
        # 按照官方文档格式解析
        if "data" in result and "result" in result["data"]:
            text = result["data"]["result"].get("text", "")
        elif "data" in result and "text" in result["data"]:
            text = result["data"]["text"]
        elif "text" in result:
            text = result["text"]
        else:
            text = ""
        
        return text.strip()
    except Exception as e:
        print(f"[ASR] 文本提取失败: {e}")
        return ""

# === API端点 ===

@router.post("/asr")
async def speech_to_text(
    file: UploadFile = File(...),
    language: str = Form("auto")
):
    """
    语音识别接口
    - 上传音频文件
    - 自动识别音频格式
    - 调用七牛云ASR
    - 返回识别文本
    """
    
    # 检查公网URL配置
    _check_public_url()
    
    # 验证文件
    if not file.filename:
        raise HTTPException(400, {"error": "NO_FILENAME", "message": "文件名不能为空"})
    
    # 读取文件内容
    try:
        content = await file.read()
        if len(content) == 0:
            raise HTTPException(400, {"error": "EMPTY_FILE", "message": "上传的音频文件为空"})
        
        # 检查文件大小（限制50MB）
        if len(content) > 50 * 1024 * 1024:
            raise HTTPException(400, {"error": "FILE_TOO_LARGE", "message": "音频文件大小不能超过50MB"})
            
    except Exception as e:
        raise HTTPException(400, {"error": "FILE_READ_FAILED", "message": f"读取文件失败: {str(e)}"})
    
    # 识别音频格式
    audio_format = _guess_audio_format(file.filename, file.content_type)
    supported_formats = {"mp3", "wav", "m4a", "webm", "ogg", "flac"}
    
    if audio_format not in supported_formats:
        raise HTTPException(400, {
            "error": "UNSUPPORTED_FORMAT",
            "message": f"不支持的音频格式: {audio_format}",
            "supported_formats": list(supported_formats)
        })
    
    # 保存文件到本地
    try:
        filename = f"{uuid.uuid4().hex}.{audio_format}"
        file_path = UPLOAD_DIR / filename
        file_path.write_bytes(content)
        
        # 生成公网可访问的URL
        audio_url = f"{PUBLIC_BASE_URL}/static/uploads/{filename}"
        
    except Exception as e:
        raise HTTPException(500, {"error": "FILE_SAVE_FAILED", "message": f"保存文件失败: {str(e)}"})
    
    # 调用ASR
    try:
        asr_result = _call_qiniu_asr(audio_url, audio_format)
        recognized_text = _extract_text_from_asr_result(asr_result)
        
        # 构建响应
        response_data = {
            "success": True,
            "text": recognized_text,
            "audio_url": audio_url,
            "audio_format": audio_format,
            "file_size": len(content),
            "language": language,
            "qiniu_reqid": asr_result.get("reqid"),
            "raw_response": asr_result  # 调试用，生产环境可以移除
        }
        
        # 添加音频信息（如果有）
        if "data" in asr_result and "audio_info" in asr_result["data"]:
            audio_info = asr_result["data"]["audio_info"]
            response_data["audio_duration_ms"] = audio_info.get("duration")
        
        return JSONResponse(response_data)
        
    except HTTPException:
        # 清理失败的文件
        try:
            file_path.unlink(missing_ok=True)
        except:
            pass
        raise
        
    except Exception as e:
        # 清理失败的文件
        try:
            file_path.unlink(missing_ok=True)
        except:
            pass
        
        raise HTTPException(500, {
            "error": "ASR_PROCESSING_FAILED",
            "message": f"语音识别处理失败: {str(e)}"
        })

@router.post("/asr/url")
def speech_to_text_by_url(
    audio_url: str = Form(...),
    audio_format: str = Form("mp3"),
    language: str = Form("auto")
):
    """
    通过URL进行语音识别
    - 适用于音频已经在公网的情况
    - 不需要上传文件
    """
    
    # 验证音频格式
    supported_formats = {"mp3", "wav", "m4a", "webm", "ogg", "flac"}
    if audio_format not in supported_formats:
        raise HTTPException(400, {
            "error": "UNSUPPORTED_FORMAT",
            "message": f"不支持的音频格式: {audio_format}",
            "supported_formats": list(supported_formats)
        })
    
    # 验证URL格式
    if not audio_url.startswith(("http://", "https://")):
        raise HTTPException(400, {"error": "INVALID_URL", "message": "音频URL必须以http://或https://开头"})
    
    try:
        # 调用ASR
        asr_result = _call_qiniu_asr(audio_url, audio_format)
        recognized_text = _extract_text_from_asr_result(asr_result)
        
        response_data = {
            "success": True,
            "text": recognized_text,
            "audio_url": audio_url,
            "audio_format": audio_format,
            "language": language,
            "qiniu_reqid": asr_result.get("reqid"),
            "raw_response": asr_result
        }
        
        # 添加音频信息（如果有）
        if "data" in asr_result and "audio_info" in asr_result["data"]:
            audio_info = asr_result["data"]["audio_info"]
            response_data["audio_duration_ms"] = audio_info.get("duration")
        
        return JSONResponse(response_data)
        
    except Exception as e:
        raise HTTPException(500, {
            "error": "ASR_PROCESSING_FAILED", 
            "message": f"语音识别处理失败: {str(e)}"
        })

@router.get("/asr/test")
def test_asr_setup():
    """
    测试ASR设置
    - 检查API密钥配置
    - 检查公网URL配置
    - 检查目录权限
    """
    
    issues = []
    
    # 检查API密钥
    if not OPENAI_API_KEY:
        issues.append("缺少 OPENAI_API_KEY 环境变量")
    elif len(OPENAI_API_KEY) < 10:
        issues.append("OPENAI_API_KEY 格式可能不正确")
    
    # 检查公网URL
    if PUBLIC_BASE_URL.startswith(("http://localhost", "http://127.0.0.1")):
        issues.append("PUBLIC_BASE_URL 必须设置为公网地址，ASR无法访问localhost")
    
    # 检查目录
    if not UPLOAD_DIR.exists():
        issues.append(f"上传目录不存在: {UPLOAD_DIR}")
    elif not os.access(UPLOAD_DIR, os.W_OK):
        issues.append(f"上传目录无写权限: {UPLOAD_DIR}")
    
    # 检查API连通性
    connectivity_ok = True
    try:
        test_url = f"{OPENAI_BASE_URL}/voice/list"
        headers = {"Authorization": f"Bearer {OPENAI_API_KEY}"}
        response = requests.get(test_url, headers=headers, timeout=10)
        if response.status_code != 200:
            issues.append(f"API连通性测试失败: {response.status_code}")
            connectivity_ok = False
    except Exception as e:
        issues.append(f"API连通性测试异常: {str(e)}")
        connectivity_ok = False
    
    status = "OK" if len(issues) == 0 else "ISSUES_FOUND"
    
    return JSONResponse({
        "status": status,
        "issues": issues,
        "configuration": {
            "api_key_configured": bool(OPENAI_API_KEY),
            "api_key_length": len(OPENAI_API_KEY) if OPENAI_API_KEY else 0,
            "base_url": OPENAI_BASE_URL,
            "public_url": PUBLIC_BASE_URL,
            "upload_dir": str(UPLOAD_DIR),
            "upload_dir_writable": os.access(UPLOAD_DIR, os.W_OK) if UPLOAD_DIR.exists() else False,
            "api_connectivity": connectivity_ok
        },
        "quick_fixes": [
            "设置环境变量: OPENAI_API_KEY=sk-your-key",
            "设置公网地址: PUBLIC_BASE_URL=https://your-domain.com",
            "使用cloudflared: cloudflared tunnel --url http://localhost:8000"
        ]
    })

@router.delete("/cleanup")
def cleanup_audio_files(max_age_hours: int = 24):
    """清理旧的音频文件"""
    import time
    
    cleaned = 0
    errors = []
    current_time = time.time()
    
    if not UPLOAD_DIR.exists():
        return {"message": "上传目录不存在", "cleaned_files": 0}
    
    for file_path in UPLOAD_DIR.glob("*"):
        if file_path.is_file():
            try:
                file_age_seconds = current_time - file_path.stat().st_mtime
                file_age_hours = file_age_seconds / 3600
                
                if file_age_hours > max_age_hours:
                    file_path.unlink()
                    cleaned += 1
            except Exception as e:
                errors.append(f"{file_path.name}: {str(e)}")
    
    return {
        "cleaned_files": cleaned,
        "max_age_hours": max_age_hours,
        "errors": errors
    }
