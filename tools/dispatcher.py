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
import sys, os, csv, json, datetime, requests
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
                val = float(m.group(1).replace(",", ""))
                _append(MET, [row["platform"], row["title"], row["metric"], val])
                print(f"  [ok] {row['title']} {row['metric']}={val:g}"); n += 1
            except Exception as e:
                print(f"  [err] {row['title']}: {e}")
    print(f"monitor 完成，回填 {n} 条（低频使用：每周一次，只抓公开页，勿提频）")

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
    else: print(__doc__)

if __name__ == "__main__":
    main()
