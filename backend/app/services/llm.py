# backend/app/services/llm.py
from typing import List, Dict
from ..core.config import USE_OPENAI, get_openai_client, get_chat_model
from ..models.skills import SKILL_TEMPLATES, SYSTEM_BASE, SkillName


def build_system_prompt(role_name: str, role_card: Dict, skill: SkillName) -> str:
    """
    根据角色卡与技能拼接系统提示词，限制输出风格，避免元信息。
    """
    parts = [SYSTEM_BASE]
    parts.append(
        f"人物：{role_name}。风格：{role_card.get('style','')}。"
        f"背景要点：{', '.join(role_card.get('backstory', []))}。"
        f"词汇倾向：{', '.join(role_card.get('lexicon', []))}。"
    )
    parts.append(SKILL_TEMPLATES[skill].format(role_name=role_name))
    parts.append("不要输出与人物身份不符的元信息；不要说'作为AI'等话术。")
    return "\n".join(parts)


async def chat(
    role_name: str,
    role_card: Dict,
    history: List[Dict],
    user_text: str,
    skill: SkillName,
) -> str:
    """
    组装对话并调用 LLM。若 LLM 不可用或报错，返回占位回答以保证链路连通。
    """
    # 1) 组系统提示
    system_prompt = build_system_prompt(role_name, role_card, skill)

    # 2) 组消息历史（截取最近 8 轮）
    messages = [{"role": "system", "content": system_prompt}]
    for turn in history[-8:]:
        if turn.get("user"):
            messages.append({"role": "user", "content": turn["user"]})
        if turn.get("assistant"):
            messages.append({"role": "assistant", "content": turn["assistant"]})
    messages.append({"role": "user", "content": user_text})

    # 3) 调用 LLM（来自 .env 的网关与模型）
    if USE_OPENAI:
        client = get_openai_client()
        if client is not None:
            try:
                resp = client.chat.completions.create(
                    model=get_chat_model(),        # 从 .env 读取 OPENAI_CHAT_MODEL
                    messages=messages,
                    temperature=0.6,
                    max_tokens=320,
                )
                text = (resp.choices[0].message.content or "").strip()
                if text:
                    return text
            except Exception as e:
                # 不中断链路，落回占位文案
                print("[WARN] LLM 调用失败，使用占位：", e)

    # 4) 兜底占位回答（LLM 未配置或异常）
    hint = ",".join(role_card.get("lexicon", [])[:2])
    return f"（占位回答）我是{role_name}。{('我常提到：'+hint) if hint else ''} 你刚才说：{user_text[:60]}。"
