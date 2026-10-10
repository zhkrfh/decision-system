# -*- coding: utf-8 -*-
"""due：预测到期提醒 + 自动进 EVOS 捕获队列（E5 · 需求4）

背景
----
战绩板规则：预测在发布时写死，到期必须登记结果，不允许「基本命中」。
但「到期」本身没人盯着 —— 到期后没人登记，等于没预测。

本工具做两件事
--------------
1. scan   读战绩板，列出待验证预测及剩余天数（含临期预警）
2. capture 把**已到期但未登记结果**的预测，自动写进 EVOS 捕获队列
          （type=prediction_fail，severity=high），走完整四环：
          捕获 → 提炼 → 晋升 → 回验

关键设计：幂等
--------------
同一条预测不会重复捕获。用 (案例号+截止日) 作为幂等键，
已有对应条目则只更新 last_seen 并累加 observed_count。
否则每天跑一次就会在 EVOS 库里堆出 N 条重复记录，把经验库撑爆。

口径纪律：EVOS 只优化执行层。本工具只做「到期未登记」这一事实的捕获，
不推断预测是否命中 —— 判定留给作者，走 distill 环节。

用法：
  python tools/due.py scan              # 列出到期情况
  python tools/due.py scan --warn 7     # 7 天内到期也算预警
  python tools/due.py capture           # 到期未登记 → 进 EVOS
  python tools/due.py capture --dry     # 只看会捕获什么，不写入
"""
import sys
import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import evos_core as E  # noqa: E402

# 临期预警天数：距截止 N 天内开始提醒
DEFAULT_WARN = 7

# 幂等键前缀，避免与其它捕获源混淆
KEY_PREFIX = "预测到期未登记"


def idem_key(item):
    """幂等键：案例号 + 截止日

    同一条预测在不同日期扫描必须映射到同一把钥匙，
    否则会重复捕获。
    """
    return f"{KEY_PREFIX}#{item['no']}@{item['deadline']}"


def is_registered(zhanji_path=None):
    """检查是否已有对应捕获条目（幂等判定）"""
    key = idem_key
    out = {}
    for it in E.load_all():
        if it.get("type") == "prediction_fail":
            ctx = it.get("context", "")
            if ctx.startswith(KEY_PREFIX):
                out[ctx] = it
    return out


def cmd_scan(warn_days=DEFAULT_WARN):
    """列出待验证预测及状态"""
    due = E.scan_due_predictions()
    print("\n=== 预测到期扫描 ===\n")
    if not due:
        print(" 战绩板无待验证条目")
        return []

    today = datetime.date.today()
    exist = is_registered()
    print(f" 今天 {today}　临期预警线 {warn_days} 天\n")

    for d in due:
        key = idem_key(d)
        if d["days_left"] < 0:
            state, mark = "已逾期", "!!"
        elif d["days_left"] == 0:
            state, mark = "今天到期", "!!"
        elif d["days_left"] <= warn_days:
            state, mark = "临期", " !"
        else:
            state, mark = "未到期", "  "

        flag = ""
        if key in exist:
            it = exist[key]
            flag = f"　[已捕获 {it['id']} · 观察 {it.get('observed_count', 1)} 次]"

        print(f" {mark} #{d['no']} {state}　剩 {d['days_left']} 天"
              f"　截止 {d['deadline']}{flag}")
        print(f"      {d['case'][:60]}")

    # 到期未登记的（可捕获）
    actionable = [d for d in due
                  if d["days_left"] <= 0 and idem_key(d) not in exist]
    if actionable:
        print(f"\n → {len(actionable)} 条已到期未登记，执行 "
              f"`python tools/due.py capture` 进入 EVOS 捕获队列")
    print()
    return due


def cmd_capture(dry=False):
    """已到期未登记 → EVOS 捕获队列（幂等）"""
    due = E.scan_due_predictions()
    if not due:
        print("\n 战绩板无待验证条目，无需捕获\n")
        return 0

    exist = is_registered()
    today = datetime.date.today()

    new_items, refreshed = [], []

    for d in due:
        key = idem_key(d)
        overdue = d["days_left"] <= 0

        if key in exist:
            # 幂等命中：已捕获过，只刷新观察计数
            it = exist[key]
            if overdue and it.get("observed_count", 1) < 99:
                refreshed.append(it)
            continue

        if not overdue:
            continue

        # 真正需要捕获
        detail = (
            f"战绩板 #{d['no']}《{d['case'][:40]}》\n"
            f"  起算日   {d['start']}\n"
            f"  验证截止 {d['deadline']}（已逾期 {abs(d['days_left'])} 天，今天 {today}）\n"
            f"  预测内容见战绩板，发布时锁定，事后不得改口径。\n"
            f"  待办：登记结果（命中 / 未命中 / 无法判定），写入对应案例复盘段。\n"
            f"  纪律：不登记等于没预测；未命中不删记录，写明原因。"
        )
        if dry:
            new_items.append({"context": key, "detail": detail, "dry": True})
        else:
            it = E.capture("prediction_fail", key, detail,
                           scope="project", category="theory_adjacent")
            new_items.append(it)

    # ── 输出 ──
    print("\n=== 到期捕获（EVOS 环1 · 捕获）===\n")

    if new_items:
        label = "将会捕获" if dry else "已捕获"
        print(f"[{label}] {len(new_items)} 条新预测")
        for it in new_items:
            print(f"  + {it['context']}")
            for line in it["detail"].splitlines()[:5]:
                print(f"      {line}")
            if not dry:
                print(f"      → id {it['id']}　状态 observing　severity {it['severity']}")
        if not dry:
            print(f"\n  下一步（环2 提炼）—— 需你判断后手动执行，自动流程不得代劳：")
            print(f"    python tools/evos.py distill <ID> \"<根因>\" \"<规则候选>\"")
            print(f"  纪律：EVOS 不推断预测是否命中，判定权在作者。")

    if refreshed:
        print(f"\n[幂等跳过] {len(refreshed)} 条此前已捕获，不重复入库")
        for it in refreshed:
            print(f"  = {it['context']}　({it['id']})")

    if not new_items and not refreshed:
        print(" 无到期未登记的预测")

    if dry and new_items:
        print(f"\n （--dry 模式，未写入 EVOS）")

    print()
    return 0


def main():
    argv = sys.argv[1:]
    cmd = argv[0] if argv else "scan"

    if cmd == "scan":
        warn = DEFAULT_WARN
        if "--warn" in argv:
            i = argv.index("--warn")
            if i + 1 < len(argv):
                warn = int(argv[i + 1])
        cmd_scan(warn)
    elif cmd == "capture":
        cmd_capture(dry="--dry" in argv)
    else:
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()