# -*- coding: utf-8 -*-
"""prep_xhs_dp.py —— DrissionPage 版小红书预填（蚁小二流程·停在发布键）
用法:
  python tools/prep_xhs_dp.py                 # 预填 assets/xhs_v2 最新稿
  python tools/prep_xhs_dp.py --stats         # 打开笔记管理页（数据人工抄）
首次运行弹出浏览器登录小红书创作平台，登录态存 ./dp_data，之后免扫码。
铁律：脚本停在发布键前，发布/AI声明 永远人工。
"""
import sys, json
from pathlib import Path
from DrissionPage import ChromiumPage, ChromiumOptions

ROOT = Path(__file__).resolve().parent.parent
PUB_URL = "https://creator.xiaohongshu.com/publish/publish?from=tab_switch"

# 小红书标题上限 20 字（页面计数器实测：23/20 会超限卡提交）
TITLE_MAX = 20
TITLE = "差点把8分的机会全押，后来我查了一条线"   # 18 字

def new_page(headless=False):
    co = ChromiumOptions()
    co.set_browser_path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")  # 本机无Chrome，用Edge内核
    co.set_local_port(9333)                      # 独立实例，不碰用户浏览器
    co.set_user_data_path(str(ROOT / "dp_data")) # 登录态持久化
    co.headless(headless)
    return ChromiumPage(co)

def dismiss_permission_dialogs(page):
    """关掉 Edge 的权限请求弹窗。

    踩坑：Edge 首次以远程调试模式启动时会弹 edge://permission-request-dialog
    （询问是否允许自动化控制）。该模态框会遮挡页面，导致后续元素定位全部超时，
    表现为「脚本卡住无输出、标题框永远不出现」。

    API 注意：Chromium 对象没有 .tabs 属性，须用 get_tabs()（DrissionPage 4.1.x）。
    """
    for _ in range(5):
        try:
            bad = [t for t in page.browser.get_tabs()
                   if "permission-request-dialog" in (t.url or "")]
        except Exception as e:
            print(f">> 弹窗检查异常（忽略）: {e}", flush=True)
            return True
        if not bad:
            return True
        for t in bad:
            try:
                t.close()          # 直接关掉弹窗标签页
                print(">> 已关闭 Edge 权限请求弹窗", flush=True)
            except Exception:
                try:
                    t.actions.key_down("ESC").key_up("ESC")
                except Exception:
                    pass
        page.wait(0.5)
    return True


def fill():
    cards = sorted((ROOT / "assets/xhs_v2").glob("卡*.png"))
    # 读当前要发的稿（默认取最新生成的正典正文）
    BODY_FILE = ROOT / "docs/小红书发布包/先查能不能输_小红书正文.txt"
    body = BODY_FILE.read_text(encoding="utf-8").split("#职业规划")[0].rstrip()
    title = TITLE
    tags = ["职业规划", "求职", "决策方法", "裸辞", "跳槽", "应届生", "实习"]
    # 标题长度自检：不超限才继续，否则提前失败并说明
    if len(title) > TITLE_MAX:
        sys.exit(f"标题超限：{len(title)}字 > {TITLE_MAX}字 —— {title}")
    # 正文去掉尾部话题串，统一由本脚本追加，保证位置可控
    body = body.rstrip()
    if len(cards) != 5:
        sys.exit(f"卡片不足5张: {[c.name for c in cards]}")

    page = new_page()
    page.get(PUB_URL)
    page.wait(3)
    dismiss_permission_dialogs(page)
    # 登录检测：URL跳转或页面含扫码/登录浮层
    if "login" in page.url or page.ele('text:扫码', timeout=3) or page.ele('css:.login-container,.qrcode', timeout=3):
        print(">> 未登录。请在弹出的浏览器窗口里扫码登录（登录态已保存，以后免扫码）...", flush=True)
        for _ in range(60):  # 最多等5分钟
            page.wait(5)
            if "login" not in page.url and page.ele('text=上传图文', timeout=2):
                break
        else:
            sys.exit("等待登录超时（5分钟）。重跑即可。")
        page.get(PUB_URL); page.wait(3)
    # 页面有3个同名「上传图文」元素，第1个在屏幕外（隐藏抽屉），
    # 只点屏幕内顶部坐标(y<200)的才是真tab；盲点第一个=图片全丢进视频通道
    cands = [e for e in page.eles('text=上传图文')
             if e.states.is_displayed and 0 < e.rect.location[0] < 800 and e.rect.location[1] < 200]
    if not cands:
        sys.exit("找不到可见的「上传图文」tab")
    cands[-1].click(); page.wait(1.5)
    inp = page.ele('css:input[type=file][accept*=image]', timeout=5) or page.ele('css:input.upload-input', timeout=5)
    if not inp:
        sys.exit("切tab后未找到图片file input（可能仍在视频tab）")
    inp.input([str(c) for c in cards])
    page.wait.ele_displayed('css:input[placeholder*="标题"]', timeout=60)
    dismiss_permission_dialogs(page)   # 上传期间可能再弹
    print("[1/5] 5张卡上传完成")

    # 2. 标题（上传后表单渲染慢，最多等30秒）
    t = page.ele('css:input[placeholder*="标题"]', timeout=15)
    if not t and page.ele('css:.captcha-form,[class*=captcha]', timeout=3):
        print(">> 触发验证码！请在弹出的浏览器窗口里手动完成验证（平台对新实例的反自动化检测，属正常）...", flush=True)
        t = page.ele('css:input[placeholder*="标题"]', timeout=120)  # 人工解题后表单出现
    if not t:
        (ROOT/"dp_data/debug_no_title.html").write_text(page.html, encoding="utf-8")
        sys.exit("标题框未出现（验证码未解或页面变更），debug已存")
    t.clear(); t.input(title)
    print("[2/5] 标题完成")

    # 3. 正文（tiptap ProseMirror）—— 话题直接并入正文一次性输入
    #    踩过的坑：单独 ed.input(" #tag") 时编辑器光标不在末尾，
    #    话题被插进正文中间（实测插到「最高轻仓，加 __话题__ 12个月止损线」）。
    #    正确做法：正文 + 空行 + 整串话题，一次性 input(clear=True)，光标无歧义。
    ed = page.ele('css:[contenteditable="true"]', timeout=15)
    if not ed:
        sys.exit("正文编辑器未出现")
    ed.click()
    page.actions.key_down("CTRL").key_down("a").key_up("a").key_up("CTRL")
    full_body = f"{body}\n\n{' '.join('#'+t for t in tags)}"
    ed.input(full_body, clear=True)
    print(f"[3/5] 正文完成({len(body)}字 + {len(tags)}个话题)")

    # 4. 校验话题是否落在正文末尾（防回归）
    page.wait(1)
    probe = (ed.text or "")
    tail = probe[-60:].replace("\n", " ")
    ok_tail = "#实习" in probe[-80:]
    print(f"[4/5] 话题位置校验：{'✓ 在正文末尾' if ok_tail else '✗ 未落在末尾，需手动核对'}")
    print(f"      正文末尾：…{tail}")

    # 5. 停在发布键
    btn = page.ele('text=发布笔记')
    print("[5/5] 预填完成。核验后自行点击「发布笔记」。")
    print("发布后登记台账：")
    print("  python tools/dispatcher.py prep 小红书 连载04_先查能不能输")
    print("  python tools/dispatcher.py ledger confirm 连载04_先查能不能输 --status published --ref <链接>")
    print()
    print("浏览器保持打开（预填状态已保存），可直接核验后点发布。")
    print("关闭浏览器窗口即结束；如需重填，重跑本脚本即可。")
    # 阻塞保持浏览器存活，避免脚本退出连带关闭导致预填丢失
    try:
        print("（等待中，关闭窗口或按 Ctrl+C 结束）")
        page.wait(36000)
    except KeyboardInterrupt:
        print("已结束")

def stats():
    page = new_page()
    page.get("https://creator.xiaohongshu.com/publish/noteManage?source=official")
    print(page.html[:0] or "浏览器已打开笔记管理页，抄数后回填：")
    print("  python tools/dispatcher.py metric 小红书 <标题> 曝光 <n> ...")

if __name__ == "__main__":
    fill() if "--stats" not in sys.argv else stats()
