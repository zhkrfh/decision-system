# -*- coding: utf-8 -*-
"""prep：发布前预填流程（蚁小二"草稿箱+停在发布键"模式）。
自动化边界：prep 负责资产就绪+台账登记+操作规程输出；预填执行由灵犀浏览器会话完成，发布键永远由用户按下。"""
import sys, subprocess
from pathlib import Path
from store import ROOT, LED, append, ledger_rows

XHS_URL = "https://creator.xiaohongshu.com/publish/publish?from=tab_switch"

def _ledger_get(item):
    for r in reversed(ledger_rows()):
        if r["item"] == item: return r
    return None

def prep_xhs(item="案例05_资格期断桥"):
    cards = sorted((ROOT / "assets/xhs").glob("卡*.png"))
    body = ROOT / "docs" / "小红书发布包" / f"{item}_小红书正文.txt"
    print(f"== prep xhs：{item} ==")
    print(f"卡片 {len(cards)} 张：" + ("全部就绪" if len(cards) == 5 else "!! 不足5张：") + ",".join(c.name for c in cards))
    if body.exists():
        txt = body.read_text(encoding="utf-8")
        print(f"正文就绪：{len(txt)} 字 → {body}")
    else:
        print(f"!! 正文缺失：{body}（先跑 mp_adapt 小红书端）")
    append(LED, [item, "小红书", "pending_publish", "", "prep xhs"])
    print(f"""-- 操作规程（灵犀浏览器会话执行，发布键归你）--
1. 灵犀打开 {XHS_URL}
2. 「上传图文」tab → file input 一次传 5 张卡（multiple）
3. 标题框 input[placeholder^="填写标题"] ← 注入标题
4. 正文 #post-textarea → focus + Range 末尾 + execCommand('insertText') 注入正文
5. 话题：编辑器末尾插入" #关键词"触发联想弹层 → 过滤点击（×4）
6. TreeWalker 核验无孤立 #；「更多设置」内无 AI 声明项（发布弹窗时勾选）
7. 停在「发布笔记」前 → 你过目后亲自按下 → 回传浏览/点赞/收藏
台账已登记 pending_publish；发布后运行：ledger confirm {item} --status published --ref <笔记链接>""")

def ledger_cmd(args):
    """ledger list / ledger confirm <稿名> --status X --ref URL"""
    if not args or args[0] == "list":
        rows = ledger_rows()
        print(f"== ledger（{len(rows)} 条）==")
        for r in rows:
            print(f"  [{r['item']}] {r['platform']} {r['status']} {r['ref']} {r['note']}")
        return
    if args[0] == "confirm":
        item, status, ref = args[1], "published", ""
        i = 2
        while i < len(args):
            if args[i] == "--status": status = args[i+1]; i += 2
            elif args[i] == "--ref": ref = args[i+1]; i += 2
            else: i += 1
        from store import ledger_update
        r = ledger_update(item, status, ref)
        print(f"[ledger] {item} → {status} {ref}")
        if status == "published":
            append(__import__("store").PLOG, [r["platform"], item, "已发布", ref])
        return
    print(__doc__)

# ---- 浏览器故障恢复规程（SOP）----
# prep 期间浏览器通信失败时的处置顺序：
# 1. execute_script 前先探测（location.href），失败即停，同一页面最多试 2 次
# 2. 报 "Another debugger already attached" → 用户侧关 F12 DevTools 或重载灵犀插件
# 3. 通信超时 → 本轮放弃该页面操作，切手动兜底：用户抄数回填（metric/ledger 命令）
# 4. 铁律：预填正文等关键内容必须本地落盘（docs/小红书发布包/），不能只存在页面里
