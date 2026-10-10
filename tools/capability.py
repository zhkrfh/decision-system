# -*- coding: utf-8 -*-
"""capability：OPC 能力层——把重计算推到云端，本机只做编排

设计前提：本机 4 核 / 3.9 GB 内存，不可本地跑模型。
本模块提供轻量 API 调用封装，所有调用都是 IO 等待，内存占用 < 30 MB。

配置：统一从环境变量或 .env 读取，密钥永不入日志。
"""
import json
import os
import time
import urllib.request
import urllib.error
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = ROOT / ".env"


# ── 配置层 ──────────────────────────────────────────────
def load_env():
    """从 .env 读取，不写入任何日志。"""
    cfg = {}
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                cfg[k.strip()] = v.strip()
    # 环境变量优先
    for k in list(os.environ.keys()):
        if k.isupper() and "_" in k:
            cfg[k] = os.environ[k]
    return cfg


def cfg(key, default=None):
    return load_env().get(key, default)


def require(key):
    v = cfg(key)
    if not v:
        raise SystemExit(
            f"缺少配置 {key}\n"
            f"  请在 {ENV_FILE} 中添加 {key}=<你的密钥>\n"
            f"  注意：不要把密钥写进对话记录，那会被明文落盘。"
        )
    return v


def status():
    """查看已配置的能力，不显示任何密钥值。"""
    keys = {
        "LLM_API_BASE": "大模型 API 地址",
        "LLM_API_KEY": "大模型 API 密钥",
        "STT_API_KEY": "语音转写 API",
        "STT_API_BASE": "语音转写地址",
        "WX_APPID": "公众号 AppID",
        "WX_APPSECRET": "公众号 AppSecret",
        "GITHUB_TOKEN": "GitHub 令牌",
        "ZHIHU_ACCESS_SECRET": "知乎开放平台",
        "OSS_AK": "对象存储 AccessKey",
        "OSS_SK": "对象存储 SecretKey",
    }
    c = load_env()
    print("\n=== 能力配置状态 ===\n")
    ok = miss = 0
    for k, desc in keys.items():
        if c.get(k):
            v = c[k]
            masked = (v[:6] + "***") if len(v) > 10 else "***"
            print(f"  ✓ {desc:<18} {k} = {masked}")
            ok += 1
        else:
            print(f"  ○ {desc:<18} {k}（未配置）")
            miss += 1
    print(f"\n已配置 {ok} 项，缺失 {miss} 项")
    print("配置位置：", ENV_FILE)
    print("\n安全提示：密钥只放 .env（已在 .gitignore 中），不要粘贴进对话。")
    return ok, miss


# ── 通用 HTTP ────────────────────────────────────────────
def http(method, url, headers=None, body=None, timeout=60, retries=2):
    """带重试的 HTTP 调用。日志只记状态码，不记内容（防密钥泄漏）。"""
    last = None
    for attempt in range(retries + 1):
        try:
            data = json.dumps(body).encode() if isinstance(body, (dict, list)) else body
            h = {"Content-Type": "application/json"} if isinstance(body, (dict, list)) else {}
            h.update(headers or {})
            req = urllib.request.Request(url, data=data, headers=h, method=method)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                raw = r.read().decode("utf-8", "replace")
                try:
                    return {"ok": True, "status": r.status, "data": json.loads(raw)}
                except json.JSONDecodeError:
                    return {"ok": True, "status": r.status, "data": raw}
        except urllib.error.HTTPError as e:
            last = f"HTTP {e.code}"
            # 4xx 不重试（除 429）
            if e.code < 500 and e.code != 429:
                return {"ok": False, "status": e.code, "error": last,
                        "hint": _http_hint(e.code)}
        except Exception as e:
            last = type(e).__name__
        if attempt < retries:
            time.sleep(1.5 * (attempt + 1))
    return {"ok": False, "status": None, "error": last}


def _http_hint(code):
    return {
        400: "请求格式错误，检查 body 结构",
        401: "密钥无效或已过期 —— 这是最常见原因，建议重置密钥",
        403: "权限不足，检查密钥作用域",
        404: "地址错误，检查 BASE URL",
        429: "触发限流，降低频率或升级套餐",
    }.get(code, "查看平台文档")


# ── 能力 1 · 大模型调用 ─────────────────────────────────
def llm(prompt, system="你是一个严谨的分析助手。回答简洁，给出可执行的下一步。",
        model=None, max_tokens=2000, temperature=0.3):
    """调用云端大模型。这是绕过本机内存限制的核心能力。

    用法:
      llm("把这段会议记录提炼成三条待办")
      llm("评估这个方案", system="你是一个怀疑论的审稿人")
    """
    base = cfg("LLM_API_BASE") or cfg("LLM_BASE_URL")
    key = cfg("LLM_API_KEY")
    if not (base and key):
        return {"ok": False, "error": "未配置 LLM_API_BASE / LLM_API_KEY",
                "hint": f"在 {ENV_FILE} 中配置；建议用云端 API，本机跑不动模型"}
    url = base.rstrip("/") + "/chat/completions"
    body = {
        "model": model or cfg("LLM_MODEL", "gpt-4o-mini"),
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    r = http("POST", url, {"Authorization": f"Bearer {key}"}, body)
    if r["ok"] and isinstance(r.get("data"), dict):
        try:
            return {"ok": True,
                    "text": r["data"]["choices"][0]["message"]["content"],
                    "usage": r["data"].get("usage")}
        except (KeyError, IndexError):
            return {"ok": False, "error": "响应结构异常", "raw": str(r["data"])[:200]}
    return r


def llm_batch(tasks, system=None, model=None):
    """批量处理。串行执行以控制内存与频率。"""
    results = []
    for i, t in enumerate(tasks, 1):
        r = llm(t, system=system, model=model)
        results.append({"index": i, "task": t[:50], "result": r})
    return results


# ── 能力 2 · 语音转写（家史服务核心）────────────────────
def transcribe(audio_path, model=None, language="zh"):
    """云端语音转写。本机不做转写（内存不足）。

    支持格式由 API 决定，常见 mp3/wav/m4a。
    需 multipart/form-data 上传。
    """
    key = cfg("STT_API_KEY")
    base = cfg("STT_API_BASE", "https://api.openai.com/v1")
    if not key:
        return {"ok": False, "error": "未配置 STT_API_KEY",
                "hint": "家史服务的必需能力；本机内存无法本地转写"}
    p = Path(audio_path)
    if not p.exists():
        return {"ok": False, "error": f"文件不存在: {p}"}

    boundary = "----EVOSBoundary7f3a"
    body = b""
    body += f"--{boundary}\r\n".encode()
    body += f'Content-Disposition: form-data; name="file"; filename="{p.name}"\r\n'.encode()
    body += b"Content-Type: application/octet-stream\r\n\r\n"
    body += p.read_bytes() + b"\r\n"
    body += f"--{boundary}\r\n".encode()
    body += b'Content-Disposition: form-data; name="model"\r\n\r\n'
    body += (model or cfg("STT_MODEL", "whisper-1")).encode() + b"\r\n"
    body += f"--{boundary}\r\n".encode()
    body += b'Content-Disposition: form-data; name="language"\r\n\r\n'
    body += language.encode() + b"\r\n"
    body += f"--{boundary}--\r\n".encode()

    url = base.rstrip("/") + "/audio/transcriptions"
    r = http("POST", url, {
        "Authorization": f"Bearer {key}",
        "Content-Type": f"multipart/form-data; boundary={boundary}",
    }, body, timeout=600)
    return r


# ── 能力 3 · 本机健康快照 ────────────────────────────────
def health():
    """本机状态快照。用于每日复盘，判断是否需要进一步清理。"""
    import ctypes, shutil, subprocess

    class MS(ctypes.Structure):
        _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("sullAvailExtended", ctypes.c_ulonglong)]
    m = MS(); m.dwLength = ctypes.sizeof(MS)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))

    out = subprocess.run(["tasklist", "/fo", "csv", "/nh"],
                         capture_output=True, text=True, encoding="utf-8", errors="replace").stdout
    from collections import defaultdict
    g, c = defaultdict(float), defaultdict(int)
    for l in out.splitlines():
        p = [x.strip('"') for x in l.split('","')]
        if len(p) >= 5:
            try: g[p[0]] += int(p[4].replace(",", "").replace(" K", "")) / 1024 / 1024
            except: pass
            c[p[0]] += 1

    disks = {}
    for d in ("C:", "E:"):
        try:
            u = shutil.disk_usage(d + "/")
            disks[d] = {"total_gb": round(u.total / 1024**3, 1),
                        "free_gb": round(u.free / 1024**3, 1),
                        "used_pct": round(100 - u.free / u.total * 100, 1)}
        except: pass

    top = sorted(g.items(), key=lambda x: -x[1])[:8]
    return {
        "memory_total_gb": round(m.ullTotalPhys / 1024**3, 2),
        "memory_avail_gb": round(m.ullAvailPhys / 1024**3, 2),
        "memory_load_pct": m.dwMemoryLoad,
        "disks": disks,
        "process_count": sum(c.values()),
        "top_processes": [{"name": k, "mem_gb": round(v, 2), "instances": c[k]}
                          for k, v in top],
    }


def health_report():
    h = health()
    print("\n=== 本机健康快照 ===\n")
    load = h["memory_load_pct"]
    flag = "🔴" if load > 90 else ("⚠" if load > 80 else "✓")
    print(f"  {flag} 内存 {h['memory_avail_gb']}/{h['memory_total_gb']} GB 可用（占用 {load}%）")
    for d, v in h["disks"].items():
        f2 = "🔴" if v["free_gb"] < 15 else "✓"
        print(f"  {f2} {d} 盘 可用 {v['free_gb']}/{v['total_gb']} GB（已用 {v['used_pct']}%）")
    print(f"\n  进程总数 {h['process_count']}")
    print("\n  内存 TOP:")
    for p in h["top_processes"]:
        print(f"    {p['mem_gb']:>5.2f} GB  x{p['instances']:<3} {p['name'][:32]}")
    print()
    return h


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2 or sys.argv[1] == "status":
        status()
    elif sys.argv[1] == "health":
        health_report()
    elif sys.argv[1] == "llm":
        r = llm(sys.argv[2])
        print(r.get("text") if r.get("ok") else f"失败: {r.get('error')} {r.get('hint','')}")
    else:
        print(__doc__)
