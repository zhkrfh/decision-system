# -*- coding: utf-8 -*-
"""母版md -> 公众号html（品牌样式）。用法: python md2html.py <input.md> <output.html>"""
import re, sys, html as H

def esc(s):
    s = H.escape(s, quote=False)
    for a, b in [('×', '&#215;'), ('±', '&#177;'), ('≤', '&#8804;'), ('−', '&#8722;'), ('÷', '&#247;')]:
        s = s.replace(a, b)
    return s

def inline(s):
    s = esc(s)
    s = re.sub(r'\*\*(.+?)\*\*', r'<strong style="color:#1F5C4A;">\1</strong>', s)
    s = re.sub(r'(?<!\*)\*([^*]+)\*(?!\*)', r'<em>\1</em>', s)
    return s

P_ST = 'style="margin:0 0 14px;font-size:15px;line-height:1.9;"'
SEC = 'style="margin:0 0 20px;"'

src = open(sys.argv[1], encoding='utf-8').read()
out, state = [], None  # state: None|'ul'|'ol'

def close():
    global state
    if state == 'ul': out.append('</ul>')
    elif state == 'ol': out.append('</ol>')
    state = None

for raw in src.split('\n'):
    line = raw.rstrip()
    if not line.strip():
        close(); continue
    if line.startswith('# '):
        close(); continue  # 标题由后台字段承载
    if line.startswith('> '):
        close()
        out.append(f'<p style="margin:0 0 14px;padding:10px 14px;background:#F7F7F2;border-left:3px solid #1F5C4A;font-size:14px;color:#555;">{inline(line[2:])}</p>')
    elif line.startswith('## '):
        close()
        # 分节标题：用带 margin 的 <p> 承载（公众号编辑器对 section 支持不佳）
        # 修：原实现连续 append 后只 pop 一次，导致标题重复输出两次
        out.append(f'<p style="margin:22px 0 10px;"><strong style="color:#1F5C4A;font-size:17px;">{inline(line[3:])}</strong></p>')
        state = 'sec'
    elif line.startswith('### '):
        close()
        out.append(f'<p style="margin:0 0 10px;"><strong style="color:#1F5C4A;">{inline(line[4:])}</strong></p>')
    elif re.match(r'^- ', line):
        if state == 'sec':
            out.append('</p>'); state = None
        if state != 'ul':
            close(); out.append('<ul style="margin:0 0 14px;padding-left:22px;">'); state = 'ul'
        out.append(f'<li style="font-size:15px;line-height:1.9;margin:0 0 6px;">{inline(line[2:])}</li>')
    elif re.match(r'^\d+\. ', line):
        if state == 'sec':
            out.append('</p>'); state = None
        if state != 'ol':
            close(); out.append('<ol style="margin:0 0 14px;padding-left:22px;">'); state = 'ol'
        out.append(f'<li style="font-size:15px;line-height:1.9;margin:0 0 6px;">{inline(re.sub(r"^\\d+\\. ", "", line))}</li>')
    elif line.strip() == '---':
        close()
        if state == 'sec': out.append('</p>'); state = None
        out.append('<hr style="border:none;border-top:1px solid #DDD;margin:18px 0;"/>')
    else:
        if state == 'ul' or state == 'ol': close()
        if state == 'sec':
            out.append(f'<p {P_ST}>{inline(line)}</p>')
        else:
            out.append(f'<p {P_ST}>{inline(line)}</p>')
close()
if state == 'sec': out.append('</section>')

body = '\n'.join(out)
body = body.replace('</section>', '')
# 在每个新 <section 前补闭合：所有 section 平铺，开头补一个 section 开标签
body = re.sub(r'<section ', '</p>\n<section ', body, count=0) if False else body
html_doc = '<div style="max-width:578px;margin:0 auto;">\n' + body + '\n</div>'
# 清理：未闭合 section 处理——把所有 <section ...> 替换为 </p><p ...>标题样式
html_doc = re.sub(r'<section style="margin:0 0 20px;"><p style="margin:0 0 10px;">(<strong[^>]*>[^<]*</strong>)</p>',
                  r'<p style="margin:22px 0 10px;">\1</p>', html_doc)
open(sys.argv[2], 'w', encoding='utf-8').write(html_doc)
print('written', sys.argv[2], len(html_doc))
