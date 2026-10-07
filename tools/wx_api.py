# -*- coding: utf-8 -*-
"""wx_api：公众号 API（token/draft/核验/状态）。凭据在 .env：WX_APPID + 任一含 SECRET 的键"""
import json, datetime, requests
from store import ROOT, PLOG, append, env

def token():
    e = env()
    sec = [v for k, v in e.items() if "SECRET" in k.upper()][0]
    r = requests.get("https://api.weixin.qq.com/cgi-bin/token",
                     params={"grant_type": "client_credential", "appid": e["WX_APPID"], "secret": sec}, timeout=15).json()
    if "access_token" not in r:
        if r.get("errcode") == 40164:
            raise SystemExit(f"[IP 白名单] 当前出口 IP {r['errmsg'].split('invalid ip ')[1].split(' ')[0]} 不在公众号白名单。\n"
                             "解决：mp 后台 → 设置与开发 → 基本配置 → IP 白名单 → 添加该 IP。")
        raise SystemExit(f"token 获取失败: {r}")
    return r["access_token"]

def post(url, payload):
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    return json.loads(requests.post(url, data=body, headers={"Content-Type": "application/json; charset=utf-8"}, timeout=30).content.decode("utf-8"))

def status():
    t = token()
    r = post(f"https://api.weixin.qq.com/cgi-bin/draft/batchget?access_token={t}", {"offset": 0, "count": 10, "no_content": 1})
    if "item" not in r:
        print("draft/batchget:", r); return
    print("== 草稿箱 ==")
    for it in r["item"]:
        for a in it["content"]["news_item"]:
            print(f"  [{datetime.datetime.fromtimestamp(it['update_time']):%m-%d %H:%M}] {a['title']}")
    p = post(f"https://api.weixin.qq.com/cgi-bin/freepublish/batchget?access_token={t}", {"offset": 0, "count": 10, "no_content": 1})
    if "item" in p:
        print("== 已发表 ==")
        for it in p["item"]:
            a = it["content"]["news_item"][0]
            print(f"  [{datetime.datetime.fromtimestamp(it['update_time']):%m-%d %H:%M}] {a['title']}")

def check():
    t = token()
    r = post(f"https://api.weixin.qq.com/cgi-bin/draft/batchget?access_token={t}", {"offset": 0, "count": 10, "no_content": 0})
    bad = []
    for it in r.get("item", []):
        for a in it["content"]["news_item"]:
            c = a["content"]
            issues = []
            if "\\u" in a["title"] or "\\u" in c: issues.append("双重编码")
            for kw in ("52.6", "1.14", "45.3", "+0.3", "27.4"):
                if kw in c: issues.append(f"旧口径残留 {kw}")
            print(("  [OK] " if not issues else "  [!!] ") + a["title"] + ("  ← " + ",".join(issues) if issues else ""))
            if issues: bad.append(a["title"])
    print("核验完成：" + ("全部通过" if not bad else f"{len(bad)} 篇需修"))

def draft_add(title, html, thumb_id):
    t = token()
    r = post(f"https://api.weixin.qq.com/cgi-bin/draft/add?access_token={t}",
             {"articles": [{"title": title[:60], "author": "蔵亥喹荣", "digest": title[:50], "content": html,
                            "thumb_media_id": thumb_id, "need_open_comment": 1, "only_fans_can_comment": 0}]})
    mid = r.get("media_id")
    return mid or f"错误:{r}"
