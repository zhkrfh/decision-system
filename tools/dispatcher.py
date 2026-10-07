# -*- coding: utf-8 -*-
"""分发台 Dispatcher v0.1
用法:
  python tools/dispatcher.py plan                 # 各平台待办看板
  python tools/dispatcher.py wx-check             # 公众号草稿箱核验(乱码/口径)
  python tools/dispatcher.py wx-status            # 公众号发布状态
  python tools/dispatcher.py log <平台> <标题> <状态> [备注]   # 记录发布
  python tools/dispatcher.py metric <平台> <标题> <指标> <数值> # 回填指标
  python tools/dispatcher.py report [周|月]       # 指标汇总
  python tools/dispatcher.py post telegram <标题> <正文文件>   # 发 Telegram 频道
  python tools/dispatcher.py post bluesky <标题> <正文文件>    # 发 Bluesky
  python tools/dispatcher.py post devto  <标题> <正文文件>     # 发 dev.to 文章
"""
import sys, os, csv, json, re, datetime, requests
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"; DATA.mkdir(exist_ok=True)
PLOG = DATA / "publish_log.csv"; MET = DATA / "metrics.csv"

def _env():
    env = {}
    for l in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        if "=" in l:
            k, v = l.strip().split("=", 1); env[k] = v
    return env

def _token():
    env = _env()
    sec = [v for k, v in env.items() if "SECRET" in k.upper()][0]
    r = requests.get("https://api.weixin.qq.com/cgi-bin/token",
                     params={"grant_type": "client_credential", "appid": env["WX_APPID"], "secret": sec}, timeout=15).json()
    if "access_token" not in r:
        if r.get("errcode") == 40164:
            raise SystemExit(f"[IP 白名单] 当前出口 IP {r['errmsg'].split('invalid ip ')[1].split(' ')[0]} 不在公众号白名单。\n"
                             "解决：mp 后台 → 设置与开发 → 基本配置 → IP 白名单 → 添加该 IP。")
        raise SystemExit(f"token 获取失败: {r}")
    return r["access_token"]

def _post(url, payload):
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    return json.loads(requests.post(url, data=body, headers={"Content-Type": "application/json; charset=utf-8"}, timeout=30).content.decode("utf-8"))

def wx_status():
    t = _token()
    r = _post(f"https://api.weixin.qq.com/cgi-bin/draft/batchget?access_token={t}", {"offset": 0, "count": 10, "no_content": 1})
    if "item" not in r:
        print("draft/batchget:", r); return
    print("== 草稿箱 ==")
    for it in r["item"]:
        for a in it["content"]["news_item"]:
            print(f"  [{it['update_time'] and datetime.datetime.fromtimestamp(it['update_time']):%m-%d %H:%M}] {a['title']}")
    p = _post(f"https://api.weixin.qq.com/cgi-bin/freepublish/batchget?access_token={t}", {"offset": 0, "count": 10, "no_content": 1})
    if "item" in p:
        print("== 已发表 ==")
        for it in p["item"]:
            a = it["content"]["news_item"][0]
            print(f"  [{datetime.datetime.fromtimestamp(it['update_time']):%m-%d %H:%M}] {a['title']}")

def wx_check():
    t = _token()
    r = _post(f"https://api.weixin.qq.com/cgi-bin/draft/batchget?access_token={t}", {"offset": 0, "count": 10, "no_content": 0})
    bad = []
    for it in r.get("item", []):
        for a in it["content"]["news_item"]:
            c = a["content"]
            issues = []
            if "\\u" in a["title"] or "\\u" in c: issues.append("双重编码")
            for kw in ("52.6", "1.14", "45.3", "+0.3", "27.4"):
                if kw in c: issues.append(f"旧口径残留 {kw}")
            if "?" * 0 and False: pass
            print(("  [OK] " if not issues else "  [!!] ") + a["title"] + ("  ← " + ",".join(issues) if issues else ""))
            if issues: bad.append(a["title"])
    print("核验完成：" + ("全部通过" if not bad else f"{len(bad)} 篇需修"))

def _append(path, row):
    new = not path.exists()
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new: w.writerow(["date"] + row_headers[path])
        w.writerow([datetime.date.today().isoformat()] + row)

row_headers = {PLOG: ["platform", "title", "status", "note"], MET: ["platform", "title", "metric", "value"]}

def plan():
    print("""== 本周待办看板（手工维护区，按大纲 v2.2）==
公众号 : 已自动化。案例01 已发布；连载02 待 10-13 定时
知乎   : [用户] 注册→四关核验选题→存底稿→15天后发首答（底稿: docs/知乎底稿_案例01回答.md）
小红书 : [用户] 注册→第3天起发 assets/xhs/卡1-卡5（降敏版，勾选AI辅助）
战绩板 : #1 案例01 进笔试验证截止 11-04，出结果即登记
合集   : [用户] 后台手动创建（信息见对话记录）""")

def report(period="周"):
    if not MET.exists():
        print("metrics.csv 为空，先回填数据"); return
    import collections
    agg = collections.defaultdict(dict)
    with open(MET, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            key = (row["platform"], row["title"])
            agg[key][row["metric"]] = agg[key].get(row["metric"], 0) + float(row["value"] or 0)
    print(f"== 指标汇总（累计）==")
    for (pf, ti), m in sorted(agg.items()):
        s = "  ".join(f"{k}={v:g}" for k, v in sorted(m.items()))
        print(f"  [{pf}] {ti[:20]}  {s}")


def post(provider, title, body_file):
    body = Path(body_file).read_text(encoding="utf-8")
    env = _env()
    if provider == "telegram":
        tok = env.get("TELEGRAM_BOT_TOKEN"); chat = env.get("TELEGRAM_CHAT_ID")
        if not tok: raise SystemExit("缺 TELEGRAM_BOT_TOKEN（@BotFather 生成，见 docs/国际渠道自动化规划.md）")
        u = f"https://api.telegram.org/bot{tok}/sendMessage"
        r = requests.post(u, json={"chat_id": chat or "@", "text": f"*{title}*\n\n{body}", "parse_mode": "Markdown"}, timeout=20).json()
        print("telegram:", r.get("ok") or r)
    elif provider == "bluesky":
        hd = env.get("BLUESKY_HANDLE"); pw = env.get("BLUESKY_APP_PASSWORD")
        if not hd: raise SystemExit("缺 BLUESKY_HANDLE/BLUESKY_APP_PASSWORD（bsky.app → App Passwords）")
        s = requests.post("https://bsky.social/xrpc/com.atproto.server.createSession", json={"identifier": hd, "password": pw}, timeout=20).json()
        r = requests.post("https://bsky.social/xrpc/com.atproto.repo.createRecord", headers={"Authorization": "Bearer " + s["accessJwt"]}, timeout=20,
            json={"repo": s["did"], "collection": "app.bsky.feed.post", "record": {"text": f"{title}\n\n{body}"[:300], "createdAt": datetime.datetime.now(datetime.timezone.utc).isoformat()}}).json()
        print("bluesky:", "ok" if "uri" in r else r)
    elif provider == "devto":
        key = env.get("DEVTO_API_KEY")
        if not key: raise SystemExit("缺 DEVTO_API_KEY（dev.to → Settings → Extensions → API Keys）")
        r = requests.post("https://dev.to/api/articles", headers={"api-key": key}, timeout=20,
            json={"article": {"title": title, "body_markdown": body, "published": False}}).json()
        print("devto(draft):", r.get("url") or r)
    else:
        raise SystemExit(f"未知渠道 {provider}")

MONCFG = ROOT / "data" / "monitor_urls.csv"

def monitor(cfg_file=None):
    """低频抓取公开页面，正则提取指标自动回填 metrics.csv。配置行：平台,标题(匹配关键词),URL,提取正则,指标名"""
    cfgp = ROOT / "data" / (cfg_file or "monitor_urls.csv")
    if not cfgp.exists():
        raise SystemExit(f"先创建 {cfgp}，每行: 平台,标题关键词,URL,正则,指标名")
    ua = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    n = 0
    with open(cfgp, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            try:
                html = requests.get(row["url"], headers=ua, timeout=20).text
                m = re.search(row["pattern"], html)
                if not m:
                    print(f"  [miss] {row['title']}（页面结构可能变化，或需登录）"); continue
                try:
                    val = float(m.group(1).replace(",", ""))
                except (IndexError, ValueError):
                    val = 1.0  # 无捕获组=连通性指标，命中即记 1
                _append(MET, [row["platform"], row["title"], row["metric"], val])
                print(f"  [ok] {row['title']} {row['metric']}={val:g}"); n += 1
            except Exception as e:
                print(f"  [err] {row['title']}: {e}")
    print(f"monitor 完成，回填 {n} 条（低频使用：每周一次，只抓公开页，勿提频）")

def dispatch(md_file):
    """一键分发：公众号草稿(API) + 独立站部署(git) + 国际渠道(API) + 手动渠道产物清单。发布键仅保留在公众号后台与知乎/小红书网页。"""
    import subprocess
    md = Path(md_file).resolve()
    if not md.exists(): raise SystemExit(f"文件不存在: {md}")
    stem = md.stem
    env = _env()
    print(f"== 分发：{stem} ==")
    # 1 公众号素材+灌稿（演练模式：文件名含"演练"则跳过灌稿）
    try:
        subprocess.run([sys.executable, str(ROOT/"tools/md2html.py"), str(md), str(ROOT / "docs/素材" / f"公众号素材_{stem}.html")], check=True)
        html = (ROOT / "docs/素材" / f"公众号素材_{stem}.html").read_text(encoding="utf-8")
        if "演练" in stem:
            print("[公众号] 演练模式：跳过灌稿")
            raise ValueError("演练跳过")
        t = _token()
        r = _post(f"https://api.weixin.qq.com/cgi-bin/draft/add?access_token={t}",
                  {"articles": [{"title": stem[:60], "author": "蔵亥喹荣", "digest": stem[:50], "content": html,
                    "thumb_media_id": (ROOT/"thumb_media_id.txt").read_text(encoding="utf-8").strip(),
                    "need_open_comment": 1, "only_fans_can_comment": 0}]})
        print(f"[公众号] 草稿 {r.get('media_id') or r} → 发布键在你手上（后台定时/发表）")
        _append(PLOG, ["公众号", stem, "草稿", "dispatch"])
    except Exception as e:
        print(f"[公众号] {'跳过' if '演练' in str(e) else '失败'}: {e}")
    # 2 独立站（若为案例页则重建，然后 push）
    try:
        if stem.startswith("案例"):
            subprocess.run([sys.executable, str(ROOT.parent/"站点/tools_build/build_case.py")], check=True, cwd=str(ROOT.parent/"站点"))
        subprocess.run(["git", "add", "-A"], cwd=str(ROOT.parent/"站点"), check=True)
        subprocess.run(["git", "commit", "-q", "-m", "dispatch: "+stem], cwd=str(ROOT.parent/"站点"))
        subprocess.run(["git", "push", "-q", "origin", "main"], cwd=str(ROOT.parent/"站点"), check=True)
        print("[独立站] 已推送，Pages 自动重建")
        _append(PLOG, ["独立站", stem, "已发布", "dispatch"])
    except Exception as e:
        print(f"[独立站] 失败: {e}")
    # 3 国际渠道（有凭据则直发，无则提示）
    for pf in ("telegram", "bluesky", "devto"):
        key = {"telegram": "TELEGRAM_BOT_TOKEN", "bluesky": "BLUESKY_HANDLE", "devto": "DEVTO_API_KEY"}[pf]
        if env.get(key):
            try:
                post(pf, stem, str(md)); _append(PLOG, [pf, stem, "已发布", "dispatch"])
            except Exception as e:
                print(f"[{pf}] 失败: {e}")
        else:
            print(f"[{pf}] 未授权（token 待配置），跳过")
    # 4 手动渠道产物清单
    print("[手动渠道] 知乎：docs/知乎底稿 → App 内贴入存草稿，你按发布")
    print("[手动渠道] 小红书：assets/xhs/ 卡片 → App 上传，你按发布")
    print("== 分发完成。发布键：公众号×1，知乎×1，小红书×1 ==")

def main():

    a = sys.argv[1:] 
    if not a: print(__doc__); return
    cmd = a[0]
    if cmd == "plan": plan()
    elif cmd == "wx-status": wx_status()
    elif cmd == "wx-check": wx_check()
    elif cmd == "log": _append(PLOG, [a[1], a[2], a[3], a[4] if len(a) > 4 else ""]); print("logged")
    elif cmd == "metric": _append(MET, [a[1], a[2], a[3], a[4]]); print("metric logged")
    elif cmd == "report": report(*(a[1:2] or ["周"]))
    elif cmd == "post": post(a[1], a[2], a[3])
    elif cmd == "monitor": monitor(a[2] if len(a) > 2 else None)
    elif cmd == "dispatch": dispatch(a[1])
    elif cmd == "zh-scout": zh_scout()
    else: print(__doc__)



def zh_scout():
    """选题侦察：知乎热榜+站内搜索（developer.zhihu.com 开放平台）"""
    import os, requests, time
    from pathlib import Path as _P
    tok = _env().get("ZHIHU_ACCESS_SECRET", "")
    if not tok:
        raise ValueError("缺 ZHIHU_ACCESS_SECRET（.env）")
    H = {"Authorization": f"Bearer {tok}", "X-Request-Timestamp": str(int(time.time()))}
    B = "https://developer.zhihu.com/api/v1/content"
    kws = ["offer 怎么选", "应届生 第一份工作", "跳槽 后悔", "康复专业 就业", "副业 决策"]
    out = ["# 知乎选题侦察 " + time.strftime("%Y-%m-%d %H:%M"), ""]
    r = requests.get(f"{B}/hot_list", headers=H, params={"Limit": "10"}, timeout=20)
    out += ["## 热榜（前10）", ""]
    if r.ok and r.json().get("Code") == 0:
        for it in r.json()["Data"]["Items"]:
            out.append(f"- [{it.get('Title','')[:45]}]({it.get('Url','').split('?')[0]})")
    out += ["", "## 垂直搜索（关键词×前2条）", ""]
    for kw in kws:
        r = requests.get(f"{B}/zhihu_search", headers=H, params={"Query": kw, "Count": "2"}, timeout=20)
        out.append(f"### {kw}")
        if r.ok and r.json().get("Code") == 0:
            for it in (r.json().get("Data") or {}).get("Items", []):
                out.append(f"- [{it.get('Title','')[:45]}]({it.get('Url','').split('?')[0]}) 赞:{it.get('VoteUpCount',0)}")
        else:
            out.append(f"- (失败 {r.status_code})")
        out.append("")
    report = _P("docs/选题侦察_" + time.strftime("%Y%m%d") + ".md")
    report.write_text("\n".join(out), encoding="utf-8")
    print("written", report)

if __name__ == "__main__":
    main()
