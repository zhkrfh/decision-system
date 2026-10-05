# -*- coding: utf-8 -*-
from PIL import Image, ImageDraw, ImageFont
import os
OUT=r"E:\Documents\lingxi-claw\20261002-14-24-38-883\正典仓库\assets\xhs"
os.makedirs(OUT,exist_ok=True)
GREEN=(31,92,74); GRID=(36,100,82); AMBER=(240,173,0); WHITE=(255,255,255); CREAM=(245,241,232); DARK=(42,54,48)
fd="C:/Windows/Fonts/msyhbd.ttc"; fr="C:/Windows/Fonts/msyh.ttc"
W,H=1080,1440
def F(sz,bold=True): return ImageFont.truetype(fd if bold else fr,sz)
def base(green=True):
    im=Image.new("RGB",(W,H),GREEN if green else CREAM); d=ImageDraw.Draw(im)
    g=GRID if green else (221,214,200)
    for x in range(0,W,90): d.line([(x,0),(x,H)],fill=g)
    for y in range(0,H,90): d.line([(0,y),(W,y)],fill=g)
    return im,d
# 卡1 首图
im,d=base()
d.rounded_rectangle([70,80,330,140],radius=14,fill=AMBER)
tb=d.textbbox((0,0),"案例 01",font=F(38)); d.text((200-(tb[2]-tb[0])//2,88),"案例 01",font=F(38),fill=(122,80,0))
d.text((70,220),"一份",font=F(72),fill=WHITE)
d.text((70,320),"1.12 分",font=F(170),fill=AMBER)
d.text((70,520),"的 offer",font=F(110),fill=WHITE)
d.line([72,680,320,690],fill=AMBER,width=10)
d.text((70,720),"境外银行客户营销岗",font=F(52),fill=WHITE)
d.text((70,800),"我用一道乘减法，替直觉记了账",font=F(40,False),fill=(214,228,221))
im.save(f"{OUT}/卡1_首图.png"); print("c1 ok")
# 卡2 打分表
im,d=base()
d.text((70,80),"五个数，每个打 1-10 分",font=F(58),fill=WHITE)
rows=[("p  成功率","6.8","能到想要状态的概率，先除以1.2"),
      ("G  上行收益","8","做成了能带走什么"),
      ("C  下行成本","7.9","失败的代价，含机会成本"),
      ("R  可逆性","5.1","中途停下，损失多少"),
      ("L  复利性","7","带得走的资产会自己增值")]
y=240
for name,val,note in rows:
    d.rounded_rectangle([70,y,1010,y+180],radius=20,fill=WHITE)
    d.text((100,y+30),name,font=F(44),fill=DARK)
    d.text((820,y+20),val,font=F(72),fill=GREEN)
    d.text((100,y+110),note,font=F(30,False),fill=(110,120,114))
    y+=210
d.text((70,y+10),"打分打在事上，不打在情绪上",font=F(38),fill=AMBER)
im.save(f"{OUT}/卡2_五个数字.png"); print("c2 ok")
# 卡3 算式
im,d=base()
d.text((70,100),"然后做一道乘减法",font=F(54),fill=WHITE)
d.rounded_rectangle([70,230,1010,420],radius=24,fill=WHITE)
d.text((140,280),"S = p×G - (1-p)×C",font=F(64),fill=GREEN)
d.text((140,560),"直觉版：",font=F(44,False),fill=(214,228,221))
d.text((140,640),"0.68×8 - 0.32×7.9 = 2.91",font=F(56),fill=WHITE)
d.text((140,790),"先除以 1.2 再算：",font=F(44,False),fill=(214,228,221))
d.text((140,870),"0.567×8 - 0.433×7.9 = 1.12",font=F(56),fill=AMBER)
d.text((140,1060),"掉掉的全是幻觉的溢价",font=F(48),fill=WHITE)
im.save(f"{OUT}/卡3_一道乘减法.png"); print("c3 ok")
# 卡4 刻度
im,d=base(False)
d.text((70,100),"1.12 分，落在哪一档？",font=F(58),fill=DARK)
d.rounded_rectangle([70,260,1010,560],radius=24,outline=DARK,width=4)
d.rectangle([280,262,560,558],fill=(232,224,205))
d.rectangle([560,262,1008,558],fill=GREEN)
d.text((175,380),"不打",font=F(52),fill=(150,150,140))
d.text((380,380),"持有",font=F(52),fill=(160,130,40))
d.text((690,380),"全力投入",font=F(52),fill=WHITE)
d.line([516,230,516,590],fill=AMBER,width=12)
d.ellipse([494,208,538,252],fill=AMBER)
d.text((430,640),"1.12",font=F(90),fill=AMBER)
d.text((70,820),"分数没到，就不该把生活全押上去。",font=F(44),fill=DARK)
d.text((70,900),"投了，但按兵不动，把主力时间",font=F(44),fill=DARK)
d.text((70,980),"投进别的地方。",font=F(44),fill=DARK)
d.text((70,1150),"误差带正负1.5：扣掉它仍为正，才配得上全力投入。",font=F(32,False),fill=(120,130,124))
im.save(f"{OUT}/卡4_刻度.png"); print("c4 ok")
# 卡5 边界声明
im,d=base()
d.text((70,100),"丑话说在前面",font=F(64),fill=WHITE)
lines=["它治好过我一次：让'我一定能行'","变成一张写着 0.567 的纸。","","但它不是万能公式——","分数决定档位，复核代替信仰；","两年为期，证据说话。","","个人方法记录，不构成任何","投资或求职建议。"]
y=280
for t in lines:
    if t: d.text((70,y),t,font=F(44),fill=WHITE)
    y+=95
d.text((70,1240),"全网同名 · 方法连载中",font=F(36,False),fill=AMBER)
im.save(f"{OUT}/卡5_边界声明.png"); print("c5 ok")
print("ALL DONE")
