# -*- coding: utf-8 -*-
"""先查能不能输 · 小红书卡片图（家族风格 5 竖卡）

沿用 assets/xhs 的视觉语言：深绿底 + 网格 + 琥珀强调 + 白色大字
"""
from PIL import Image, ImageDraw, ImageFont
from pathlib import Path

OUT = Path(r"E:\Documents\lingxi-claw\20261002-14-24-38-883\正典仓库\assets\xhs_v2")
OUT.mkdir(parents=True, exist_ok=True)

GREEN = (31, 92, 74)
GRID = (36, 100, 82)
AMBER = (240, 173, 0)
WHITE = (255, 255, 255)
CREAM = (245, 241, 232)
DARK = (42, 54, 48)
SOFT = (214, 228, 221)

FD = "C:/Windows/Fonts/msyhbd.ttc"
FR = "C:/Windows/Fonts/msyh.ttc"
W, H = 1080, 1440


def F(sz, bold=True):
    return ImageFont.truetype(FD if bold else FR, sz)


def base():
    im = Image.new("RGB", (W, H), GREEN)
    d = ImageDraw.Draw(im)
    for x in range(0, W, 90):
        d.line([(x, 0), (x, H)], fill=GRID)
    for y in range(0, H, 90):
        d.line([(0, y), (W, y)], fill=GRID)
    return im, d


def tag(d, text, y=80, x=70):
    tb = d.textbbox((0, 0), text, font=F(38))
    w = tb[2] - tb[0] + 60
    d.rounded_rectangle([x, y, x + w, y + 62], radius=14, fill=AMBER)
    d.text((x + 30, y + 10), text, font=F(38), fill=(122, 80, 0))


# 卡1 首图 —— 反常识钩子
im, d = base()
tag(d, "连载 04")
d.text((70, 230), "我算了个", font=F(76), fill=WHITE)
d.text((70, 340), "8 分", font=F(190), fill=AMBER)
d.text((70, 560), "的机会", font=F(110), fill=WHITE)
d.line([72, 700, 330, 712], fill=AMBER, width=10)
d.text((70, 750), "差点全押", font=F(58), fill=SOFT)
d.text((70, 850), "后来一道线拦住了我", font=F(46), fill=SOFT)
im.save(OUT / "卡1_首图.png")
print("卡1 ok")

# 卡2 转折 —— 那道线是什么
im, d = base()
tag(d, "转折")
d.text((70, 220), "但它有两个", font=F(58), fill=WHITE)
d.text((70, 300), "配套指标", font=F(58), fill=WHITE)
y = 430
for label, val in [("能反悔程度", "3 分"), ("能攒下东西", "3 分")]:
    d.rounded_rectangle([70, y, 1010, y + 150], radius=20, fill=WHITE)
    d.text((110, y + 42), label, font=F(46), fill=DARK)
    d.text((790, y + 32), val, font=F(70), fill=GREEN)
    y += 180
d.text((70, 800), "3 × 3 = 9", font=F(120), fill=AMBER)
d.text((70, 950), "低于警戒线 10", font=F(52), fill=WHITE)
d.text((70, 1030), "总分作废", font=F(66), fill=WHITE)
im.save(OUT / "卡2_转折.png")
print("卡2 ok")

# 卡3 三种局 —— 分类
im, d = base()
tag(d, "三种局")
y = 220
cases = [
    ("能走 攒不下", "亏得起，赚不到大", "试错局 · 轻仓"),
    ("出不来 攒得下", "被套住但有资产", "套牢局 · 长扛"),
    ("出不来 攒不下", "时间换不来东西", "被吞掉 · 别进"),
]
for a, b, c in cases:
    d.rounded_rectangle([70, y, 1010, y + 190], radius=20, fill=WHITE)
    d.text((110, y + 30), a, font=F(46), fill=DARK)
    d.text((110, y + 95), b, font=F(32, False), fill=(110, 120, 114))
    d.text((110, y + 140), c, font=F(38), fill=GREEN)
    y += 215
d.text((70, 900), "第三种里，高分不是好消息", font=F(44, False), fill=SOFT)
d.text((70, 970), "它只是「亏损到账晚一点」", font=F(50), fill=AMBER)
im.save(OUT / "卡3_三种局.png")
print("卡3 ok")

# 卡4 扎心一句
im, d = base()
tag(d, "扎心")
d.text((70, 240), "高分的原因，", font=F(56), fill=WHITE)
d.text((70, 330), "是明面上的好", font=F(56), fill=WHITE)
d.line([72, 440, 330, 450], fill=AMBER, width=8)
d.text((70, 500), "低分的原因，", font=F(56), fill=WHITE)
d.text((70, 590), "在暗处", font=F(80), fill=AMBER)
d.rounded_rectangle([70, 780, 1010, 1000], radius=20, fill=(20, 66, 53))
d.text((110, 830), "它按小时收走", font=F(48), fill=WHITE)
d.text((110, 900), "你的选择权", font=F(60), fill=AMBER)
d.text((70, 1100), "这不是投资，是被吞掉", font=F(46, False), fill=SOFT)
im.save(OUT / "卡4_扎心.png")
print("卡4 ok")

# 卡5 答案 —— 这次直接给
im, d = base()
tag(d, "我的答案")
d.text((70, 240), "那个 8 分的机会", font=F(52), fill=WHITE)
d.text((70, 320), "我最后拿了", font=F(52), fill=WHITE)
d.text((70, 420), "10%", font=F(230), fill=AMBER)
d.line([72, 700, 330, 712], fill=AMBER, width=10)
d.text((70, 760), "不是胆小", font=F(52), fill=WHITE)
d.text((70, 850), "是我在里面看不清", font=F(46, False), fill=SOFT)
d.text((70, 920), "自己什么时候会想走", font=F(46, False), fill=SOFT)
d.rounded_rectangle([70, 1050, 1010, 1200], radius=20, fill=WHITE)
d.text((110, 1090), "先查能不能输，再看分数", font=F(42), fill=DARK)
d.text((110, 1145), "人只在「想要」时出错", font=F(34, False), fill=(110, 120, 114))
im.save(OUT / "卡5_答案.png")
print("卡5 ok")

print(f"\n5 张卡片输出到 {OUT}")
