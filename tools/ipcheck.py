# -*- coding: utf-8 -*-
"""ipcheck：公众号 IP 白名单诊断助手

为什么需要这个：
你的出口 IP 会变（多网卡 + 代理残留），手动加白名单每次都要重来。
本工具不修改白名单（那需要账号权限），只做两件事：
  1. 报出「微信接口当前看到的 IP」—— 这才是要加白名单的那个
  2. 判断是否稳定，避免加错

用法:
    python tools/ipcheck.py            # 检查一次
    python tools/ipcheck.py --watch    # 持续监测，IP 变了就提醒
"""
import re
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import store  # noqa: E402

API = "https://api.weixin.qq.com/cgi-bin/token?grant_type=client_credential&appid={}&secret={}"


def current_ip():
    """让微信接口报出它看到的 IP —— 这是唯一准确的来源"""
    env = store.env()
    if not (env.get("WX_APPID") and env.get("WX_APPSECRET")):
        return None, "未配置公众号密钥"
    try:
        r = urllib.request.urlopen(
            API.format(env["WX_APPID"], env["WX_APPSECRET"]), timeout=10
        ).read().decode()
    except Exception as e:
        return None, f"{type(e).__name__}"
    m = re.search(r"invalid ip (\d+\.\d+\.\d+\.\d+)", r)
    if m:
        return m.group(1), "not_in_whitelist"
    if "access_token" in r:
        return "已通过白名单", "ok"
    return None, r[:120]


def sample(n=3, gap=1.5):
    """多次采样判断稳定性"""
    seen = {}
    for _ in range(n):
        ip, st = current_ip()
        if ip:
            seen[ip] = seen.get(ip, 0) + 1
        time.sleep(gap)
    return seen


def report():
    seen = sample(3)
    if not seen:
        print("接口查询失败，检查网络或密钥")
        return
    print()
    print("=" * 46)
    print(" 公众号 IP 白名单诊断")
    print("=" * 46)
    print()
    for ip, cnt in seen.items():
        print(f"  微信看到的 IP: {ip}   （3 次采样中占 {cnt} 次）")
    print()
    if len(seen) == 1:
        ip = list(seen)[0]
        if ip == "已通过白名单":
            print("  ✓ 白名单已生效，可以直接灌稿")
        else:
            print(f"  → 需要把这个 IP 加进白名单：")
            print(f"     {ip}")
            print()
            print("     mp.weixin.qq.com → 设置与开发 → 基本配置")
            print("     → IP 白名单 → 添加")
    else:
        print("  ⚠ IP 有波动，白名单会反复失效")
        print()
        print("  原因通常是多网卡或代理残留。处理方式：")
        print("    1. 断开不用的 VPN / 加速器")
        print("    2. 留一次采样，把所有出现过的 IP 都加进白名单")
        print("    3. 或改用手动粘贴草稿箱（不依赖 API）")
    print()


def watch(interval=60):
    print("持续监测中，IP 变化会立即提示（Ctrl+C 停止）\n")
    last = None
    while True:
        ip, st = current_ip()
        if ip and ip != last:
            print(f"[{time.strftime('%H:%M:%S')}] 当前 IP: {ip}  ({st})")
            if last and last != "已通过白名单":
                print(f"  ⚠ IP 已从 {last} 变为 {ip}，需要更新白名单")
            last = ip
        time.sleep(interval)


if __name__ == "__main__":
    if "--watch" in sys.argv:
        watch()
    else:
        report()
