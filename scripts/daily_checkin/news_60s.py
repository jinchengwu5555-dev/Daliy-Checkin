import requests

url = 'https://60s.viki.moe/v2/60s?encoding=text'
resp = requests.get(url)

lines = resp.text.split('\n')

# 分离标题行（第一行）、新闻条目、结尾【微语】
title = ''
news = []
footer = ''

for line in lines:
    stripped = line.strip()
    if not stripped:
        continue
    if stripped.startswith('每天'):
        title = stripped
    elif stripped.startswith('【'):
        footer = stripped
    else:
        news.append(stripped)

half = len(news) // 2
content1 = '\n'.join(news[:half])
content2 = '\n'.join(news[half:])

print(title)
print(content1)
print('---')
print(content2)
print(footer)