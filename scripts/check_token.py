import os
import urllib.request

path = os.path.join(os.path.dirname(__file__), '..', '.env')
path = os.path.abspath(path)
if not os.path.exists(path):
    print('.env not found at', path)
    raise SystemExit(1)

with open(path, 'r', encoding='utf-8') as f:
    token = None
    for line in f:
        if line.strip().startswith('BOT_TOKEN='):
            token = line.strip().split('=',1)[1]
            break
    if not token:
        print('BOT_TOKEN not found in .env')
        raise SystemExit(1)

url = f'https://api.telegram.org/bot{token}/getMe'
try:
    with urllib.request.urlopen(url, timeout=10) as resp:
        data = resp.read(4000).decode('utf-8', errors='ignore')
        print('HTTP', resp.status)
        print(data)
except Exception as e:
    import traceback
    traceback.print_exc()
    raise
