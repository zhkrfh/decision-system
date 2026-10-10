# -*- coding: utf-8 -*-
"""cover：家族风格封面生成（绿底网格 + 白线岔路 + 琥珀X）

沿用已有封面的视觉语言，保证系列一致性：
- 底色 #1a4a3c 深绿，细网格线
- 右上：白线岔路图形 + 琥珀色 X
- 左上：黄色圆角标签（连载编号）
- 主标题：白色粗体大字
- 副标题：浅绿小字
- 左下：黄色短横线

用法: python cover.py <输出png> <标签> <主标题> <副标题>
"""
import sys
from PIL import Image, ImageDraw, ImageFont

W, H = 900, 383          # 与既有封面同比例
BG = (26, 74, 60)        # 深绿
GRID = (32, 88, 71)      # 网格线（略浅）
WHITE = (240, 244, 241)
LIGHT = (168, 206, 190)  # 副标题浅绿
AMBER = (245, 176, 32)   # 琥珀
TAG_BG = (250, 190, 40)


def cn_font(size, bold=True):
    """找中文字体"""
    cands = [
        "C:/Windows/Fonts/msyhbd.ttc" if bold else "C:/Windows/Fonts/msyh.ttc",
        "C:/Windows/Fonts/simhei.ttf",
        "C:/Windows/Fonts/simsun.ttc",
    ]
    for c in cands:
        try:
            return ImageFont.truetype(c, size)
        except Exception:
            continue
    return ImageFont.load_default()


def draw(out, tag, title, subtitle):
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)

    # 网格
    step = 45
    for x in range(0, W, step):
        d.line([(x, 0), (x, H)], fill=GRID, width=1)
    for y in range(0, H, step):
        d.line([(0, y), (W, y)], fill=GRID, width=1)

    # 右上：白线岔路
    px, py = 640, 58
    d.line([(px, py), (px, 320)], fill=WHITE, width=7)          # 竖干
    d.line([(px, py), (848, py - 22)], fill=WHITE, width=7)      # 上岔
    d.line([(px, py + 46), (838, py + 112)], fill=LIGHT, width=7)  # 下岔（浅绿）
    # 琥珀 X
    d.line([(698, 34), (748, 82)], fill=AMBER, width=11)
    d.line([(748, 34), (698, 82)], fill=AMBER, width=11)

    # 左上黄色标签
    f_tag = cn_font(24)
    tw = d.textlength(tag, font=f_tag)
    d.rounded_rectangle([68, 52, 68 + tw + 40, 96], radius=10, fill=TAG_BG)
    d.text((68 + 20, 60), tag, font=f_tag, fill=BG)

    # 主标题
    f_t = cn_font(52)
    d.text((68, 150), title, font=f_t, fill=WHITE)

    # 副标题
    f_s = cn_font(25)
    d.text((68, 232), subtitle, font=f_s, fill=LIGHT)

    # 左下黄线
    d.rectangle([68, 300, 138, 307], fill=AMBER)

    img.save(out)
    return out


if __name__ == "__main__":
    if len(sys.argv) < 5:
        print(__doc__)
        sys.exit(1)
    p = draw(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4])
    print("written", p)
