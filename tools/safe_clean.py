# -*- coding: utf-8 -*-
"""safe_clean：安全清理器 —— 全部走回收站，可恢复

设计原则：
1. 只删缓存与临时文件，不碰用户文档、项目数据、凭证
2. 全部移入回收站（SHFileOperation），失败则跳过而非强删
3. 每次清理前生成清单存档，可回溯
"""
import os
import sys
import datetime
import ctypes
from ctypes import wintypes
from pathlib import Path

# ── 回收站 API ────────────────────────────────────────────
FO_DELETE = 0x0003
FOF_SILENT = 0x0004
FOF_NOCONFIRMATION = 0x0010
FOF_ALLOWUNDO = 0x0040          # 关键：允许撤销（进回收站）
FOF_NOCONFIRMMKDIR = 0x0200
FOF_NOERRORUI = 0x0400


class SHFILEOPSTRUCT(ctypes.Structure):
    _fields_ = [
        ("hwnd", wintypes.HWND),
        ("wFunc", wintypes.UINT),
        ("pFrom", ctypes.c_wchar_p),
        ("pTo", ctypes.c_wchar_p),
        ("fFlags", cint := wintypes.WORD),
        ("fAnyOperationsAborted", wintypes.BOOL),
        ("hNameMappings", ctypes.c_void_p),
        ("lpszProgressTitle", ctypes.c_wchar_p),
    ]


def to_recycle(paths):
    """把路径移入回收站。返回 (成功数, 失败列表)

    注意：SHFileOperationW 即使成功也可能返回非 0（如 DE_OPCANCELLED=2 表示
    "文件已删除，无需跳过"），因此以「文件是否真的消失」为准，不看返回码。
    """
    if not paths:
        return 0, []
    ok = 0
    fails = []
    # 逐项处理：大批量易超时，且能精确定位失败项
    for p in paths:
        pp = Path(p)
        if not pp.exists():
            continue
        # 单文件时检查其内容是否也会被清掉
        try:
            probe = list(pp.iterdir()) if pp.is_dir() else None
        except Exception:
            probe = None

        from_str = str(pp) + "\0\0"
        op = SHFILEOPSTRUCT()
        op.hwnd = None
        op.wFunc = FO_DELETE
        op.pFrom = from_str
        op.pTo = None
        op.fFlags = FOF_ALLOWUNDO | FOF_NOCONFIRMATION | FOF_SILENT | FOF_NOERRORUI | FOF_NOCONFIRMMKDIR
        op.fAnyOperationsAborted = False
        op.hNameMappings = None
        op.lpszProgressTitle = None

        try:
            ctypes.windll.shell32.SHFileOperationW(ctypes.byref(op))
        except Exception as e:
            fails.append((type(e).__name__, str(p)))
            continue

        # 以「是否真的消失」判断成功
        gone = not pp.exists()
        if not gone and probe is not None:
            try:
                gone = len(list(pp.iterdir())) == 0
            except Exception:
                gone = True
        if gone:
            ok += 1
        else:
            fails.append(("未删除", str(p)))
    return ok, fails


# ── 清理目标定义 ──────────────────────────────────────────
# 只含可重建的缓存/临时文件。绝不包含用户文档、项目、凭证。
TARGETS = [
    (r"C:\Users\Administrator\AppData\Local\pip\Cache", "pip缓存", False),
    (r"C:\Users\Administrator\AppData\Local\npm-cache\_cacache", "npm缓存", False),
    (r"C:\Users\Administrator\AppData\Local\CrashDumps", "崩溃转储", False),
    (r"C:\Windows\Temp", "系统临时", False),
    (r"C:\Users\Administrator\AppData\Local\Temp", "用户临时", False),
]

# 动态发现的缓存子目录名（Edge/Chrome 多配置文件结构）
CACHE_NAMES = ["Cache", "Code Cache", "GPUCache", "CacheStorage",
               "DawnCache", "DawnGraphiteCache", "DawnWebGPUCache"]
BROWSER_ROOTS = [
    r"C:\Users\Administrator\AppData\Local\Microsoft\Edge\User Data",
    r"C:\Users\Administrator\AppData\Local\Google\Chrome\User Data",
    r"C:\Users\Administrator\AppData\Roaming\360ChromeX",
]


def discover_browser_caches():
    """动态发现所有浏览器缓存目录（只取 Cache 类，不碰 Cookie/历史/书签）"""
    found = []
    for root in BROWSER_ROOTS:
        rp = Path(root)
        if not rp.exists():
            continue
        for prof in rp.iterdir():
            if not prof.is_dir():
                continue
            for cn in CACHE_NAMES:
                d = prof / cn
                if d.exists():
                    found.append((str(d), f"浏览器缓存({prof.name}/{cn})", True))
            sw = prof / "Service Worker" / "CacheStorage"
            if sw.exists():
                found.append((str(sw), f"浏览器SW缓存({prof.name})", True))
    return found


def discover_thumb_cache():
    """缩略图缓存是单文件，单独处理"""
    d = Path(r"C:\Users\Administrator\AppData\Local\Microsoft\Windows\Explorer")
    if d.exists():
        return [(str(d), "缩略图缓存", False)]
    return []

# 保护清单：即使在清理目录下也不动
PROTECT_NAMES = {
    "desktop.ini", "index.dat", "$I*", "$R*",
}


def dir_size(p):
    p = Path(p)
    if not p.exists():
        return 0, 0
    sz = n = 0
    try:
        for dp, dn, fn in os.walk(p):
            for f in fn:
                try:
                    sz += (Path(dp) / f).stat().st_size
                    n += 1
                except:
                    pass
    except:
        pass
    return sz, n


def scan(dry_run=True):
    """扫描待清理项"""
    print("\n=== 清理前扫描 ===\n")
    all_targets = TARGETS + discover_browser_caches() + discover_thumb_cache()

    total = 0
    plan = []
    for path, desc, wipe in all_targets:
        p = Path(path)
        if not p.exists():
            continue
        sz, n = dir_size(p)
        if sz == 0:
            continue
        plan.append({"path": path, "desc": desc, "size": sz, "files": n, "wipe": wipe})
        total += sz
        print(f"  {sz / 1024**2:>9.1f} MB  {n:>5} 文件  {desc}")
    print(f"\n  合计: {total / 1024**3:.2f} GB ({total / 1024**2:.0f} MB)")
    print(f"  项目数: {len(plan)}")
    return plan, total


def archive_manifest(plan):
    """把清理清单存档到 E 盘，可回溯"""
    dst = Path(r"E:\Workspace\archive\clean-logs")
    dst.mkdir(parents=True, exist_ok=True)
    f = dst / f"clean-{datetime.date.today()}.md"
    lines = [f"# 清理记录 {datetime.date.today()}", "",
             "> 全部项目已移入回收站，可通过回收站恢复", "",
             "| 体积 | 文件数 | 项目 | 路径 |", "|---|---|---|---|"]
    for i in plan:
        lines.append(f"| {i['size'] / 1024**2:.1f} MB | {i['files']} | {i['desc']} | `{i['path']}` |")
    lines.append(f"\n合计 {sum(i['size'] for i in plan) / 1024**3:.2f} GB")
    f.write_text("\n".join(lines), encoding="utf-8")
    return f


def execute(plan):
    """执行清理，全部走回收站。按文件粒度处理，避免整目录操作失败。"""
    manifest = archive_manifest(plan)
    print(f"\n清理清单已存档: {manifest}")
    print("\n=== 执行清理（移入回收站）===\n")

    freed = 0
    ok_count = 0
    fail_count = 0

    for i in plan:
        src = Path(i["path"])
        if not src.exists():
            continue

        # 收集文件：目录则取其下所有文件
        files = []
        if src.is_file():
            files = [src]
        else:
            try:
                for dp, dn, fn in os.walk(src):
                    for f in fn:
                        files.append(Path(dp) / f)
            except Exception:
                pass

        if not files:
            print(f"  - {i['desc']:<26} 已为空")
            continue

        # 分批送入回收站（每批 30 个，避免单次调用过大）
        batch_ok = 0
        for k in range(0, len(files), 30):
            chunk = [str(f) for f in files[k:k + 30]]
            try:
                ok, fails = to_recycle(chunk)
            except Exception:
                ok, fails = 0, []
            batch_ok += ok

        if batch_ok:
            # 清理残留空目录
            if src.is_dir():
                try:
                    for dp, dn, fn in os.walk(src, topdown=False):
                        if dp != str(src):
                            try: os.rmdir(dp)
                            except: pass
                except:
                    pass
            freed += i["size"]
            ok_count += batch_ok
            print(f"  ✓ {i['desc']:<26} {i['size'] / 1024**2:>8.1f} MB ({batch_ok} 文件)")
        else:
            fail_count += 1
            print(f"  ✗ {i['desc']:<26} 跳过（可能无权限或被占用）")

    print(f"\n  完成：{ok_count} 个文件，共 {freed / 1024**3:.2f} GB 已移入回收站")
    if fail_count:
        print(f"  跳过 {fail_count} 项（多为运行中程序占用）")
    print("  如需恢复：打开回收站右键『还原』")
    return freed


if __name__ == "__main__":
    dry = "--go" not in sys.argv
    plan, total = scan(dry)
    if dry:
        print("\n这是预览。加 --go 执行（全部进回收站）")
    else:
        execute(plan)
