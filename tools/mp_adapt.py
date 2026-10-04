# -*- coding: utf-8 -*-
"""多平台互转适配器（一鱼多吃管线）
用法：python mp_adapt.py <master.md> <平台>
平台：xhs（小红书文本卡）/ html（小报童·知识星球等通用富文本）/ all（全部输出到 dist/）
母版约定（master.md）：
  第一行  # 标题
  --- 之后的正文按段落分块；"> " 开头的行视为边界提示框；"## " 为小节标题。
"""
import sys, os, re, hashlib

def parse_master(path):
    lines = open(path, encoding="utf-8").read().splitlines()
    title = next((l[2:].strip() for l in lines if l.startswith("# ")), os.path.basename(path))
    body_lines = lines  # 全文解析；"---" 分隔线视为段落断
    blocks, buf, kind = [], [], None
    for l in body_lines:
        if l.startswith("# "):
            continue  # 主标题不重复进正文
        if l.startswith("> "):
            if buf: blocks.append((kind, "\n".join(buf))); buf=[]
            kind="quote"; buf=[l[2:]]
        elif l.startswith("## "):
            if buf: blocks.append((kind,"\n".join(buf))); buf=[]
            kind="h"; buf=[l[3:]]
        elif not l.strip():
            if buf: blocks.append((kind,"\n".join(buf))); buf=[]; kind=None
        else:
            if kind is None: kind="p"
            buf.append(l)
    if buf: blocks.append((kind or "p","\n".join(buf)))
    return title, blocks

def to_xhs(title, blocks):
    out=[f"{title}"]  # 小红书标题独立字段，正文首行复述
    for k,t in blocks:
        t=t.strip()
        if k=="h": out.append(f"📌 {t}")
        elif k=="quote": out.append(f"⚠️ {t}")
        else: out.append(t)
    txt="\n\n".join(out)
    if len(txt)>1000:  # 小红书正文上限1000字，超则截断并留钩子
        txt=txt[:940].rsplit("。",1)[0]+"。👇 完整算法拆解见公众号「蔵亥喹荣」"
    txt+="\n\n#职业选择 #offer #跳槽 #决策 #职场干货 #个人成长"
    return txt

def esc(s): return s.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
def to_html(title, blocks):
    o=[f'<section style="max-width:100%;font-family:-apple-system,\'Microsoft YaHei\',sans-serif;font-size:16px;color:#2C2C2C;line-height:1.9;">',
       f'<h1 style="font-size:20px;margin:0 0 20px;">{esc(title)}</h1>']
    for k,t in blocks:
        t=esc(t.strip())
        if k=="h": o.append(f'<h2 style="font-size:17px;color:#1F5C4A;margin:24px 0 12px;">{t}</h2>')
        elif k=="quote": o.append(f'<section style="background:#FFF9E6;border-left:4px solid #D4B106;padding:12px 16px;margin:0 0 18px;border-radius:4px;font-size:15px;">{t}</section>')
        else: o.append(f'<p style="margin:0 0 18px;">{t}</p>')
    o.append('<p style="font-size:13px;color:#888;border-top:1px solid #E0E0E0;padding-top:12px;">蔵亥喹荣 · 把能算的算清楚，把算不清的想明白</p></section>')
    return "\n".join(o)

if __name__=="__main__":
    src, plat = sys.argv[1], sys.argv[2]
    title, blocks = parse_master(src)
    stem = os.path.splitext(os.path.basename(src))[0]
    dist = os.path.join(os.path.dirname(os.path.abspath(src)), "dist"); os.makedirs(dist, exist_ok=True)
    outs={}
    if plat in ("xhs","all"): outs[f"{stem}_小红书.txt"]=to_xhs(title,blocks)
    if plat in ("html","all"): outs[f"{stem}_通用.html"]=to_html(title,blocks)
    for name,content in outs.items():
        p=os.path.join(dist,name); open(p,"w",encoding="utf-8").write(content)
        print("OK", p, f"({len(content)}字符)")
