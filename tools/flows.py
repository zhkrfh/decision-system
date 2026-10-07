# -*- coding: utf-8 -*-
"""flows：看板/指标/国际渠道/监控/一键分发"""
import sys, csv, re, subprocess, datetime, collections, requests
from pathlib import Path
from store import ROOT, DATA, PLOG, MET, append, env
import wx_api

def plan():
    """自动看板：排期队列 + 内容状态 + 台账 pending + 人工事项"""
    import content
    print("== 分发台看板 " + datetime.date.today().isoformat() + " ==")
    import io, contextlib
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        content.queue_cmd(["due"])
        content.status_cmd(["list"])
    print(buf.getvalue().rstrip())
    print("""-- 人工事项（不可自动化）--
公众号 : 发布键（草稿箱→定时/群发）
知乎   : 养号期内不发；15天后 prep zhihu 首答
小红书 : prep xhs → 页面过目 → 发布键 + AI声明弹窗
战绩板 : #1 案例01 进笔试验证截止 11-04""")

def report(period="周"):
    if not MET.exists():
        print("metrics.csv 为空，先回填数据"); return
    agg = collections.defaultdict(dict)
    with open(MET, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            key = (row["platform"], row["title"])
            agg[key][row["metric"]] = agg[key].get(row["metric"], 0) + float(row["value"] or 0)
    print("== 指标汇总（累计）==")
    for (pf, ti), m in sorted(agg.items()):
        s = "  ".join(f"{k}={v:g}" for k, v in sorted(m.items()))
        print(f"  [{pf}] {ti[:20]}  {s}")

def post(provider, title, body_file):
    body = Path(body_file).read_text(encoding="utf-8")
    e = env()
    if provider == "telegram":
        tok = e.get("TELEGRAM_BOT_TOKEN"); chat = e.get("TELEGRAM_CHAT_ID")
        if not tok: raise SystemExit("缺 TELEGRAM_BOT_TOKEN（@BotFather 生成）")
        r = requests.post(f"https://api.telegram.org/bot{tok}/sendMessage",
                          json={"chat_id": chat or "@", "text": f"*{title}*\n\n{body}", "parse_mode": "Markdown"}, timeout=20).json()
        print("telegram:", r.get("ok") or r)
    elif provider == "bluesky":
        hd = e.get("BLUESKY_HANDLE"); pw = e.get("BLUESKY_APP_PASSWORD")
        if not hd: raise SystemExit("缺 BLUESKY_HANDLE/BLUESKY_APP_PASSWORD")
        s = requests.post("https://bsky.social/xrpc/com.atproto.server.createSession", json={"identifier": hd, "password": pw}, timeout=20).json()
        r = requests.post("https://bsky.social/xrpc/com.atproto.repo.createRecord", headers={"Authorization": "Bearer " + s["accessJwt"]}, timeout=20,
            json={"repo": s["did"], "collection": "app.bsky.feed.post", "record": {"text": f"{title}\n\n{body}"[:300], "createdAt": datetime.datetime.now(datetime.timezone.utc).isoformat()}}).json()
        print("bluesky:", "ok" if "uri" in r else r)
    elif provider == "devto":
        key = e.get("DEVTO_API_KEY")
        if not key: raise SystemExit("缺 DEVTO_API_KEY")
        r = requests.post("https://dev.to/api/articles", headers={"api-key": key}, timeout=20,
            json={"article": {"title": title, "body_markdown": body, "published": False}}).json()
        print("devto(draft):", r.get("url") or r)
    else:
        raise SystemExit(f"未知渠道 {provider}")

def monitor(cfg_file=None):
    """低频抓取公开页面，正则提取指标自动回填 metrics.csv。配置行：平台,标题,URL,正则,指标名"""
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
                    print(f"  [miss] {row['title']}"); continue
                try: val = float(m.group(1).replace(",", ""))
                except (IndexError, ValueError): val = 1.0
                append(MET, [row["platform"], row["title"], row["metric"], val])
                print(f"  [ok] {row['title']} {row['metric']}={val:g}"); n += 1
            except Exception as e:
                print(f"  [err] {row['title']}: {e}")
    print(f"monitor 完成，回填 {n} 条（低频使用：每周一次，只抓公开页）")

def dispatch(md_file):
    """一键分发：公众号草稿(API) + 独立站部署(git) + 国际渠道(API) + 手动渠道清单。发布键保留在用户手里。"""
    md = Path(md_file).resolve()
    if not md.exists(): raise SystemExit(f"文件不存在: {md}")
    stem = md.stem
    e = env()
    print(f"== 分发：{stem} ==")
    try:
        subprocess.run([sys.executable, str(ROOT/"tools/md2html.py"), str(md), str(ROOT / "docs/素材" / f"公众号素材_{stem}.html")], check=True)
        html = (ROOT / "docs/素材" / f"公众号素材_{stem}.html").read_text(encoding="utf-8")
        if "演练" in stem:
            print("[公众号] 演练模式：跳过灌稿"); raise ValueError("演练跳过")
        thumb = (ROOT/"thumb_media_id.txt").read_text(encoding="utf-8").strip()
        mid = wx_api.draft_add(stem, html, thumb)
        print(f"[公众号] 草稿 {mid} → 发布键在你手上")
        append(PLOG, ["公众号", stem, "草稿", "dispatch"])
    except Exception as ex:
        print(f"[公众号] {'跳过' if '演练' in str(ex) else '失败'}: {ex}")
    try:
        if stem.startswith("案例"):
            subprocess.run([sys.executable, str(ROOT.parent/"站点/tools_build/build_case.py")], check=True, cwd=str(ROOT.parent/"站点"))
        subprocess.run(["git", "add", "-A"], cwd=str(ROOT.parent/"站点"), check=True)
        subprocess.run(["git", "commit", "-q", "-m", "dispatch: "+stem], cwd=str(ROOT.parent/"站点"))
        subprocess.run(["git", "push", "-q", "origin", "main"], cwd=str(ROOT.parent/"站点"), check=True)
        print("[独立站] 已推送")
        append(PLOG, ["独立站", stem, "已发布", "dispatch"])
    except Exception as ex:
        print(f"[独立站] 失败: {ex}")
    for pf, key in (("telegram", "TELEGRAM_BOT_TOKEN"), ("bluesky", "BLUESKY_HANDLE"), ("devto", "DEVTO_API_KEY")):
        if e.get(key):
            try:
                post(pf, stem, str(md)); append(PLOG, [pf, stem, "已发布", "dispatch"])
            except Exception as ex:
                print(f"[{pf}] 失败: {ex}")
        else:
            print(f"[{pf}] 未授权（token 待配置），跳过")
    print("[手动渠道] 知乎：docs/知乎底稿 → prep zhihu（养号期满后）")
    print("[手动渠道] 小红书：prep xhs → 卡片+正文预填，你按发布")
    print("== 分发完成。发布键：公众号×1，知乎×1，小红书×1 ==")
