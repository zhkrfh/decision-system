# -*- coding: utf-8 -*-
"""content：内容中心——单一事实源的状态机与排期队列。
状态机：draft→final→scheduled→publishing→published→measured；失败停在原地等人，不静默重试。"""
import csv, datetime
from pathlib import Path
from store import DATA, ledger_rows

CIDX = DATA / "content_index.csv"
QUEUE = DATA / "queue.csv"
C_HEADERS = ["item", "topic", "status", "note"]
Q_HEADERS = ["date", "platform", "item", "note"]
STATES = ["draft", "final", "scheduled", "publishing", "published", "measured"]

def _rows(path, headers):
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))

def _save(path, headers, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=headers)
        w.writeheader(); w.writerows(rows)

def status_cmd(args):
    """status list / status <稿名> <新状态> [备注] / status <稿名>（查看）"""
    if not args or args[0] == "list":
        rows = _rows(CIDX, C_HEADERS)
        print(f"== 内容索引（{len(rows)} 条）==")
        for r in rows:
            mark = "←" if r["status"] not in ("published", "measured") else " "
            print(f"  {mark} [{r['status']:>10}] {r['item']}  {r['topic']} {r['note']}")
        return
    item, new = args[0], args[1] if len(args) > 1 else None
    rows = _rows(CIDX, C_HEADERS)
    hit = next((r for r in rows if r["item"] == item), None)
    if new is None:
        print(f"[{item}] {hit['status'] if hit else '未登记'}"); return
    if not hit:
        rows.append({"item": item, "topic": args[2] if len(args) > 2 else "",
                     "status": new, "note": args[3] if len(args) > 3 else ""})
        _save(CIDX, C_HEADERS, rows)
        print(f"[content] 新登记 {item} = {new}"); return
    cur = STATES.index(hit["status"]) if hit["status"] in STATES else -1
    tgt = STATES.index(new) if new in STATES else None
    if tgt is None: raise SystemExit(f"未知状态 {new}（合法：{'/'.join(STATES)}）")
    if tgt < cur: raise SystemExit(f"状态不可回退：{hit['status']} → {new}（异常回退请人工处理数据后重建条目）")
    hit["status"] = new
    if len(args) > 3: hit["note"] = args[3]
    _save(CIDX, C_HEADERS, rows)
    print(f"[content] {item}: {STATES[cur]} → {new}" if cur >= 0 else f"[content] {item} = {new}")

def queue_cmd(args):
    """queue add <YYYY-MM-DD|today> <平台> <稿名> [备注] / queue due [日期] / queue list"""
    sub = args[0] if args else "due"
    if sub == "add":
        d = datetime.date.today().isoformat() if args[1] == "today" else args[1]
        rows = _rows(QUEUE, Q_HEADERS)
        rows.append({"date": d, "platform": args[2], "item": args[3],
                     "note": args[4] if len(args) > 4 else ""})
        _save(QUEUE, Q_HEADERS, rows)
        print(f"[queue] {args[3]} → {args[2]} {d}")
        status_cmd([args[3], "scheduled"])
        return
    if sub == "list":
        rows = _rows(QUEUE, Q_HEADERS)
        print(f"== 排期队列（{len(rows)} 条）==")
        for r in rows: print(f"  {r['date']} [{r['platform']}] {r['item']} {r['note']}")
        return
    # due
    d = datetime.date.today().isoformat() if len(args) < 2 else args[1]
    rows = [r for r in _rows(QUEUE, Q_HEADERS) if r["date"] <= d]
    print(f"== 应发布（<= {d}，共 {len(rows)} 条）==")
    led = {r["item"]: r["status"] for r in ledger_rows()}
    for r in rows:
        st = led.get(r["item"], "未开始")
        warn = "" if st in ("published", "measured") else "  ← 待执行: prep " + r["platform"]
        print(f"  {r['date']} [{r['platform']}] {r['item']} ({st}){warn}")
