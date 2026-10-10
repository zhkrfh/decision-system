# -*- coding: utf-8 -*-
"""opc：OPC 能力平台统一入口

把分散的工具聚合成一条命令。按本机约束设计：
- 4 核 / 3.9 GB 内存 → 所有子命令必须轻量，禁止常驻
- 重计算走云端 API（见 capability.py）
- 一切操作走 EVOS 引擎记录经验

子命令:
  health      本机健康快照（含内存/磁盘/进程）
  doctor      快速诊断：环境、依赖、能力状态
  clean       清理缓存（走回收站）
  evos        经验系统（status/verify/scan/trial/...）
  content     内容中心（plan/index/queue）
  publish     发布分发（wx-status/wx-check/prep/dispatch）
  zancun      算仓交付（questionnaire/check/record）
  cap         能力层（status/llm/health）
  git         仓库操作（log/status/commit/push，带 EVOS 记录）
  check       内容自检（recalc/audit/lint/due 发布前一键把关）
  all         依次跑全部只读检查
"""
import os
import sys
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOOLS = ROOT / "tools"
PY = sys.executable


def run_tool(script, *args, capture=True):
    """调用 tools/ 下的脚本。

    优先用带 requests 的 venv 解释器（dispatcher 依赖它），
    否则回退到当前解释器。
    """
    global PY
    venv_py = Path.home() / ".workbuddy" / "binaries" / "python" / "envs" / "default" / "Scripts" / "python.exe"
    interp = str(venv_py) if venv_py.exists() else PY
    p = subprocess.run([interp, str(TOOLS / script)] + list(args),
                       capture_output=capture, text=True,
                       encoding="utf-8", errors="replace")
    return p.returncode, p.stdout, p.stderr


def _cap(text):
    """取子命令说明"""
    for line in (text or "").splitlines():
        if line.strip().startswith("用法:") or line.strip().startswith("python tools/"):
            return line.strip()
    return ""


# ── 子命令 ──────────────────────────────────────────────
def cmd_health():
    return run_tool("capability.py", "health")


def cmd_doctor(args=None):
    """快速诊断：一眼看清环境状态"""
    print("\n" + "=" * 58)
    print(" OPC 平台诊断")
    print("=" * 58)

    import ctypes, shutil, platform
    class MS(ctypes.Structure):
        _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("sullAvailExtended", ctypes.c_ulonglong)]
    m = MS(); m.dwLength = ctypes.sizeof(MS)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))

    print(f"\n[本机]")
    print(f"  系统     {platform.platform()[:40]}")
    print(f"  内存     {m.ullAvailPhys / 1024**3:.1f}/{m.ullTotalPhys / 1024**3:.1f} GB "
          f"(占用 {m.dwMemoryLoad}%)")
    for d in ("C:", "E:"):
        try:
            u = shutil.disk_usage(d + "/")
            print(f"  {d} 盘     可用 {u.free / 1024**3:.1f}/{u.total / 1024**3:.1f} GB")
        except Exception:
            pass

    print(f"\n[工具链]")
    print(f"  ✓ Python  {PY}")
    for name, cmd in [("Git", "git"), ("Node", "node")]:
        r = subprocess.run(["where" if os.name == "nt" else "which", cmd],
                           capture_output=True, text=True)
        print(f"  {'✓' if r.returncode == 0 else '✗'} {name}")

    # requests 检查：可能在独立 venv 里，不在当前解释器
    venv_py = Path.home() / ".workbuddy" / "binaries" / "python" / "envs" / "default" / "Scripts" / "python.exe"
    req_ok = False
    req_where = ""
    for py in (venv_py, Path(PY)):
        if not py.exists():
            continue
        r = subprocess.run([str(py), "-c", "import requests;print(requests.__version__)"],
                           capture_output=True, text=True)
        if r.returncode == 0:
            req_ok = True
            req_where = f"{py.parent.parent.parent.name}({r.stdout.strip()})"
            break
    if req_ok:
        print(f"  ✓ requests {r.stdout.strip()} @ {req_where}")
    else:
        print(f"  ✗ requests 未安装 —— dispatcher 会失败")
        print(f"    修复: {venv_py} -m pip install requests")

    print(f"\n[项目模块]")
    mods = sorted(p.stem for p in TOOLS.glob("*.py"))
    print(f"  {len(mods)} 个模块: {', '.join(mods)}")

    print(f"\n[关键能力]")
    try:
        sys.path.insert(0, str(TOOLS))
        import capability as C
        c = C.load_env()
        for k, d in [("LLM_API_KEY", "大模型"), ("STT_API_KEY", "语音转写"),
                     ("WX_APPID", "公众号"), ("GITHUB_TOKEN", "GitHub"),
                     ("ZHIHU_ACCESS_SECRET", "知乎")]:
            print(f"  {'✓' if c.get(k) else '○'} {d}")
        if not c.get("LLM_API_KEY"):
            print(f"\n  提示：大模型 API 未配置 → 本机无法本地推理")
    except Exception as e:
        print(f"  能力层加载失败: {e}")

    print(f"\n[EVOS]")
    try:
        sys.path.insert(0, str(TOOLS))
        import evos_core as E
        items = E.load_all()
        by = {}
        for i in items:
            by[i["status"]] = by.get(i["status"], 0) + 1
        print(f"  经验 {len(items)} 条: {by}")
        due = E.scan_due_predictions()
        for d in due:
            flag = "已到期!" if d["due"] else f"{d['days_left']}天"
            print(f"  预测 #{d['no']} {flag}")
    except Exception as e:
        print(f"  EVOS 加载失败: {e}")
    print()
    return 0


def cmd_clean(args):
    print("清理请用 safe_clean.py（在工作区），或执行 opc.py clean --go")
    return run_tool("../safe_clean.py" if (ROOT.parent.parent / "safe_clean.py").exists()
                    else "capability.py", "status")


def cmd_evos(args):
    return run_tool("evos.py", *args)


def cmd_content(args):
    return run_tool("dispatcher.py", *args)


def cmd_publish(args):
    return run_tool("dispatcher.py", *args)


def cmd_zancun(args):
    return run_tool("zancun.py", *args)


def cmd_cap(args):
    return run_tool("capability.py", *args)


def cmd_git(args):
    p = subprocess.run(["git"] + list(args), cwd=ROOT,
                       capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if p.stdout:
        print(p.stdout)
    if p.returncode != 0 and p.stderr:
        print(p.stderr, file=sys.stderr)
    return p.returncode, "", ""


def cmd_check(args):
    """内容自检：发布前一键把关

    recalc 算术复算（A3）—— 独立复算文中算式，不符即报警
    audit  口径审计（A4）—— 旧值/旧公式残留，三层判定
    lint   标题钩子（A5/A6）—— 场景化标题、场景化开头
    due    预测到期（E5）—— 到期未登记进 EVOS 捕获

    无参数时跑前三项只读检查；due 只扫不写，避免误改经验库。
    """
    argv = list(args or [])
    sub = argv[0] if argv and not argv[0].startswith("-") else "all"

    if sub == "recalc":
        return run_tool("recalc.py", *argv[1:])
    if sub == "audit":
        return run_tool("audit.py", *argv[1:])
    if sub == "lint":
        return run_tool("lint.py", *argv[1:])
    if sub == "due":
        # capture 会写 EVOS 库，必须显式指定，避免 check 时误改经验库
        if len(argv) > 1 and argv[1] == "capture":
            print("提示：capture 会写入 EVOS 经验库，确认后执行")
        return run_tool("due.py", *argv[1:])

    # 默认：三项只读检查汇总
    checks = [
        ("算术复算", "recalc.py", []),
        ("口径审计", "audit.py", []),
        ("标题钩子", "lint.py", []),
        ("预测到期", "due.py", ["scan"]),
    ]
    print("\n" + "=" * 58)
    print(" 内容自检（发布前把关）")
    print("=" * 58)
    results = []
    for name, script, cargs in checks:
        t0 = time.time()
        rc, out, err = run_tool(script, *cargs)
        results.append((name, rc, out, time.time() - t0))

    for name, rc, out, dur in results:
        mark = "✓" if rc == 0 else "!"
        print(f"  {mark} {name:<10} {dur:.1f}s")

    # 汇总关键结论
    print()
    for name, rc, out, _ in results:
        if not out:
            continue
        for line in out.splitlines():
            s = line.strip()
            if s.startswith("共复算") or s.startswith("合计") or s.startswith("→"):
                print(f"  {name}：{s}")

    failed = [n for n, rc, _, _ in results if rc != 0]
    print()
    if failed:
        print(f"  {len(failed)} 项待处理：{'、'.join(failed)}")
        print("  建议逐项查看：python tools/opc.py check <子项>")
    else:
        print("  全部通过")
    print()
    return 1 if failed else 0


def cmd_all(args=None):
    """依次跑全部只读检查"""
    checks = [
        ("本机健康", lambda: _rc(cmd_health())),
        ("环境诊断", lambda: _rc(cmd_doctor())),
        ("EVOS 看板", lambda: _rc(run_tool("evos.py", "status"))),
        ("内容看板", lambda: _rc(run_tool("dispatcher.py", "plan"))),
        ("预测到期", lambda: _rc(run_tool("evos.py", "scan"))),
        ("内容自检", lambda: _rc(cmd_check([]))),
    ]
    print("\n" + "=" * 58)
    print(" 全量只读检查")
    print("=" * 58)
    results = []
    for name, fn in checks:
        t0 = time.time()
        try:
            ok = (fn() == 0)
        except Exception:
            ok = False
        results.append((name, ok, time.time() - t0))
        print(f"  {'✓' if ok else '✗'} {name:<12} {results[-1][2]:.1f}s")

    passed = sum(1 for _, ok, _ in results if ok)
    print(f"\n  {passed}/{len(results)} 项通过\n")
    return 0


def _rc(x):
    """统一返回值为 int 退出码"""
    if isinstance(x, tuple):
        return x[0]
    if isinstance(x, int):
        return x
    return 0


COMMANDS = {
    "health": (cmd_health, "本机健康快照"),
    "doctor": (cmd_doctor, "环境快速诊断"),
    "evos": (cmd_evos, "经验系统"),
    "content": (cmd_content, "内容中心"),
    "publish": (cmd_publish, "发布分发"),
    "zancun": (cmd_zancun, "算仓交付"),
    "cap": (cmd_cap, "能力层"),
    "git": (cmd_git, "仓库操作"),
    "check": (cmd_check, "内容自检（recalc/audit/lint/due）"),
    "all": (cmd_all, "全量只读检查"),
}


def usage():
    print(__doc__)
    print("可用子命令:")
    for k, (_, d) in COMMANDS.items():
        print(f"  {k:<10} {d}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        usage()
        sys.exit(0)
    c = sys.argv[1]
    if c in ("-h", "--help", "help"):
        usage()
    elif c in COMMANDS:
        fn, _ = COMMANDS[c]
        rc = fn(sys.argv[2:])
        sys.exit(rc if isinstance(rc, int) else 0)
    else:
        print(f"未知子命令: {c}\n")
        usage()
        sys.exit(1)
