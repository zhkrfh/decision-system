# -*- coding: utf-8 -*-
"""evos：EVOS 命令行入口（捕获 / 提炼 / 晋升 / 回验 / 扫描）

用法:
  python tools/evos.py status                     # 看板
  python tools/evos.py verify                     # 周度回验报告
  python tools/evos.py scan                       # 扫描到期预测
  python tools/evos.py log <类型> <上下文> [详情]   # 环1 捕获
  python tools/evos.py distill <ID> "<根因>" "<规则候选>"   # 环2 提炼
  python tools/evos.py trial <ID>                 # 环3 观察→试行
  python tools/evos.py noted <ID> "<备注>"         # 试行/固化触发记录
  python tools/evos.py codify <ID> clean|dirty    # 环3 试行→固化
  python tools/evos.py rollback <ID> "<原因>"      # 环3 降级
  python tools/evos.py archive <ID> "<原因>"       # 环4 归档
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import evos_core as E  # noqa: E402

STATUS_LABEL = {
    "observing": "观察", "trialing": "试行", "codified": "固化",
    "rolled_back": "已回滚", "archived": "已归档", "pending_verification": "待验证",
}
SEV_MARK = {"critical": "!!", "high": "! ", "medium": "  ", "low": "  "}


def cmd_status():
    items = E.load_all()
    if not items:
        print("经验库为空")
        return
    by = {}
    for it in items:
        by.setdefault(it["status"], []).append(it)
    print(f"\nEVOS 看板 · 共 {len(items)} 条\n" + "-" * 62)
    for st in ["observing", "trialing", "codified", "rolled_back", "archived", "pending_verification"]:
        if st not in by:
            continue
        print(f"\n[{STATUS_LABEL.get(st, st)}] {len(by[st])} 条")
        for it in by[st]:
            rc = (it.get("root_cause") or "")[:34]
            m = SEV_MARK.get(it.get("severity", "low"), "  ")
            print(f"  {m}{it['id']}  x{it.get('observed_count', 1)}  {rc or '(未提炼)'}")
    eligible = E.verify()["eligible_for_trial"]
    if eligible:
        print(f"\n→ 可进入试行: {', '.join(eligible)}")
        print(f"  执行: python tools/evos.py trial {eligible[0]}")
    print()


def cmd_verify():
    r = E.verify()
    print("\n=== EVOS 周度回验 ===\n")
    print(f"检查时间   : {r['checked_at']}")
    print(f"经验总数   : {r['total']}")
    print(f"分布       : {r['by_status']}")
    print(f"近90天活跃 : {r['recent_count']} 条 (复发率 {r['recurrence_rate']}%)")
    if r["codified_count"]:
        print(f"固化规则   : {r['codified_count']} 条，有效率 {r['codified_effectiveness']}%")
    else:
        print("固化规则   : 0 条（尚未进入固化阶段）")
    print(f"净收益代理 : {r['net_value_proxy']}（试行次数 - 2x回滚）")
    print()
    if r["eligible_for_trial"]:
        print(f"可进入试行 : {', '.join(r['eligible_for_trial'])}")
    if r["suggest_rollback"]:
        print(f"建议回滚   : {', '.join(r['suggest_rollback'])}")
    if r["to_archive"]:
        print(f"建议归档   : {', '.join(r['to_archive'])}")
    print()


def cmd_scan():
    due = E.scan_due_predictions()
    print("\n=== 预测到期扫描 ===\n")
    if not due:
        print("战绩板无待验证条目")
        return
    for d in due:
        if d["due"]:
            print(f"  [已到期] #{d['no']} {d['case'][:30]} — 截止 {d['deadline']}")
        else:
            print(f"  [{d['days_left']}天]  #{d['no']} {d['case'][:30]} — 截止 {d['deadline']}")
    print()


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return
    c = sys.argv[1]
    a = sys.argv[2:]
    if c == "status":
        cmd_status()
    elif c == "verify":
        cmd_verify()
    elif c == "scan":
        cmd_scan()
    elif c == "log":
        E.capture(a[0], a[1], a[2] if len(a) > 2 else "")
        print(f"已捕获: {a[1]}")
    elif c == "distill":
        it = E.distill(a[0], a[1], a[2] if len(a) > 2 else "")
        print(f"已提炼 {it['id']}（观察次数 {it['observed_count']}）")
    elif c == "trial":
        it = E.promote_to_trial(a[0])
        print(f"{it['id']} → 试行。规则将影响行为，触发时用 noted 记录")
    elif c == "noted":
        it = E.log_trial(a[0], a[1] if len(a) > 1 else "")
        print(f"已记录触发（累计 {len(it.get('trials', []))} 次）")
    elif c == "codify":
        it = E.promote_to_codified(a[0], clean_trials=(a[1] == "clean"))
        print(f"{it['id']} → 固化")
    elif c == "rollback":
        print(f"{E.rollback(a[0], a[1] if len(a) > 1 else '')['id']} → 已回滚")
    elif c == "archive":
        print(f"{E.archive(a[0], a[1] if len(a) > 1 else '')['id']} → 已归档")
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
