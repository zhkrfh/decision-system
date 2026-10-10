# -*- coding: utf-8 -*-
"""wx_push：公众号草稿一键灌稿（封面自动上传）

用法:
    python tools/wx_push.py <html文件> <封面jpg> [标题]
    python tools/wx_push.py <html文件> <封面jpg> [标题] --sched "2026-10-13 20:30"

流程：上传封面拿 media_id → 灌草稿箱 → 校验 → 停手（群发键归作者）
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import wx_api  # noqa: E402
from store import ROOT  # noqa: E402


def upload_thumb(img_path):
    """上传封面图，返回 media_id

    现有 wx_api.post 只支持 JSON，微信封面上传需要 multipart，
    因此这里直接用 requests 调，不改动 wx_api。
    """
    import requests

    img = Path(img_path)
    if not img.exists():
        raise SystemExit(f"封面不存在: {img}")

    t = wx_api.token()
    data = {"media": (img.name, open(img, "rb").read(), "image/jpeg")}
    r = requests.post(
        "https://api.weixin.qq.com/cgi-bin/material/add_material"
        f"?access_token={t}&type=thumb",
        files=data, timeout=60)
    j = r.json()
    if "media_id" not in j:
        raise SystemExit(f"封面上传失败: {j}")
    return j["media_id"]


def push(html_file, cover_file, title=None, scheduled=None):
    html_file = Path(html_file)
    cover_file = Path(cover_file)

    if not html_file.exists():
        raise SystemExit(f"HTML 不存在: {html_file}")

    html = html_file.read_text(encoding="utf-8")
    # 标题：优先传入，否则取文件名
    if not title:
        title = html_file.stem.replace("_", "｜")

    print(f"\n=== 公众号灌稿 ===\n")
    print(f"  标题   {title}")
    print(f"  正文   {html_file.name}  ({len(html)} 字符)")
    print(f"  封面   {cover_file.name}")

    # 1 上传封面
    print("\n  [1/3] 上传封面…")
    thumb = upload_thumb(cover_file)
    print(f"        media_id = {thumb}")
    (ROOT / "thumb_media_id.txt").write_text(thumb, encoding="utf-8")

    # 2 灌草稿箱
    print("\n  [2/3] 灌入草稿箱…")
    media_id = wx_api.draft_add(title, html, thumb)
    if str(media_id).startswith("错误"):
        raise SystemExit(f"  灌稿失败: {media_id}")
    print(f"        草稿 media_id = {media_id}")

    # 3 校验
    print("\n  [3/3] 校验草稿…")
    time.sleep(1)
    t = wx_api.token()
    r = wx_api.post(f"https://api.weixin.qq.com/cgi-bin/draft/count?access_token={t}", {})
    print(f"        草稿总数 = {r.get('total', '未知')}")

    # 存档
    (ROOT / "wx_last_push.json").write_text(json.dumps({
        "title": title, "media_id": media_id, "thumb": thumb,
        "html": str(html_file), "cover": str(cover_file),
        "scheduled": scheduled, "at": time.strftime("%Y-%m-%d %H:%M"),
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n" + "=" * 46)
    print(" 灌稿完成 —— 群发键归你")
    print("=" * 46)
    print(f"\n  下一步：打开 mp.weixin.qq.com → 草稿箱")
    print(f"  找到《{title}》→ 检查排版 → 点群发")
    if scheduled:
        print(f"  或设为定时发布：{scheduled}")
    print()
    return media_id


if __name__ == "__main__":
    a = [x for x in sys.argv[1:] if not x.startswith("--")]
    sched = None
    if "--sched" in sys.argv:
        i = sys.argv.index("--sched")
        sched = sys.argv[i + 1] if len(sys.argv) > i + 1 else None
    if len(a) < 2:
        print(__doc__)
    else:
        push(a[0], a[1], a[2] if len(a) > 2 else None, sched)
