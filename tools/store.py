# -*- coding: utf-8 -*-
"""store：.env 读取、发布台账/指标 CSV 读写（dispatcher 共用底层）"""
import csv, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"; DATA.mkdir(exist_ok=True)
PLOG = DATA / "publish_log.csv"
MET = DATA / "metrics.csv"
LED = DATA / "ledger.csv"

ROW_HEADERS = {PLOG: ["platform", "title", "status", "note"],
               MET: ["platform", "title", "metric", "value"],
               LED: ["item", "platform", "status", "ref", "note"]}

def env():
    out = {}
    p = ROOT / ".env"
    if not p.exists():
        return out
    for l in p.read_text(encoding="utf-8").splitlines():
        if "=" in l:
            k, v = l.strip().split("=", 1); out[k] = v
    return out

def append(path, row):
    new = not path.exists()
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new: w.writerow(["date"] + ROW_HEADERS[path])
        w.writerow([datetime.date.today().isoformat()] + row)

def ledger_rows():
    if not LED.exists():
        return []
    with open(LED, encoding="utf-8") as f:
        return list(csv.DictReader(f))

def ledger_update(item, status, ref=""):
    """更新 ledger 中指定稿名的状态（最后一条匹配行）"""
    rows = ledger_rows()
    hit = None
    for r in rows:
        if r["item"] == item: hit = r
    if not hit:
        raise SystemExit(f"ledger 无记录: {item}（先用 prep <平台> <稿名> 创建）")
    hit["status"] = status
    if ref: hit["ref"] = ref
    with open(LED, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["date"] + ROW_HEADERS[LED])
        w.writeheader(); w.writerows(rows)
    return hit
