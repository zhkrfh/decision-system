# -*- coding: utf-8 -*-
"""evos_core：EVOS 自我进化操作系统核心引擎

四环：捕获(Capture) → 提炼(Distill) → 晋升(Promote) → 回验(Verify)

设计纪律：
1. 只优化执行层。L4 理论口径不可被本模块触碰（见 FORBIDDEN_SCOPES）。
2. 晋升不自动到 codified，必须过 trialing 且显式告知。
3. 只进出会导致记忆库膨胀。archive / rollback 是维护手段，不是失败。
"""
import json
import datetime
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EVOS_DIR = ROOT / "EVOS"
SKILLS_DIR = EVOS_DIR / "skills"
LEDGER = EVOS_DIR / "experience.jsonl"
STATS = EVOS_DIR / "stats.json"

# ── 分层定义 ──────────────────────────────────────────────
LAYERS = {
    "L1": {"name": "执行记忆", "path": "EVOS/experience.jsonl", "mutable_by": "ai"},
    "L2": {"name": "技能规则", "path": "EVOS/skills/", "mutable_by": "ai_proposes_author_approves"},
    "L3": {"name": "项目规范", "path": "docs/", "mutable_by": "author"},
    "L4": {"name": "理论口径", "path": "frozen", "mutable_by": "author_only"},
}

# 禁止作用域：进化系统永远不能自动升格到这些地方
FORBIDDEN_SCOPES = {"L4", "theory", "formula", "口径"}

SEVERITY_ORDER = {"low": 0, "medium": 1, "high": 2, "critical": 3}

# 晋升门槛
PROMOTION_GATE = {
    "observing": {"next": "trialing", "min_observations": 2, "require_root_cause": True},
    "trialing": {"next": "codified", "require_clean_trial": True, "min_observations": 3},
    "codified": {"next": None},
    "rolled_back": {"next": None},
    "archived": {"next": None},
}

ROLLOFF_DAYS = 90      # 未触发且未验证有效 → 归档
ROLLBACK_THRESHOLD = 2 # 导致 >=2 次新错误 → 立即回滚


# ── 基础读写 ──────────────────────────────────────────────
_seq = 0


def _today():
    return datetime.date.today().isoformat()


def _now():
    return datetime.datetime.now().isoformat(timespec="seconds")


def load_all():
    if not LEDGER.exists():
        return []
    items = []
    for line in LEDGER.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            items.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return items


def append(item):
    EVOS_DIR.mkdir(exist_ok=True)
    with open(LEDGER, "a", encoding="utf-8") as f:
        f.write(json.dumps(item, ensure_ascii=False) + "\n")


def gen_id(kind):
    day = _today().replace("-", "")
    h = hashlib.md5(f"{kind}{_now()}{_uid()}".encode()).hexdigest()[:4].upper()
    return f"EVOS-{day}-{h}"


def _uid():
    """进程内单调序号 + 时间微秒，避免同秒碰撞"""
    global _seq
    _seq += 1
    return f"{_seq}{datetime.datetime.now().microsecond}"


def save(item):
    """覆盖写入单条（按 id 匹配）"""
    items = load_all()
    out = [i for i in items if i["id"] != item["id"]]
    out.append(item)
    with open(LEDGER, "w", encoding="utf-8") as f:
        for i in out:
            f.write(json.dumps(i, ensure_ascii=False) + "\n")


def save_stats(d):
    EVOS_DIR.mkdir(exist_ok=True)
    STATS.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")


def load_stats():
    if STATS.exists():
        return json.loads(STATS.read_text(encoding="utf-8"))
    return {"install_date": _today(), "checks": 0, "trials_logged": 0, "rollbacks": 0}


# ── 环 1 · 捕获 Capture ───────────────────────────────────
CAPTURE_SOURCES = {
    "bash_error":     {"severity": "medium", "category": "infra"},
    "user_correction":{"severity": "high",   "category": "behavior"},
    "prediction_fail":{"severity": "high",   "category": "theory_adjacent"},
    "platform_fault": {"severity": "medium", "category": "platform"},
    "flip-flop":      {"severity": "low",    "category": "infra"},
}


def capture(kind, context, detail="", scope="project", category=None):
    """环1：登记一条原始事件，状态 observing，不影响任何行为。"""
    meta = CAPTURE_SOURCES.get(kind, {"severity": "medium", "category": "general"})
    item = {
        "id": gen_id(kind),
        "type": kind,
        "severity": meta["severity"],
        "category": category or meta["category"],
        "context": context,
        "detail": detail,
        "root_cause": "",            # 环2 提炼时填写
        "rule_candidate": "",
        "evidence": [],
        "scope": scope,
        "observed_count": 1,
        "status": "observing",
        "promoted_to": None,
        "trials": [],                # 试行期记录
        "triggered_after_codify": 0, # 固化后被触发的次数
        "first_seen": _today(),
        "last_seen": _today(),
    }
    append(item)
    return item


def record_observation(context, detail=""):
    """同类事件再次发生 → observed_count+1，并刷新 last_seen。"""
    items = load_all()
    for it in reversed(items):
        if it.get("context") == context and it.get("root_cause", "") == "":
            it["observed_count"] = it.get("observed_count", 1) + 1
            it["last_seen"] = _today()
            save(it)
            return it, True
    return capture("bash_error", context, detail), False


# ── 环 2 · 提炼 Distill ───────────────────────────────────
def distill(item_id, root_cause, rule_candidate, evidence=None):
    """环2：填入根因与候选规则。根因质量决定规则质量。"""
    items = load_all()
    for it in items:
        if it["id"] == item_id:
            it["root_cause"] = root_cause
            it["rule_candidate"] = rule_candidate
            it["evidence"] = evidence or it.get("evidence", [])
            it["distilled_at"] = _now()
            save(it)
            return it
    raise SystemExit(f"未找到经验条目: {item_id}")


# ── 环 3 · 晋升 Promote ───────────────────────────────────
def eligible_for_trial(items):
    """observing → trialing 的候选：观察到 >=2 次且根因明确"""
    out = []
    for it in items:
        if it["status"] != "observing":
            continue
        if it.get("observed_count", 0) >= PROMOTION_GATE["observing"]["min_observations"] \
           and it.get("root_cause", "").strip():
            out.append(it)
    return out


def promote_to_trial(item_id):
    it = _get(item_id)
    if it["status"] != "observing":
        raise SystemExit(f"{item_id} 状态为 {it['status']}，非 observing")
    if it.get("observed_count", 0) < 2:
        raise SystemExit(f"{item_id} 观察到 {it['observed_count']} 次，未达试行门槛(需>=2)")
    if not it.get("root_cause", "").strip():
        raise SystemExit(f"{item_id} 未提炼根因，禁止进入试行")
    it["status"] = "trialing"
    it["trial_started"] = _today()
    save(it)
    _record_trial(it, "promoted")
    return it


def log_trial(item_id, note=""):
    """试行期触发时调用 —— 显式告知，不静默改变行为。"""
    it = _get(item_id)
    if it["status"] not in ("trialing", "codified"):
        raise SystemExit(f"{item_id} 不在试行/固化状态，无需记录")
    it.setdefault("trials", []).append({"date": _today(), "note": note})
    if it["status"] == "codified":
        it["triggered_after_codify"] = it.get("triggered_after_codify", 0) + 1
    save(it)
    return it


def promote_to_codified(item_id, clean_trials=None):
    """trialing → codified。需显式确认试行结果。"""
    it = _get(item_id)
    if it["status"] != "trialing":
        raise SystemExit(f"{item_id} 状态为 {it['status']}，非 trialing")
    if clean_trials is None:
        raise SystemExit("必须显式指定 clean_trials（True=试行期无复发 / False=仍有问题）")
    it["status"] = "codified"
    it["codified_at"] = _today()
    it["clean_trial"] = bool(clean_trials)
    save(it)
    _record_trial(it, "codified")
    return it


def rollback(item_id, reason):
    """固化后仍致同类错误 → 自动降级。"""
    it = _get(item_id)
    it["status"] = "rolled_back"
    it["rollback_reason"] = reason
    it["rolled_back_at"] = _today()
    save(it)
    st = load_stats()
    st["rollbacks"] = st.get("rollbacks", 0) + 1
    save_stats(st)
    return it


def archive(item_id, reason):
    it = _get(item_id)
    it["status"] = "archived"
    it["archive_reason"] = reason
    it["archived_at"] = _today()
    save(it)
    return it


def _record_trial(it, event):
    st = load_stats()
    st["trials_logged"] = st.get("trials_logged", 0) + 1
    save_stats(st)


def _get(item_id):
    for it in load_all():
        if it["id"] == item_id:
            return it
    raise SystemExit(f"未找到经验条目: {item_id}")


# ── 环 4 · 回验 Verify ────────────────────────────────────
def verify():
    """周度回验：产出三个指标 + 待归档 + 建议回滚项。"""
    items = load_all()
    today = datetime.date.today()

    by_status = {}
    for it in items:
        by_status.setdefault(it["status"], []).append(it)

    # 指标1 复发率：近90天出现的条目占比
    cutoff = today - datetime.timedelta(days=ROLLOFF_DAYS)
    recent = [i for i in items if datetime.date.fromisoformat(i["last_seen"]) >= cutoff]

    # 指标2 规则有效性：固化规则中被触发且记录为有效的比例
    codified = by_status.get("codified", [])
    valid_codified = [i for i in codified if i.get("triggered_after_codify", 0) > 0]

    # 指标3 净收益（以试行次数作代理指标；真实收益需接人工口径）
    st = load_stats()
    net = st.get("trials_logged", 0) - st.get("rollbacks", 0) * 2

    # 待归档：observing 超过90天且从未触发
    to_archive = [
        i for i in by_status.get("observing", [])
        if datetime.date.fromisoformat(i["first_seen"]) < cutoff
        and i.get("observed_count", 0) <= 1
    ]

    # 建议回滚：固化后仍记录到新错误
    to_rollback = [
        i for i in codified
        if i.get("triggered_after_codify", 0) >= ROLLBACK_THRESHOLD
        and i.get("new_errors_after_codify", 0) > 0
    ]

    report = {
        "checked_at": _now(),
        "total": len(items),
        "by_status": {k: len(v) for k, v in sorted(by_status.items())},
        "recent_count": len(recent),
        "recurrence_rate": round(len(recent) / len(items) * 100, 1) if items else 0,
        "codified_count": len(codified),
        "codified_effectiveness": round(len(valid_codified) / len(codified) * 100, 1) if codified else None,
        "net_value_proxy": net,
        "to_archive": [i["id"] for i in to_archive],
        "suggest_rollback": [i["id"] for i in to_rollback],
        "eligible_for_trial": [i["id"] for i in eligible_for_trial(items)],
    }
    return report


# ── 预测到期扫描（捕获源之一） ────────────────────────────
def scan_due_predictions(zhanji_path=None):
    """扫战绩板，输出已到验证截止日但仍为'待验证'的条目。

    表格列序：# | 案例 | 预测 | 起算日 | 验证截止 | 结果 | 备注
    """
    p = Path(zhanji_path) if zhanji_path else (ROOT / "docs" / "战绩板.md")
    if not p.exists():
        return []
    today = datetime.date.today()
    due = []
    for line in p.read_text(encoding="utf-8").splitlines():
        if "待验证" not in line or not line.strip().startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 6:
            continue
        case_no, name = cells[0], cells[1]
        start, deadline, status = cells[3], cells[4], cells[5]
        if status != "待验证":
            continue
        try:
            d = datetime.date.fromisoformat(deadline)
        except ValueError:
            continue
        days_left = (d - today).days
        due.append({"no": case_no, "case": name, "start": start,
                    "deadline": deadline, "days_left": days_left,
                    "due": days_left <= 0})
    return due


# ── 防护：确认目标不被允许自动修改 ────────────────────────
def guard_scope(target_scope):
    if target_scope in FORBIDDEN_SCOPES:
        raise SystemExit(
            f"拒绝操作：{target_scope} 属理论口径层，仅作者可修改。"
            "EVOS 只优化执行层。"
        )
    return True


def guard_auto_promote(item_id):
    """确认 codified 不能由自动流程直接达成。"""
    it = _get(item_id)
    if it["status"] == "codified" and not it.get("clean_trial"):
        raise SystemExit(f"{item_id} 未经干净试行期，禁止置为 codified")
    return True


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(0)
    cmd = sys.argv[1]
    if cmd == "verify":
        r = verify()
        print(json.dumps(r, ensure_ascii=False, indent=2))
    elif cmd == "due":
        print(json.dumps(scan_due_predictions(), ensure_ascii=False, indent=2))
    else:
        print(__doc__)
