import json
from typing import Dict
from ..core.config import USE_OPENAI, get_openai_client
from ..presets.roles import PRESET_ROLES

def build_role_card(role_name: str) -> Dict:
    if role_name in PRESET_ROLES:
        return PRESET_ROLES[role_name]

    if USE_OPENAI:
        client = get_openai_client()
        try:
            resp = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role":"system","content":"仅输出 JSON；包含 style, backstory(list), lexicon(list), taboo(list)。"},
                    {"role":"user","content": f"为人物『{role_name}』生成扮演卡；避免暴露AI身份。"}
                ],
                temperature=0.4
            )
            data = json.loads(resp.choices[0].message.content)
            return {
                "style": data.get("style",""),
                "backstory": data.get("backstory",[]),
                "lexicon": data.get("lexicon",[]),
                "taboo": data.get("taboo",["AI","模型"]),
            }
        except Exception as e:
            print("[WARN] 生成角色卡失败:", e)

    return {"style": f"你是{role_name}，保持该人物常见口吻与价值观。",
            "backstory": [], "lexicon": [], "taboo": ["AI","语言模型"]}
