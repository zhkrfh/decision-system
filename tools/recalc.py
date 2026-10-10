# -*- coding: utf-8 -*-
"""recalc：算术复算自动化（A3 · 最高价值）

问题：每篇发布前手工复算，是流程中最易出错的环节。
已发生真实事故 —— v1.8.0 口径迁移后，草稿箱残留旧值 52.6。

做法：解析文中的算式，**独立复算并与文中声明值比对**，不一致则报警并定位到行。

支持的算式形态
--------------
1. 完整链：  S = 0.408×7.5 − 0.592×8.5 = 3.06 − 5.03 = −1.97
2. 提示项：  R×L = 5.1×7 = 35.7   /  R×L = 3×2 = 6
3. 警戒线：  R×L < 10  /  3×3=9 低于 10
4. E 模型：  E = q×M − (1−q)×W
5. 反推 p：  给定 S、G、C 反解 p = (S + C) / (G + C)

设计纪律
--------
- 纯标准库，不引第三方依赖（requests 之外一律不用）
- 跑完即退，峰值内存 < 20MB
- 判定失败要说清原因，不静默通过
- 只读工具：不修改任何被检查的文件

用法
----
  python tools/recalc.py                     # 复算全库
  python tools/recalc.py <文件路径>          # 复算单文件
  python tools/recalc.py --json              # 机器可读输出
  python tools/recalc.py --solve 1.12 8 7.9  # 反推 p
"""
import re
import sys
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"

# 判定容差：文中数值保留 1-2 位小数，复算允许舍入误差
TOL_ABS = 0.011
TOL_REL = 0.005

# 警戒线（体系铁律，任何文档不得改）
WARN_LINE = 10.0

# 全角/中文符号 → 可解析形式
NORM = {
    "×": "*", "÷": "/", "−": "-", "–": "-", "—": "-",
    "（": "(", "）": ")", "，": ",", "　": " ", "−": "-",
}


def normalize(s):
    for a, b in NORM.items():
        s = s.replace(a, b)
    return s


def close(a, b):
    """是否在容差内相等"""
    return abs(a - b) <= max(TOL_ABS, abs(b) * TOL_REL)


def strip_md(s):
    """去掉 markdown 强调与代码标记，保留数值与运算符"""
    s = re.sub(r"\*\*(.+?)\*\*", r"\1", s)
    s = re.sub(r"`(.+?)`", r"\1", s)
    s = re.sub(r"\*(\S[^*]*?)\*", r"\1", s)
    s = re.sub(r"\[(.+?)\]\(.*?\)", r"\1", s)   # 链接只留文字
    return s


NUM = r"[-+]?\d+(?:\.\d+)?"


# ── 算式提取 ──────────────────────────────────────────────
# 形如  A = B = C  的链，且 A/B/C 是纯算式（只含数字与 + - * / ( )）
CHAIN_RE = re.compile(
    rf"(?:^|[^\w])((?:\(?\s*{NUM}\s*\)?\s*[-+*/]\s*|\(\s*1\s*[-+]\s*{NUM}\s*\)\s*[-+*/\s])*)"
)


def _is_expr(tok):
    """判断 token 是否为纯算式"""
    t = tok.strip()
    if not t:
        return False
    if not re.fullmatch(r"[\d\s.+\-*/()]+", t):
        return False
    if not re.search(r"\d", t):
        return False
    # 必须含运算符，否则只是一个裸数字（裸数字由另一路处理）
    return bool(re.search(r"[-+*/]", t))


def _safe_eval(tok):
    """只允许数字与四则运算的表达式求值 —— 禁用 eval 的任意代码路径"""
    if not _is_expr(tok):
        return None
    t = tok.strip().replace("--", "- -")
    if not re.fullmatch(r"[\d\s.+\-*/()]+", t):
        return None
    try:
        # 白名单字符集已由上面的正则保证；长度上限防畸形输入
        if len(t) > 120:
            return None
        return eval(t, {"__builtins__": {}}, {})  # noqa: S307 - 字符集已白名单化
    except (SyntaxError, ZeroDivisionError, TypeError, NameError):
        return None


def _fmt(v):
    """格式化，抑制浮点尾噪"""
    if v == int(v) and abs(v) < 1e15:
        return str(int(v))
    return f"{v:.4f}".rstrip("0").rstrip(".")


# ── 复算核 ────────────────────────────────────────────────
class Finding:
    """一条复算结果"""

    def __init__(self, kind, expr, stated, computed, path, line, ok, note=""):
        self.kind = kind
        self.expr = expr
        self.stated = stated
        self.computed = computed
        self.path = path
        self.line = line
        self.ok = ok
        self.note = note

    def as_dict(self):
        return {"kind": self.kind, "expr": self.expr, "stated": self.stated,
                "computed": self.computed, "file": self.path, "line": self.line,
                "ok": self.ok, "note": self.note}

    def line_ref(self):
        try:
            rel = Path(self.path).relative_to(ROOT)
        except ValueError:
            rel = Path(self.path)
        return f"{rel}:{self.line}"


def check_chain(expr_text, path, lineno):
    """复算 `A = B = C` 型算式链，逐段比对。

    例：S = 0.408×7.5 − 0.592×8.5 = 3.06 − 5.03 = −1.97
    例（跨行合并后）：= 0.567×8 − 0.433×7.9 = 4.54 − 3.42 = 1.12

    比对逻辑：
      1. 以等号切分整条链的所有段
      2. 取第一个含运算符且可算的段作基准值
      3. 取最后一个可算段作文中声明值
      4. 比对基准与声明；中间可算段再做交叉验证
    """
    out = []
    text = normalize(strip_md(expr_text))
    if "=" not in text:
        return out

    # 取左侧标识符（仅用于展示），无则记为链式演算
    m_head = re.search(r"\b([A-Z](?:×[A-Z])?)\s*=\s*", text)
    lhs = m_head.group(1) if m_head else "链"

    parts = [p.strip() for p in text.split("=")]
    if len(parts) < 2:
        return out

    # 末段通常是声明值（可能被中文括号或后注包裹）
    stated, stated_idx = None, None
    for i in range(len(parts) - 1, -1, -1):
        v = _safe_eval(parts[i])
        if v is not None:
            stated, stated_idx = v, i
            break
    if stated is None:
        return out

    # 基准表达式 = 第一个含运算符且可完整计算的段
    base = None
    for p in parts:
        if re.search(r"[-+*/]", p):
            v = _safe_eval(p)
            if v is not None:
                base = (p, v)
                break
    if base is None:
        return out

    base_expr, base_val = base
    ok = close(base_val, stated)
    out.append(Finding(
        kind="chain", expr=f"{lhs} = {base_expr}", stated=_fmt(stated),
        computed=_fmt(base_val), path=path, line=lineno, ok=ok,
        note="" if ok else f"文中声明 {_fmt(stated)}，独立复算得 {_fmt(base_val)}",
    ))

    # 交叉验证：中间段若也能独立算出，同样应等于基准值
    for p in parts[1:stated_idx]:
        if not re.search(r"[-+*/]", p):
            continue
        v = _safe_eval(p)
        if v is None:
            continue
        cross_ok = close(v, base_val)
        out.append(Finding(
            kind="chain_step", expr=p.strip(), stated=_fmt(base_val),
            computed=_fmt(v), path=path, line=lineno, ok=cross_ok,
            note="" if cross_ok else f"中间段「{p.strip()}」算得 {_fmt(v)}，与全式 {_fmt(base_val)} 不符",
        ))
    return out

    # 末段通常是声明值（可能被括号或中文标点包裹）
    stated = None
    for i in range(len(parts) - 1, -1, -1):
        v = _safe_eval(parts[i])
        if v is not None:
            # 若末段之后还有非算式文字（如"（v1.8.0 重算：旧版 −0.8 ...）"），忽略
            stated = v
            parts = parts[: i + 1]
            break
    if stated is None or len(parts) < 2:
        return out

    # 基准表达式 = 第一个可完整计算的段
    base = None
    for p in parts:
        if _is_expr(p) and re.search(r"[-+*/]", p):
            v = _safe_eval(p)
            if v is not None:
                base = (p, v)
                break
    if base is None:
        return out

    base_expr, base_val = base
    ok = close(base_val, stated)
    out.append(Finding(
        kind="chain", expr=f"{lhs} = {base_expr}", stated=_fmt(stated),
        computed=_fmt(base_val), path=path, line=lineno, ok=ok,
        note="" if ok else f"文中声明 {_fmt(stated)}，独立复算得 {_fmt(base_val)}",
    ))

    # 交叉验证：若中间段也能独立算出，同样应等于基准值
    for p in parts[1:-1] if len(parts) > 2 else []:
        v = _safe_eval(p)
        if v is None:
            continue
        cross_ok = close(v, base_val)
        out.append(Finding(
            kind="chain_step", expr=p.strip(), stated=_fmt(base_val),
            computed=_fmt(v), path=path, line=lineno, ok=cross_ok,
            note="" if cross_ok else f"中间段「{p.strip()}」算得 {_fmt(v)}，与全式 {_fmt(base_val)} 不符",
        ))
    return out


def check_product(text, path, lineno):
    """复算乘积型：R×L = 5.1×7 = 35.7 / 3×3=9

    注意：normalize 已把 × 转成 *，正则须按 * 匹配（原文里的 × 是全角乘号）。
    整行含 ≥2 个等号时视为算式链，其子乘积交由 check_chain 交叉验证，
    此处跳过以免把同行前半段的数字错配进来。
    """
    out = []
    s = normalize(strip_md(text))
    if s.count("=") >= 2:
        return out
    # 标识符型：R*L = a*b = v
    for m in re.finditer(rf"([A-Z])\s*\*\s*([A-Z])\s*=\s*({NUM})\s*\*\s*({NUM})\s*=\s*({NUM})", s):
        lhs, rhs, a, b, stated = m.groups()
        a, b, stated = float(a), float(b), float(stated)
        computed = a * b
        ok = close(computed, stated)
        out.append(Finding(
            kind="product", expr=f"{lhs}×{rhs} = {m.group(3)}×{m.group(4)}",
            stated=_fmt(stated), computed=_fmt(computed), path=path, line=lineno, ok=ok,
            note="" if ok else f"{lhs}×{rhs} 复算得 {_fmt(computed)}，文中写 {_fmt(stated)}",
        ))
    # 裸写法：3*3 = 9
    # 约束左边界为「非数字且非小数点」，保证只匹配独立的乘积项，
    # 不会把算式链中间的 `0.592*8.5 = 5.03` 与同行前半段的数字错配。
    for m in re.finditer(rf"(?<![\d.])({NUM})\s*\*\s*(\d+(?:\.\d+)?)\s*=\s*({NUM})(?![\d.])", s):
        a, b, stated = float(m.group(1)), float(m.group(2)), float(m.group(3))
        computed = a * b
        ok = close(computed, stated)
        out.append(Finding(
            kind="product", expr=f"{m.group(1)}×{m.group(2)}",
            stated=_fmt(stated), computed=_fmt(computed), path=path, line=lineno, ok=ok,
            note="" if ok else f"复算得 {_fmt(computed)}，文中写 {_fmt(stated)}",
        ))
    return out


def check_warnline(text, path, lineno):
    """校验 R×L 与 10 警戒线的判定是否自洽。

    文中若写「R×L = 6 < 10：双重确认」，则算得值必须确实 < 10。
    若写「35.7，远在警戒线之上」，则算得值必须 >= 10。
    """
    out = []
    s = normalize(strip_md(text))
    for m in re.finditer(rf"([A-Z])\s*\*\s*([A-Z])\s*=\s*({NUM})\s*(<|>|≥|≤)\s*({NUM}(?:\.\d+)?)", s):
        lhs, rhs, val, op, bound = m.groups()
        val, bound = float(val), float(bound)
        if op == "<":
            ok = val < bound
            expect = f"< {bound}"
        elif op in (">", "≥"):
            ok = val > bound
            expect = f"> {bound}"
        else:
            ok = val <= bound
            expect = f"≤ {bound}"
        out.append(Finding(
            kind="warnline", expr=f"{lhs}×{rhs} = {val} {op} {bound}",
            stated=expect, computed=_fmt(val), path=path, line=lineno, ok=ok,
            note="" if ok else f"文中判定 {expect}，但算得 {_fmt(val)}",
        ))

    # 「35.7，远在警戒线之上」这类自然语言判定
    for m in re.finditer(rf"({NUM}(?:\.\d+)?)\s*[，,]\s*远在警戒线之上", s):
        val = float(m.group(1))
        ok = val >= WARN_LINE
        out.append(Finding(
            kind="warnline", expr=f"{m.group(1)} 远在警戒线之上",
            stated=f"≥ {WARN_LINE}", computed=_fmt(val), path=path, line=lineno, ok=ok,
            note="" if ok else f"文中称高于警戒线，但 {_fmt(val)} < {WARN_LINE}",
        ))
    return out


def scan_file(path):
    """复算单个文件的所有算式。

    跨行链合并：连续以 `=` 开头的行属于同一条演算链
    （案例01 写作 `= 0.567×8 − 0.433×7.9` / `= 4.54 − 3.42` / `= 1.12` 三行），
    必须拼成一条再复算，否则会漏检。
    """
    p = Path(path)
    if not p.exists():
        print(f"文件不存在: {path}", file=sys.stderr)
        return []
    findings = []
    lines = p.read_text(encoding="utf-8").splitlines()

    buf, buf_start = [], None
    in_fence = False

    def flush():
        nonlocal buf, buf_start
        if buf:
            findings.extend(check_chain(" ".join(buf), str(p), buf_start))
            buf, buf_start = [], None

    for i, raw in enumerate(lines, 1):
        line = raw.strip()
        if line.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if not line:
            flush()
            continue
        # 续行：以 = 开头，或以 `= ` 形式的演算步骤
        if line.startswith("="):
            if buf_start is None:
                buf_start = i
            buf.append(line)
            continue
        flush()
        findings += check_chain(line, str(p), i)
        findings += check_product(line, str(p), i)
        findings += check_warnline(line, str(p), i)
    flush()
    return findings


def iter_docs():
    """待复算的文档集合：连载 + 案例"""
    files = []
    for sub in ("连载", ""):
        d = DOCS / sub if sub else DOCS
        if not d.exists():
            continue
        for f in sorted(d.glob("*.md")):
            if sub == "" and ("连载" in f.name or "案例" not in f.name):
                continue
            files.append(f)
    seen, out = set(), []
    for f in files:
        rp = f.resolve()
        if rp not in seen:
            seen.add(rp)
            out.append(f)
    return out


# ── 反推 p ────────────────────────────────────────────────
def solve_p(S, G, C):
    """由 S = p×G − (1−p)×C 反解 p

    S = pG − C + pC = p(G + C) − C
    ⇒ p = (S + C) / (G + C)

    例：S=1.12, G=8, C=7.9 ⇒ p = 9.02 / 15.9 = 0.5673
    """
    denom = G + C
    if abs(denom) < 1e-12:
        return None
    return (S + C) / denom


def cmd_solve(argv):
    """反推 p：python tools/recalc.py --solve <S> <G> <C>"""
    if len(argv) < 3:
        print("用法: python tools/recalc.py --solve <S> <G> <C>")
        print("  例: --solve 1.12 8 7.9   →  p = 0.5673")
        return 1
    try:
        S, G, C = (float(x) for x in argv[:3])
    except ValueError as e:
        print(f"参数必须是数字: {e}", file=sys.stderr)
        return 1
    p = solve_p(S, G, C)
    if p is None:
        print(f"无法反推：G + C = 0（分母为零）")
        return 1
    print(f"\n反推 p")
    print(f"  已知  S = {_fmt(S)}, G = {_fmt(G)}, C = {_fmt(C)}")
    print(f"  公式  S = p×G − (1−p)×C")
    print(f"  解得  p = (S + C) / (G + C) = ({_fmt(S)} + {_fmt(C)}) / ({_fmt(G)} + {_fmt(C)})")
    print(f"        = {_fmt(S + C)} / {_fmt(denom if (denom := G + C) else 0)}")
    print(f"        = {p:.4f}")
    # 验算
    back = p * G - (1 - p) * C
    print(f"  验算  {p:.4f}×{_fmt(G)} − {1 - p:.4f}×{_fmt(C)} = {back:.4f}"
          f"  {'✓ 与给定 S 一致' if close(back, S) else '✗ 与给定 S 不符'}")
    print(f"\n  对应打分 p_raw = {p * 10:.3f} 分（除以 1.2 前的原始分 ≈ {p * 10 * 1.2:.2f}）\n")
    return 0


# ── 主流程 ────────────────────────────────────────────────
def run(targets=None):
    files = [Path(t) for t in targets] if targets else iter_docs()
    all_findings = []
    for f in files:
        all_findings += scan_file(f)

    ok = [x for x in all_findings if x.ok]
    bad = [x for x in all_findings if not x.ok]
    return all_findings, ok, bad


def report(all_f, ok, bad, as_json=False):
    if as_json:
        print(json.dumps({
            "total": len(all_f), "passed": len(ok), "failed": len(bad),
            "findings": [x.as_dict() for x in all_f],
        }, ensure_ascii=False, indent=2))
        return 1 if bad else 0

    print("\n" + "=" * 66)
    print(" 算术复算校验（A3）")
    print("=" * 66)

    # 按文件分组展示通过的项
    by_file = {}
    for x in ok:
        by_file.setdefault(x.line_ref(), []).append(x)

    if by_file:
        print("\n[复算通过]")
        for ref in sorted(by_file):
            for x in by_file[ref]:
                print(f"  ✓ {ref:<46} {x.expr[:34]:<34} = {x.stated}")

    if bad:
        print(f"\n[复算不符 · {len(bad)} 项]")
        for x in bad:
            print(f"  ✗ {x.line_ref()}")
            print(f"      算式   {x.expr}")
            print(f"      文中   {x.stated}")
            print(f"      复算   {x.computed}")
            if x.note:
                print(f"      原因   {x.note}")
            print()

    print("-" * 66)
    print(f" 共复算 {len(all_f)} 处：通过 {len(ok)}，不符 {len(bad)}")
    if bad:
        print(f" → 存在 {len(bad)} 处不一致，发布前必须修正")
    else:
        print(" → 全部一致")
    print()

    # 附加：反推 p 自检（案例01 是验收基准）
    p = solve_p(1.12, 8, 7.9)
    print(f"[验收基准] 案例01 反推 p = {p:.4f}"
          f"（文中 0.567，{'✓ 一致' if close(p, 0.567) else '✗ 不一致'}）")
    back = 0.567 * 8 - 0.433 * 7.9
    print(f"[验收基准] 0.567×8 − 0.433×7.9 = {back:.4f} ≈ 1.12"
          f"（{'✓ 舍入内' if close(back, 1.12) else '✗ 超出容差'}）\n")
    return 1 if bad else 0


def main():
    argv = sys.argv[1:]
    if "--solve" in argv:
        i = argv.index("--solve")
        sys.exit(cmd_solve(argv[i + 1:]))
    as_json = "--json" in argv
    targets = [a for a in argv if not a.startswith("--")]
    if targets:
        missing = [t for t in targets if not Path(t).exists()]
        if missing:
            print(f"文件不存在: {', '.join(missing)}", file=sys.stderr)
            sys.exit(1)
    all_f, ok, bad = run(targets)
    if not all_f:
        print("未发现可复算的算式（检查文档是否含 S = ... 或 R×L = ... 形式）")
        sys.exit(0)
    sys.exit(report(all_f, ok, bad, as_json))


if __name__ == "__main__":
    main()