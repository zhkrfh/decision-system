# -*- coding: utf-8 -*-
"""audit：口径一致性审计（A4）

问题：口径从 v1.7.1 迁到 v1.8.3 后，历史稿件与草稿可能残留旧值。
已发生真实事故 —— v1.8.0 迁移后草稿箱残留旧值 52.6。

核心设计：区分「归档区」与「现行口径区」
------------------------------------------------
本项目有大量**故意保留的旧稿**（大纲明确："旧稿《连载01》由案例01取代，留档不删"）。
审计若不区分二者，会淹没在误报里，反而让人忽略真问题。

因此每条命中都带一个 disposition 判定：

  residual   现行口径区出现旧值 —— 真问题，必须处理
  archived   已知归档件中的旧值 —— 预期内，仅备案
  legitimate 文中主动声明"旧版已废弃"的对照说明 —— 合规写法

现行口径 v1.8.3：
  S = p×G − (1−p)×C        两项严格同量纲，期望分制 −10..10
  R×L                       提示项，不进总分；R×L < 10 触发警戒线
  p 打完分除以 1.2

检查项：
  1. 旧公式残留  +0.3×R×L / 三项混量纲
  2. 旧值残留    52.6 / 45.3 / 27.4 / −0.8 等
  3. 旧刻度残留  0..10 / 10..20 / S>20 分档（应为 −10..10）
  4. 版本冲突    同一案例在不同文档取值不同
  5. 编号一致性  案例编号与 content_index.csv 是否对得上

设计纪律：只读工具，不修改任何被检查文件；纯标准库；跑完即退。
用法：
  python tools/audit.py                # 全库审计
  python tools/audit.py --json         # 机器可读
  python tools/audit.py --only residual # 只看真问题
"""
import re
import csv
import sys
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
DATA = ROOT / "data"
CONTENT_INDEX = DATA / "content_index.csv"

CURRENT_CALIBER = "v1.8.3"

# ── 已知归档件（大纲明确「留档不删」） ────────────────────
# 这些文件里的旧值是历史留痕，不是残留。命中只备案不报警。
ARCHIVED_FILES = {
    "连载01_职业凯利公式.md",       # 大纲：由案例01取代，留档不删
    "版本演进_权重侧重分析.md",     # 版本演进分析，以旧结构为分析对象
    "项目志_正典仓库编年史.md",     # 编年史，记录各版本当时的数值
}

# ── 旧值残留规则 ──────────────────────────────────────────
# (正则, 说明, 处置方式)
LEGACY_RULES = [
    (r"\+?\s*0\.3\s*[×*]\s*R\s*[×*]\s*L",
     "旧公式「+0.3×R×L」把复利项当加分项混进总分（量纲错误）", "residual"),
    (r"\b52\.6\b",
     "旧值 52.6（v1.7.1 三项混量纲输出，已由 1.12 取代）", "residual"),
    (r"\b45\.3\b",
     "旧值 45.3（v1.8.0 前 p×G 口径，已由 4.54 取代）", "residual"),
    (r"\b27\.4\b",
     "旧值 27.4（案例02 旧版输出，已由 −1.97 取代）", "residual"),
    (r"\b−0\.8\b|\b-0\.8\b",
     "旧值 −0.8（案例04 旧版输出，已由 −6.44 取代）", "residual"),
    (r"S\s*>\s*20",
     "旧刻度「S>20 重仓」（现行刻度为 −10..10）", "residual"),
    (r"0\s*<\s*S\s*≤\s*10",
     "旧刻度「0<S≤10 轻仓」（现行刻度为 −10..10）", "residual"),
    (r"10\s*<\s*S\s*≤\s*20",
     "旧刻度「10<S≤20 正常持有」（现行刻度为 −10..10）", "residual"),
]

# 文中主动声明"旧版已废弃"的合规写法：命中即视为 legitimate。
#
# 纪律：只收「明确宣告该口径已作废」的措辞，不收「复算/旧版/口径」等泛化词 ——
# 「按旧版口径复算得 52.6」是在**陈述旧值本身**，不是宣告它已废弃，
# 若放进本表会让真实残留逃过审计（漏报比误报危险）。
LEGIT_MARKERS = [
    "已废弃", "诚实声明", "遗留债", "旧结构", "病灶",
    "修正为", "已按凯利模板", "取代", "留档不删",
    "混量纲", "已废弃——", "错了就改", "不可混算",
]

# 修复记录语义：说明该处旧值**已经被处理**，不是残留。
# 例：「✅ 连载02 "45.3"→ 4.54 | W2 发布件 | 已完成」
#     「v1.8.3 口径全文复算（重点：45.3→4.54 已修）」
#
# 判定必须严格：要求「旧值紧邻新值」（→ 或 → 号连接），或带完成态标记。
# 否则「按旧版口径复算…得 52.6」这类描述性写法会被误当成已修复而漏报 —— 
# 漏报比误报危险得多，故这里宁可多报。
RESOLVED_PATTERNS = [
    re.compile(r"✅"),                                   # 任务清单已完成
    re.compile(r"已修|已完成|已改正|已替换"),            # 明确完成态
    re.compile(r"\d+(?:\.\d+)?\s*[→>➔]\s*\d+(?:\.\d+)?"),  # 旧值→新值
    re.compile(r"(?:复算|核算|修订|修正)记录"),          # 复算记录表
]

# 案例编号 → 现版权威值（跨文档冲突检测基准）
CASE_CANON = {
    "案例01": {"S": 1.12, "note": "工银泰国"},
    "案例02": {"S": -1.97, "note": "996轻仓"},
    "案例03": {"S": -7.5, "note": "裸辞做IP"},
    "案例04": {"S": -6.44, "note": "清仓"},
    "案例05": {"note": "资格期断桥"},
}


class Hit:
    """一条审计命中"""

    def __init__(self, disposition, rule, path, line, text, note=""):
        self.disposition = disposition   # residual | archived | legitimate
        self.rule = rule
        self.path = path
        self.line = line
        self.text = text.strip()
        self.note = note

    def ref(self):
        try:
            rel = Path(self.path).relative_to(ROOT)
        except ValueError:
            rel = Path(self.path)
        return f"{rel}:{self.line}"

    def as_dict(self):
        return {"disposition": self.disposition, "rule": self.rule,
                "file": self.path, "line": self.line, "text": self.text,
                "note": self.note, "ref": self.ref()}


def classify(path_name, line_text):
    """判定该处旧值属于哪一类"""
    # 已知归档件 → archived
    if path_name in ARCHIVED_FILES:
        return "archived", f"已知归档件（{path_name}）"
    # 修复记录：旧值已被处理 → legitimate（优先于下面的声明判定）
    for pat in RESOLVED_PATTERNS:
        if pat.search(line_text):
            return "legitimate", f"行内匹配「{pat.pattern}」，属修复记录/任务清单，非残留"
    # 文中主动声明旧版已废弃 → legitimate
    for m in LEGIT_MARKERS:
        if m in line_text:
            return "legitimate", f"文中声明「{m}」，属合规的历史对照说明"
    return "residual", ""


def iter_docs():
    """待审计的文档：docs 下的 md（含子目录）"""
    out = []
    for f in sorted(DOCS.rglob("*.md")):
        out.append(f)
    return out


def audit_legacy():
    """检查项 1-3：旧公式 / 旧值 / 旧刻度残留"""
    hits = []
    for f in iter_docs():
        try:
            lines = f.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            continue
        for i, raw in enumerate(lines, 1):
            for pattern, desc, _ in LEGACY_RULES:
                if re.search(pattern, raw):
                    disp, why = classify(f.name, raw)
                    hits.append(Hit(disp, desc, str(f), i, raw, why))
    return hits


def audit_case_values():
    """检查项 4：同一案例在不同文档取值是否一致。

    扫描形如「案例01 ... S=1.12」或标题含案例号且同段出现 S 值的写法，
    汇总后与 CASE_CANON 比对。
    """
    hits = []
    # 匹配：案例NN ... S=<数字>（允许 ≈、=、空格）
    pat = re.compile(rf"(案例0[1-5])[^\n]{{0,40}}?S\s*[=≈]\s*(\d+(?:\.\d+)?)")
    seen = {}
    for f in iter_docs():
        if f.name in ARCHIVED_FILES:
            continue
        try:
            text = f.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for lineno, line in enumerate(text.splitlines(), 1):
            for m in pat.finditer(line):
                case, val = m.group(1), float(m.group(2))
                seen.setdefault(case, []).append((val, str(f), lineno))

    for case, entries in seen.items():
        canon = CASE_CANON.get(case, {}).get("S")
        if canon is None:
            continue
        for val, path, lineno in entries:
            if abs(val - canon) > 0.02:
                hits.append(Hit(
                    "residual",
                    f"{case} 取值冲突：文中 S={val}，现行口径 S={canon}",
                    path, lineno, f"{case} S={val}",
                    "口径不一致，需统一到现行值",
                ))
    return hits


def audit_index():
    """检查项 5：案例编号与 content_index.csv 一致性。

    校验：索引里出现的案例/连载文件是否真实存在；
          docs 下的案例文件是否都已进索引。
    """
    hits = []
    if not CONTENT_INDEX.exists():
        hits.append(Hit("residual", "content_index.csv 不存在",
                        str(CONTENT_INDEX), 0, "", "索引缺失，无法校验编号一致性"))
        return hits

    rows = []
    with open(CONTENT_INDEX, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            rows.append(r)
    if not rows:
        return hits

    indexed = set()
    for r in rows:
        item = (r.get("item") or "").strip()
        if not item:
            continue
        indexed.add(item)
        stem = item.split("_")[0]
        # 索引项应能在 docs 找到对应 md
        found = any(item in f.name or f.stem == item for f in iter_docs())
        if not found:
            hits.append(Hit(
                "residual", f"索引项「{item}」在 docs 下找不到对应文档",
                str(CONTENT_INDEX), 0, item,
                "索引与文档不一致：要么补文档，要么清理索引",
            ))

    # 反向：docs 下的案例文件是否进索引
    for f in iter_docs():
        m = re.match(r"(案例0[1-5])", f.stem)
        if not m:
            continue
        if not any(f.stem in i or i.startswith(m.group(1)) for i in indexed):
            hits.append(Hit(
                "residual", f"案例 {m.group(1)} 未登记进 content_index.csv",
                str(f), 1, f.stem, "文档存在但索引缺失，状态机无法跟踪",
            ))
    return hits


def run():
    hits = audit_legacy() + audit_case_values() + audit_index()
    return hits


def report(hits, as_json=False, only_residual=False):
    if as_json:
        print(json.dumps({
            "caliber": CURRENT_CALIBER,
            "total": len(hits),
            "by_disposition": {
                d: sum(1 for h in hits if h.disposition == d)
                for d in ("residual", "archived", "legitimate")
            },
            "hits": [h.as_dict() for h in hits],
        }, ensure_ascii=False, indent=2))
        return 1 if any(h.disposition == "residual" for h in hits) else 0

    residual = [h for h in hits if h.disposition == "residual"]
    archived = [h for h in hits if h.disposition == "archived"]
    legit = [h for h in hits if h.disposition == "legitimate"]

    print("\n" + "=" * 68)
    print(f" 口径一致性审计（A4）· 现行口径 {CURRENT_CALIBER}")
    print("=" * 68)

    if residual:
        print(f"\n[真问题 · 现行口径区残留 · {len(residual)} 项]  ← 发布前须处理")
        for h in residual:
            print(f"  ✗ {h.ref()}")
            print(f"      {h.rule}")
            print(f"      原文   {h.text[:60]}")
            if h.note:
                print(f"      说明   {h.note}")
            print()
    else:
        print("\n[真问题] 无 —— 现行口径区未发现旧值残留")

    if not only_residual:
        if legit:
            print(f"\n[合规对照 · {len(legit)} 项]  文中主动声明旧版已废弃，无需处理")
            for h in legit[:8]:
                print(f"  · {h.ref():<40} {h.rule[:44]}")
            if len(legit) > 8:
                print(f"    …… 另有 {len(legit) - 8} 项同类")

        if archived:
            print(f"\n[归档留痕 · {len(archived)} 项]  已知旧稿留档，不删不改")
            for h in archived[:8]:
                print(f"  · {h.ref():<40} {h.rule[:44]}")
            if len(archived) > 8:
                print(f"    …… 另有 {len(archived) - 8} 项同类")

    print("-" * 68)
    print(f" 合计 {len(hits)} 处命中：真问题 {len(residual)} / 合规对照 {len(legit)} / 归档留痕 {len(archived)}")
    if residual:
        print(f" → {len(residual)} 处真问题需处理")
    else:
        print(" → 现行口径区干净")
    print()
    return 1 if residual else 0


def main():
    argv = sys.argv[1:]
    as_json = "--json" in argv
    only_res = "--only" in argv and "residual" in argv[argv.index("--only") + 1:]

    hits = run()
    if not hits:
        print("\n未发现任何口径问题\n")
        sys.exit(0)
    sys.exit(report(hits, as_json, only_res))


if __name__ == "__main__":
    main()