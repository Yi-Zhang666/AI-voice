from typing import List, Dict
from ..core.config import USE_OPENAI, get_openai_client
from ..models.skills import SKILL_TEMPLATES, SYSTEM_BASE, SkillName

def build_system_prompt(role_name: str, role_card: Dict, skill: SkillName) -> str:
    parts = [SYSTEM_BASE]
    parts.append(
        f"人物：{role_name}。风格：{role_card.get('style','')}。"
        f"背景要点：{', '.join(role_card.get('backstory', []))}。"
        f"词汇倾向：{', '.join(role_card.get('lexicon', []))}。"
    )
    parts.append(SKILL_TEMPLATES[skill].format(role_name=role_name))
    parts.append("不要输出与人物身份不符的元信息；不要说'作为AI'等话术。")
    return "\n".join(parts)

async def chat(role_name: str, role_card: Dict, history: List[Dict], user_text: str, skill: SkillName) -> str:
    system_prompt = build_system_prompt(role_name, role_card, skill)
    messages = [{"role":"system","content":system_prompt}]
    for turn in history[-8:]:
        messages += [{"role":"user","content":turn["user"]},
                     {"role":"assistant","content":turn["assistant"]}]
    messages.append({"role":"user","content":user_text})

    if USE_OPENAI:
        client = get_openai_client()
        try:
            resp = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                temperature=0.6,
                max_tokens=320,
            )
            return resp.choices[0].message.content.strip()
        except Exception as e:
            print("[WARN] LLM 调用失败，使用占位：", e)

    hint = ",".join(role_card.get("lexicon", [])[:2])
    return f"（占位回答）我是{role_name}。{('我常提到：'+hint) if hint else ''} 你刚才说：{user_text[:60]}。"
