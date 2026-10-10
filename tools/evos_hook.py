# -*- coding: utf-8 -*-
"""evos_hook：EVOS 自动捕获钩子

用途：包裹任意命令的执行，失败时自动登记到 EVOS 经验库。
不修改被包裹的命令本身。

三种用法:
  1) 命令包装（推荐）:
     python tools/evos_hook.py run -- python tools/dispatcher.py plan
  2) Shell 集成（写入 ~/.bashrc 后自动生效）:
     evos_run python tools/dispatcher.py plan
  3) 批量（对 dispatcher 所有子命令做一次巡检）:
     python tools/evos_hook.py sweep
"""
import sys
import subprocess
import datetime
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import evos_core as E  # noqa: E402

# 不值得记录的错误（噪声，捕获了也没用）
NOISE = (
    "KeyboardInterrupt",
    "BrokenPipeError",
    "Operation cancelled by user",
    "^C",
)

# 已知的、有既定解法的错误 → 直接映射到已沉淀规则，避免重复提炼
KNOWN = {
    "48001": "公众号未认证，stats 接口不可用",
    "40007": "AppID 与 AppSecret 不匹配",
    "40164": "IP 不在白名单",
    "48001:api unauthorized": "公众号未认证",
}


def should_capture(stderr_text, rc):
    """判定是否值得捕获。噪声与已知问题不重复记录。"""
    if rc == 0:
        return False, ""
    t = (stderr_text or "")[-800:]
    for n in NOISE:
        if n in t:
            return False, "噪声"
    return True, ""


def summarize(stderr_text):
    """从 stderr 提取一行可读摘要。"""
    if not stderr_text:
        return "命令返回非零退出码"
    lines = [l.strip() for l in stderr_text.strip().splitlines() if l.strip()]
    if not lines:
        return "命令返回非零退出码"
    # 优先取含 Error/Error/失败 的行
    for l in reversed(lines):
        low = l.lower()
        if any(k in low for k in ("error", "exception", "traceback", "失败", "错误", "denied")):
            return l[:160]
    return lines[-1][:160]


def run(argv):
    """执行命令并捕获失败"""
    if not argv:
        print("用法: evos_hook.py run -- <命令> [参数...]")
        return 1

    t0 = time.time()
    started = datetime.datetime.now().isoformat(timespec="seconds")
    proc = subprocess.run(argv, capture_output=True, text=True,
                          encoding="utf-8", errors="replace")
    elapsed = time.time() - t0

    cmd_str = " ".join(Path(a).name if a.endswith(".py") else a for a in argv)

    if proc.returncode != 0:
        ok, why = should_capture(proc.stderr, proc.returncode)
        if ok:
            summary = summarize(proc.stderr)
            # 已知错误 → 关联到已有规则而非新建
            matched = next((v for k, v in KNOWN.items() if k in (proc.stderr or "")), None)
            if matched:
                it, dup = E.record_observation(matched, f"命令: {cmd_str}")
                print(f"[evos] 已关联已知问题: {matched}（累计 {it['observed_count']} 次）",
                      file=sys.stderr)
            else:
                it = E.capture("bash_error",
                               f"命令 {cmd_str} 执行失败",
                               summary)
                print(f"[evos] 已捕获 {it['id']}：{summary}", file=sys.stderr)
        elif why:
            print(f"[evos] 跳过（{why}）", file=sys.stderr)

    # 原样转发输出，不吞掉
    if proc.stdout:
        sys.stdout.write(proc.stdout)
    if proc.stderr:
        sys.stderr.write(proc.stderr)

    # 追加耗时到 EVOS 统计
    st = E.load_stats()
    st.setdefault("commands", []).append(
        {"cmd": cmd_str, "rc": proc.returncode, "sec": round(elapsed, 2),
         "at": started})
    st["commands"] = st["commands"][-200:]   # 只留最近 200 条
    E.save_stats(st)

    return proc.returncode


def sweep():
    """巡检：对 dispatcher 常用子命令跑一遍，看哪些还坏着"""
    py = r"C:/Users/Administrator/.workbuddy/binaries/python/envs/default/Scripts/python.exe"
    checks = [
        [py, str(ROOT / "tools" / "dispatcher.py"), "plan"],
        [py, str(ROOT / "tools" / "evos.py"), "verify"],
        [py, str(ROOT / "tools" / "capability.py"), "status"],
    ]
    print("=== EVOS 巡检 ===\n")
    results = []
    for c in checks:
        name = Path(c[1]).name + " " + (c[2] if len(c) > 2 else "")
        p = subprocess.run(c, capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        status = "✓" if p.returncode == 0 else "✗"
        print(f"  {status} {name}")
        if p.returncode != 0:
            s = summarize(p.stderr)
            print(f"      {s}")
            E.capture("bash_error", f"巡检失败: {name}", s)
        results.append((name, p.returncode))
    print(f"\n{sum(1 for _, rc in results if rc == 0)}/{len(results)} 项通过")
    return results


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
    elif sys.argv[1] == "run":
        sep = sys.argv.index("--") if "--" in sys.argv else 0
        argv = sys.argv[sep + 1:] if sep else sys.argv[2:]
        sys.exit(run(argv))
    elif sys.argv[1] == "sweep":
        sweep()
    else:
        print(__doc__)
