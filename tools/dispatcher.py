# -*- coding: utf-8 -*-
"""分发台 Dispatcher v0.6（模块化重构：store/wx_api/zhihu_api/prep/flows）
蚁小二技术逻辑本地化：草稿箱=prep+ledger 状态机；数据回收=metric/report/monitor；
一稿多发=dispatch。核心纪律：自动化做到发布键前一格，按键永远归用户。

用法:
  python tools/dispatcher.py plan                # 各平台待办看板
  python tools/dispatcher.py wx-status           # 公众号草稿箱/已发表
  python tools/dispatcher.py wx-check            # 公众号草稿核验(乱码/口径)
  python tools/dispatcher.py prep xhs [稿名]     # 小红书预填规程+台账登记
  python tools/dispatcher.py ledger [list]       # 发布台账
  python tools/dispatcher.py ledger confirm <稿名> --status published --ref <链接>
  python tools/dispatcher.py log <平台> <标题> <状态> [备注]
  python tools/dispatcher.py metric <平台> <标题> <指标> <数值>
  python tools/dispatcher.py report [周|月]      # 指标汇总
  python tools/dispatcher.py monitor [配置文件]  # 公开页指标抓取回填
  python tools/dispatcher.py post <telegram|bluesky|devto> <标题> <正文文件>
  python tools/dispatcher.py dispatch <md文件>   # 一键分发（发布键归你）
  python tools/dispatcher.py zh-scout            # 知乎选题侦察（热榜+垂直搜索）
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import store, wx_api, zhihu_api, prep, flows  # noqa: E402

def main():
    a = sys.argv[1:]
    if not a: print(__doc__); return
    cmd = a[0]
    if cmd == "plan": flows.plan()
    elif cmd == "wx-status": wx_api.status()
    elif cmd == "wx-check": wx_api.check()
    elif cmd == "prep": prep.prep_xhs(a[2] if len(a) > 2 else "案例05_资格期断桥")
    elif cmd == "ledger": prep.ledger_cmd(a[1:])
    elif cmd == "log": store.append(store.PLOG, [a[1], a[2], a[3], a[4] if len(a) > 4 else ""]); print("logged")
    elif cmd == "metric": store.append(store.MET, [a[1], a[2], a[3], a[4]]); print("metric logged")
    elif cmd == "report": flows.report(*(a[1:2] or ["周"]))
    elif cmd == "post": flows.post(a[1], a[2], a[3])
    elif cmd == "monitor": flows.monitor(a[1] if len(a) > 1 else None)
    elif cmd == "dispatch": flows.dispatch(a[1])
    elif cmd == "zh-scout": zhihu_api.scout()
    else: print(__doc__)

if __name__ == "__main__":
    main()
