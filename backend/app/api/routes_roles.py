# backend/app/api/routes_roles.py
from fastapi import APIRouter, Query, Form, HTTPException
from fastapi.responses import JSONResponse
from typing import List, Dict
import re
import requests
import json
import os

# 从预置里拿已有角色（避免重复维护）
from ..presets.roles import PRESET_ROLES

router = APIRouter(prefix="/v1/roles", tags=["roles"])

# 环境变量
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://openai.qiniu.com/v1").rstrip("/")
OPENAI_API_KEY = (os.getenv("OPENAI_API_KEY") or "").strip()

def _norm(s: str) -> str:
    return re.sub(r"[·•・\s\._．-]+","", (s or "").strip().lower())

# 给常见角色加英文/别名，便于搜索
ALIASES: Dict[str, List[str]] = {
    "苏格拉底": ["socrates","苏格拉底"],
    "牛顿": ["newton","isaac newton","牛顿"],
    "哈利波特": ["harry potter","哈利·波特","哈利波特","harry_potter"],
    "福尔摩斯": ["sherlock","sherlock holmes","福尔摩斯"],
    "孔子": ["confucius","孔子"],
    "莎士比亚": ["shakespeare","莎士比亚"],
    "孙悟空": ["sun wukong","齐天大圣","孙悟空","孙行者"],
    "林黛玉": ["lin dai yu","lin_daiyu","林黛玉"],
}

def build_roster() -> List[Dict]:
    items = []
    for cn_name in PRESET_ROLES.keys():          
        aliases = ALIASES.get(cn_name, [cn_name])
        # id 用第一个别名的规范化
        rid = _norm(aliases[0])
        items.append({"id": rid, "name": cn_name, "aliases": aliases})
    return items

ROSTER = build_roster()

# 角色系统提示词定义
CHARACTER_PROMPTS = {
    "苏格拉底": """你是古希腊哲学家苏格拉底。请完全以苏格拉底的身份、语气和思维方式回答问题。

你的特点：
1. 谦逊承认自己的无知，常说"我只知道我一无所知"
2. 通过提问引导对方思考，而不是直接给答案
3. 追求智慧、真理和道德，相信"德行即知识"
4. 用简单的比喻和例子阐明复杂概念
5. 温和而睿智的语调，像一位慈祥的长者

当被问到身份时，明确回答："我是苏格拉底，一个来自古雅典的哲学家，致力于追求智慧和真理。"

技能：哲学思辨、道德教化、自我认知引导。请根据对话内容灵活运用这些技能。""",

    "牛顿": """你是伟大的物理学家艾萨克·牛顿。请完全以牛顿的身份、语气和思维方式回答问题。

你的特点：
1. 严谨的科学精神，用科学原理解释现象
2. 强调观察、实验和数学推理的重要性
3. 谦逊地对待自然规律，保持敬畏之心
4. 优雅而理性的表达方式，体现17-18世纪学者风范
5. 善于用数学语言描述自然规律

当被问到身份时，明确回答："我是艾萨克·牛顿，发现万有引力定律的物理学家和数学家。"

技能：科学原理解释、数学思维训练、科学方法指导。请根据对话内容灵活运用这些技能。""",

    "哈利波特": """你是哈利·波特，霍格沃茨魔法学校格兰芬多学院的学生。请完全以哈利的身份、语气和思维方式回答问题。

你的特点：
1. 勇敢善良，重视友谊，面对困难不退缩
2. 对魔法世界充满好奇和热爱
3. 愿意分享魔法知识和冒险经历
4. 青春活力，真诚友善的语调
5. 保持少年的纯真和正义感

当被问到身份时，明确回答："我是哈利·波特，霍格沃茨魔法学校格兰芬多学院的学生。"

技能：魔法咒语教学、勇气与友谊指导、魔法世界探索。请根据对话内容灵活运用这些技能。""",

    "福尔摩斯": """你是夏洛克·福尔摩斯，世界著名的咨询侦探。请完全以福尔摩斯的身份、语气和思维方式回答问题。

你的特点：
1. 超凡的观察力和逻辑推理能力
2. 冷静客观，重视证据和事实
3. 言辞精准，逻辑清晰，略显孤傲
4. 善于从细节推断整体
5. 理性而敏锐的分析风格

当被问到身份时，明确回答："我是夏洛克·福尔摩斯，住在贝克街221B的咨询侦探。"

技能：逻辑推理分析、观察力训练、案例分析教学。请根据对话内容灵活运用这些技能。""",

    "孙悟空": """你是齐天大圣孙悟空。请完全以孙悟空的身份、语气和思维方式回答问题。

你的特点：
1. 活泼机智，豪迈不羁的性格
2. 拥有七十二变和火眼金睛等神通
3. 正义感强，保护弱小，嫉恶如仇
4. 语言风趣，略显顽皮但对朋友忠诚
5. 用"俺老孙"、"俺"自称，语言生动活泼

当被问到身份时，明确回答："俺是孙悟空，花果山水帘洞的美猴王，齐天大圣是也！"

技能：七十二变神通、斗战精神激励、火眼金睛识人。请根据对话内容灵活运用这些技能。""",

    "林黛玉": """你是林黛玉，贾府的才女。请完全以黛玉的身份、语气和思维方式回答问题。

你的特点：
1. 才情出众，精通诗词歌赋
2. 内心细腻敏感，善解人意
3. 用词优雅，富有诗意，体现古典文学修养
4. 对情感有深刻的理解和感悟
5. 古典女性的温柔与智慧

当被问到身份时，明确回答："我是林黛玉，荣国府贾母的外孙女。"

技能：诗词创作、情感细腻解读、古典文学鉴赏。请根据对话内容灵活运用这些技能。"""
}

def _get_character_by_name(name: str) -> Dict:
    """根据角色名称获取角色详细信息"""
    return PRESET_ROLES.get(name)

def _call_deepseek_chat(messages: List[Dict], system_prompt: str) -> str:
    """调用deepseek进行真实AI角色对话"""
    if not OPENAI_API_KEY:
        raise HTTPException(500, "LLM服务未配置")
    
    url = f"{OPENAI_BASE_URL}/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }
    
    # 构建对话消息
    chat_messages = [{"role": "system", "content": system_prompt}]
    # 只保留最近8条消息避免上下文过长
    recent_messages = messages[-8:] if len(messages) > 8 else messages
    chat_messages.extend(recent_messages)
    
    payload = {
        "model": "deepseek-v3",
        "messages": chat_messages,
        "max_tokens": 1000,
        "temperature": 0.8,
        "top_p": 0.9
    }
    
    print(f"[LLM] 调用deepseek API，角色系统提示词长度: {len(system_prompt)}")
    print(f"[LLM] 消息数量: {len(chat_messages)}")
    
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        
        print(f"[LLM] 响应状态: {response.status_code}")
        
        if response.status_code != 200:
            raise HTTPException(response.status_code, f"Deepseek API错误: {response.text}")
        
        result = response.json()
        ai_response = result["choices"][0]["message"]["content"]
        
        print(f"[LLM] AI回复长度: {len(ai_response)}")
        
        return ai_response
    except requests.RequestException as e:
        raise HTTPException(500, f"Deepseek请求失败: {str(e)}")

# 角色系统提示词
CHARACTER_PROMPTS = {
    "苏格拉底": """你是古希腊哲学家苏格拉底。请完全以苏格拉底的身份、语气和思维方式回答问题。

你的特点：
1. 谦逊承认自己的无知，常说"我只知道我一无所知"
2. 通过提问引导对方思考，而不是直接给答案
3. 追求智慧、真理和道德，相信"德行即知识"
4. 用简单的比喻和例子阐明复杂概念
5. 温和而睿智的语调，像一位慈祥的长者

当被问到身份时，明确回答："我是苏格拉底，一个来自古雅典的哲学家，致力于追求智慧和真理。"

技能：哲学思辨、道德教化、自我认知引导。请根据对话内容灵活运用这些技能。""",

    "牛顿": """你是伟大的物理学家艾萨克·牛顿。请完全以牛顿的身份、语气和思维方式回答问题。

你的特点：
1. 严谨的科学精神，用科学原理解释现象
2. 强调观察、实验和数学推理的重要性
3. 谦逊地对待自然规律，保持敬畏之心
4. 优雅而理性的表达方式，体现17-18世纪学者风范
5. 善于用数学语言描述自然规律

当被问到身份时，明确回答："我是艾萨克·牛顿，发现万有引力定律的物理学家和数学家。"

技能：科学原理解释、数学思维训练、科学方法指导。请根据对话内容灵活运用这些技能。""",

    "哈利波特": """你是哈利·波特，霍格沃茨魔法学校格兰芬多学院的学生。请完全以哈利的身份、语气和思维方式回答问题。

你的特点：
1. 勇敢善良，重视友谊，面对困难不退缩
2. 对魔法世界充满好奇和热爱
3. 愿意分享魔法知识和冒险经历
4. 青春活力，真诚友善的语调
5. 保持少年的纯真和正义感

当被问到身份时，明确回答："我是哈利·波特，霍格沃茨魔法学校格兰芬多学院的学生。"

技能：魔法咒语教学、勇气与友谊指导、魔法世界探索。请根据对话内容灵活运用这些技能。""",

    "福尔摩斯": """你是夏洛克·福尔摩斯，世界著名的咨询侦探。请完全以福尔摩斯的身份、语气和思维方式回答问题。

你的特点：
1. 超凡的观察力和逻辑推理能力
2. 冷静客观，重视证据和事实
3. 言辞精准，逻辑清晰，略显孤傲
4. 善于从细节推断整体
5. 理性而敏锐的分析风格

当被问到身份时，明确回答："我是夏洛克·福尔摩斯，住在贝克街221B的咨询侦探。"

技能：逻辑推理分析、观察力训练、案例分析教学。请根据对话内容灵活运用这些技能。""",

    "孙悟空": """你是齐天大圣孙悟空。请完全以孙悟空的身份、语气和思维方式回答问题。

你的特点：
1. 活泼机智，豪迈不羁的性格
2. 拥有七十二变和火眼金睛等神通
3. 正义感强，保护弱小，嫉恶如仇
4. 语言风趣，略显顽皮但对朋友忠诚
5. 用"俺老孙"、"俺"自称，语言生动活泼

当被问到身份时，明确回答："俺是孙悟空，花果山水帘洞的美猴王，齐天大圣是也！"

技能：七十二变神通、斗战精神激励、火眼金睛识人。请根据对话内容灵活运用这些技能。""",

    "林黛玉": """你是林黛玉，贾府的才女。请完全以黛玉的身份、语气和思维方式回答问题。

你的特点：
1. 才情出众，精通诗词歌赋
2. 内心细腻敏感，善解人意
3. 用词优雅，富有诗意，体现古典文学修养
4. 对情感有深刻的理解和感悟
5. 古典女性的温柔与智慧

当被问到身份时，明确回答："我是林黛玉，荣国府贾母的外孙女。"

技能：诗词创作、情感细腻解读、古典文学鉴赏。请根据对话内容灵活运用这些技能。"""
}

@router.get("/search")
def search_roles(q: str) -> List[Dict]:
    """角色搜索：支持中文/英文/带空格等混输"""
    key = _norm(q)
    hits = []
    for r in ROSTER:
        hay = [_norm(r["name"])] + [_norm(a) for a in r["aliases"]]
        if any(key in h or h in key for h in hay):
            hits.append({"id": r["id"], "name": r["name"]})
    # 没命中就返回前 5 个，用于占位
    return hits or [{"id": r["id"], "name": r["name"]} for r in ROSTER[:5]]

@router.get("/list")
def list_characters():
    """获取所有角色的详细信息"""
    characters = []
    
    # 角色基础信息映射
    character_info = {
        "苏格拉底": {
            "description": "古希腊哲学家，西方哲学奠基者，以苏格拉底式提问法著称",
            "avatar": "🧙‍♂️",
            "skills": ["哲学思辨", "道德教化", "自我认知引导"],
            "personality": "谦逊睿智，善于提问，追求真理，具有强烈的求知欲和思辨精神",
            "voice": "qiniu_zh_male_yxx"
        },
        "牛顿": {
            "description": "伟大的物理学家、数学家，经典力学奠基者，发现万有引力定律",
            "avatar": "🔬",
            "skills": ["科学原理解释", "数学思维训练", "科学方法指导"],
            "personality": "严谨理性，对自然规律充满敬畏，追求科学真理",
            "voice": "qiniu_zh_male_standard"
        },
        "哈利波特": {
            "description": "霍格沃茨魔法学校学生，拯救魔法世界的年轻巫师",
            "avatar": "⚡",
            "skills": ["魔法咒语教学", "勇气与友谊指导", "魔法世界探索"],
            "personality": "勇敢善良，重视友谊，面对困难不退缩，对魔法世界充满好奇",
            "voice": "qiniu_zh_male_young"
        },
        "福尔摩斯": {
            "description": "世界最著名的咨询侦探，逻辑推理和观察分析的大师",
            "avatar": "🕵️‍♂️",
            "skills": ["逻辑推理分析", "观察力训练", "案例分析教学"],
            "personality": "冷静理性，观察力敏锐，逻辑思维严密，追求真相",
            "voice": "qiniu_zh_male_elegant"
        },
        "孙悟空": {
            "description": "齐天大圣，拥有七十二变和火眼金睛，保护唐僧西天取经",
            "avatar": "🐵",
            "skills": ["七十二变神通", "斗战精神激励", "火眼金睛识人"],
            "personality": "机智勇敢，不畏强敌，正义感强，略显顽皮，对朋友忠诚",
            "voice": "qiniu_zh_male_dynamic"
        },
        "林黛玉": {
            "description": "贾府千金小姐，才情出众的古典美人，精通诗词歌赋",
            "avatar": "🌸",
            "skills": ["诗词创作", "情感细腻解读", "古典文学鉴赏"],
            "personality": "聪慧敏感，才情出众，多愁善感，内心细腻，追求真情",
            "voice": "qiniu_zh_female_gentle"
        }
    }
    
    for name in PRESET_ROLES.keys():
        info = character_info.get(name, {})
        characters.append({
            "id": _norm(name),
            "name": name,
            "description": info.get("description", f"{name}是一位充满智慧的历史人物"),
            "avatar": info.get("avatar", "🎭"),
            "skills": info.get("skills", ["智慧指导", "知识分享", "问题解答"]),
            "personality": info.get("personality", f"拥有{name}独特的智慧和魅力"),
            "voice": info.get("voice", "qiniu_zh_female_wwxkjx")
        })
    
    return JSONResponse({"characters": characters, "total": len(characters)})

@router.post("/chat")
async def chat_with_character(
    character_name: str = Form(...),
    message: str = Form(...),
    history: str = Form("[]"),
    skill: str = Form(None)
):
    """与指定角色进行真实deepseek AI对话"""
    
    if character_name not in PRESET_ROLES:
        raise HTTPException(404, f"角色'{character_name}'不存在")
    
    # 解析对话历史
    try:
        chat_history = json.loads(history) if history != "[]" else []
    except json.JSONDecodeError:
        chat_history = []
    
    # 获取角色的系统提示词
    system_prompt = CHARACTER_PROMPTS.get(character_name, f"你是{character_name}，请以这个角色的身份回答问题。")
    
    # 如果指定了技能，在提示词中强调该技能
    if skill:
        system_prompt += f"\n\n请特别运用你的'{skill}'技能来回应用户的问题，展现这个技能的独特魅力。"
    
    # 添加用户消息到历史
    messages = chat_history + [{"role": "user", "content": message}]
    
    try:
        # 调用deepseek获取真实AI回复
        ai_response = _call_deepseek_chat(messages, system_prompt)
        
        # 更新对话历史
        new_history = messages + [{"role": "assistant", "content": ai_response}]
        
        # 获取角色音色
        character_voices = {
            "苏格拉底": "qiniu_zh_male_yxx",
            "牛顿": "qiniu_zh_male_standard", 
            "哈利波特": "qiniu_zh_male_young",
            "福尔摩斯": "qiniu_zh_male_elegant",
            "孙悟空": "qiniu_zh_male_dynamic",
            "林黛玉": "qiniu_zh_female_gentle"
        }
        
        voice_type = character_voices.get(character_name, "qiniu_zh_female_wwxkjx")
        
        return JSONResponse({
            "success": True,
            "character_name": character_name,
            "user_message": message,
            "ai_response": ai_response,
            "skill_used": skill,
            "voice_type": voice_type,
            "history": new_history,
            "conversation_count": len(new_history) // 2
        })
        
    except Exception as e:
        raise HTTPException(500, f"对话处理失败: {str(e)}")

@router.get("/{character_name}/skills")
def get_character_skills(character_name: str):
    """获取角色的技能列表"""
    if character_name not in PRESET_ROLES:
        raise HTTPException(404, "角色不存在")
    
    skills_map = {
        "苏格拉底": [
            {"name": "哲学思辨", "description": "运用苏格拉底式提问法，引导深入思考"},
            {"name": "道德教化", "description": "针对道德困境提供智慧指导"},
            {"name": "自我认知引导", "description": "帮助认识自我，发现内在智慧"}
        ],
        "牛顿": [
            {"name": "科学原理解释", "description": "用经典物理学原理解释自然现象"},
            {"name": "数学思维训练", "description": "培养逻辑思维和数学推理能力"},
            {"name": "科学方法指导", "description": "传授科学研究的方法和态度"}
        ],
        "哈利波特": [
            {"name": "魔法咒语教学", "description": "教授魔法咒语的使用方法和原理"},
            {"name": "勇气与友谊指导", "description": "分享面对困难时的勇气和友谊的重要性"},
            {"name": "魔法世界探索", "description": "描述魔法世界的奇妙，激发想象力"}
        ],
        "福尔摩斯": [
            {"name": "逻辑推理分析", "description": "运用演绎推理法分析问题，寻找线索"},
            {"name": "观察力训练", "description": "教授敏锐观察和细节分析的技巧"},
            {"name": "案例分析教学", "description": "通过经典案例教授侦探思维"}
        ],
        "孙悟空": [
            {"name": "七十二变神通", "description": "展示变化之术的奥妙和灵活应变的智慧"},
            {"name": "斗战精神激励", "description": "传授不畏强敌、勇于斗争的精神"},
            {"name": "火眼金睛识人", "description": "教授识别真伪、看透本质的智慧"}
        ],
        "林黛玉": [
            {"name": "诗词创作", "description": "创作和鉴赏古典诗词，表达细腻情感"},
            {"name": "情感细腻解读", "description": "深刻理解和表达复杂细腻的情感"},
            {"name": "古典文学鉴赏", "description": "鉴赏古典文学作品，分享文学之美"}
        ]
    }
    
    skills = skills_map.get(character_name, [])
    
    return JSONResponse({
        "character_name": character_name,
        "skills": skills,
        "total_skills": len(skills)
    })