# -*- coding: utf-8 -*-
import os, re, json, requests

env = {}
for line in open('.env', encoding='utf-8'):
    line = line.strip()
    if '=' in line and not line.startswith('#'):
        k, v = line.split('=', 1); env[k] = v

tok = requests.get('https://api.weixin.qq.com/cgi-bin/token',
                   params={'grant_type': 'client_credential',
                           'appid': env['WX_APPID'], 'secret': env['WX_APPSECRET']}).json()['access_token']

MID = 'p_wLbiT8D6v7ycoT6tk1KzIFNNjKj4KWVWn_DqZlcWq-9uEXTwgeT7wil00drlKv'
cur = requests.post('https://api.weixin.qq.com/cgi-bin/draft/get?access_token=' + tok,
                    json={'media_id': MID}).json()
item = cur['news_item'][0]

html = open('docs/素材/公众号素材2_案例01.html', encoding='utf-8').read()
item['content'] = html
item['digest'] = '一道完整的仓位题：52.6怎么算，为何过20才重仓'

r = requests.post('https://api.weixin.qq.com/cgi-bin/draft/update?access_token=' + tok,
                  json={'media_id': MID, 'index': 0, 'articles': item})
print('update:', r.json())

chk = requests.post('https://api.weixin.qq.com/cgi-bin/draft/get?access_token=' + tok,
                    json={'media_id': MID}).json()['news_item'][0]
txt = re.sub(r'<[^>]+>', '', chk['content'])
txt = txt.replace('&gt;', '>').replace('&lt;', '<').replace('&nbsp;', ' ').replace('\ufeff', '')
ok = [kw for kw in ['才敢重仓', '打分误差', '轻仓试错', '按了按钮之后', '反而安静了', '还在长', '第二版', '第六版', '终审判决', 'R×L=35.7'] if kw in txt]
print('核验命中', len(ok), '/10:', ok)
print('digest:', chk['digest'])
print('标题:', chk['title'])
