# -*- coding: utf-8 -*-
"""公众号草稿箱灌稿脚本（路径 B）
用法：python wechat_draft.py <正文html路径> <标题> [作者] [摘要]
读取同目录 .env 的 WX_APPID / WX_APPSECRET。凭据不打印、不外传。
"""
import sys, os, json, urllib.request, urllib.parse

BASE = os.path.dirname(os.path.abspath(__file__))
env = {}
with open(os.path.join(BASE, ".env"), encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()

APPID, SECRET = env["WX_APPID"], env["WX_APPSECRET"]

def api(url, payload=None):
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload else None
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode("utf-8"))

# 上传封面图获取 thumb_media_id（缓存复用）
import requests
def get_thumb():
    cache = os.path.join(BASE, "thumb_media_id.txt")
    if os.path.exists(cache):
        mid = open(cache, encoding="utf-8").read().strip()
        if mid:
            return mid
    cover = os.path.join(BASE, "cover.jpg")
    with open(cover, "rb") as f:
        r = requests.post(
            f"https://api.weixin.qq.com/cgi-bin/material/add_material",
            params={"access_token": T, "type": "image"},
            files={"media": ("cover.jpg", f, "image/jpeg")}, timeout=60)
        res = r.json()
    if "media_id" not in res:
        print("UPLOAD_FAIL:", json.dumps(res, ensure_ascii=False)); sys.exit(1)
    open(cache, "w").write(res["media_id"])
    return res["media_id"]
tok = api(f"https://api.weixin.qq.com/cgi-bin/token?grant_type=client_credential&appid={APPID}&secret={SECRET}")
if "access_token" not in tok:
    print("TOKEN_FAIL:", tok.get("errcode"), tok.get("errmsg")); sys.exit(1)
T = tok["access_token"]
THUMB = get_thumb()

html_path, title = sys.argv[1], sys.argv[2]
author = sys.argv[3] if len(sys.argv) > 3 else "蔵亥喹荣"
digest = sys.argv[4] if len(sys.argv) > 4 else ""
content = open(html_path, encoding="utf-8").read()

r = api(f"https://api.weixin.qq.com/cgi-bin/draft/add?access_token={T}",
        {"articles": [{"title": title[:32], "author": author[:16],
                       "digest": digest[:120], "content": content,
                       "thumb_media_id": THUMB, "need_open_comment": 1, "only_fans_can_comment": 0}]})
print("DRAFT_ADD:", json.dumps(r, ensure_ascii=False))
