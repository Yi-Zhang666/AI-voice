# backend/app/api/routes_roles.py
from fastapi import APIRouter, Query
from typing import List, Dict
import re

# 从预置里拿已有角色（避免重复维护）
from ..presets.roles import PRESET_ROLES

router = APIRouter(prefix="/v1/roles", tags=["roles"])

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
