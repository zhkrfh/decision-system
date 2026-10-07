# -*- coding: utf-8 -*-
"""zhihu_api：知乎数据开放平台（developer.zhihu.com）。GET+大写参数；无发布API（发布走 prep zhihu 浏览器流程）"""
import time, requests
from pathlib import Path
from store import ROOT, env

B = "https://developer.zhihu.com/api/v1/content"
KWS = ["offer 怎么选", "应届生 第一份工作", "跳槽 后悔", "康复专业 就业", "副业 决策"]

def _headers():
    tok = env().get("ZHIHU_ACCESS_SECRET", "")
    if not tok:
        raise SystemExit("缺 ZHIHU_ACCESS_SECRET（.env）")
    return {"Authorization": f"Bearer {tok}", "X-Request-Timestamp": str(int(time.time()))}

def scout():
    """选题侦察：热榜前10 + 垂直关键词搜索 → docs/选题侦察_YYYYMMDD.md"""
    H = _headers()
    out = ["# 知乎选题侦察 " + time.strftime("%Y-%m-%d %H:%M"), ""]
    r = requests.get(f"{B}/hot_list", headers=H, params={"Limit": "10"}, timeout=20)
    out += ["## 热榜（前10）", ""]
    if r.ok and r.json().get("Code") == 0:
        for it in r.json()["Data"]["Items"]:
            out.append(f"- [{it.get('Title','')[:45]}]({it.get('Url','').split('?')[0]})")
    out += ["", "## 垂直搜索（关键词×前2条）", ""]
    for kw in KWS:
        r = requests.get(f"{B}/zhihu_search", headers=H, params={"Query": kw, "Count": "2"}, timeout=20)
        out.append(f"### {kw}")
        if r.ok and r.json().get("Code") == 0:
            for it in (r.json().get("Data") or {}).get("Items", []):
                out.append(f"- [{it.get('Title','')[:45]}]({it.get('Url','').split('?')[0]}) 赞:{it.get('VoteUpCount',0)}")
        else:
            out.append(f"- (失败 {r.status_code})")
        out.append("")
    rep = ROOT / "docs" / ("选题侦察_" + time.strftime("%Y%m%d") + ".md")
    rep.write_text("\n".join(out), encoding="utf-8")
    print("written", rep)
