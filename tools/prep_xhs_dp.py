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

def new_page(headless=False):
    co = ChromiumOptions()
    co.set_browser_path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")  # 本机无Chrome，用Edge内核
    co.set_local_port(9333)                      # 独立实例，不碰用户浏览器
    co.set_user_data_path(str(ROOT / "dp_data")) # 登录态持久化
    co.headless(headless)
    return ChromiumPage(co)

def fill():
    cards = sorted((ROOT / "assets/xhs_v2").glob("卡*.png"))
    # 读当前要发的稿（默认取最新生成的正典正文）
    BODY_FILE = ROOT / "docs/小红书发布包/先查能不能输_小红书正文.txt"
    body = BODY_FILE.read_text(encoding="utf-8").split("#职业规划")[0].rstrip()
    title = "我算了个8分的机会差点全押，后来一道线拦住了我"
    tags = ["职业规划", "求职", "决策方法", "裸辞", "跳槽", "应届生", "实习"]
    if len(cards) != 5:
        sys.exit(f"卡片不足5张: {[c.name for c in cards]}")

    page = new_page()
    page.get(PUB_URL)
    page.wait(3)
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

    # 3. 正文（tiptap ProseMirror）
    ed = page.ele('css:[contenteditable="true"]', timeout=15)
    if not ed:
        sys.exit("正文编辑器未出现")
    ed.click()
    page.actions.key_down("CTRL").key_down("a").key_up("a").key_up("CTRL")
    ed.input(body, clear=True)
    print(f"[3/5] 正文完成({len(body)}字)")

    # 4. 话题：末尾输入 " #tag" → 弹层点选
    for tag in tags:
        ed.input(f" #{tag}")
        page.wait(1.5)
        item = page.ele(f'text={tag}', timeout=5)
        if item:
            item.click()
            print(f"[4/5] 话题 #{tag} ✓", end=" ")
        else:
            print(f"[4/5] 话题 #{tag} 弹层未出现，手动检查", end=" ")
    print()

    # 5. 停在发布键
    btn = page.ele('text=发布笔记')
    print("[5/5] 预填完成。核验后自行点击「发布笔记」。")
    print("台账: python tools/dispatcher.py ledger confirm 康复专业坑不坑续篇 --status published --ref <链接>")

def stats():
    page = new_page()
    page.get("https://creator.xiaohongshu.com/publish/noteManage?source=official")
    print(page.html[:0] or "浏览器已打开笔记管理页，抄数后回填：")
    print("  python tools/dispatcher.py metric 小红书 <标题> 曝光 <n> ...")

if __name__ == "__main__":
    fill() if "--stats" not in sys.argv else stats()
