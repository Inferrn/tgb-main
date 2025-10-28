import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
fp = ROOT / 'app' / 'data' / 'ovz.json'
with open(fp, 'r', encoding='utf-8') as f:
    data = json.load(f)

options_scale = data.get('options_scale', [])

mod1 = {q['id']: q for q in data.get('modul_1', [])}
mod2 = {q['id']: q for q in data.get('modul_2', [])}

print('raw modul_1 q3 type:', mod1[3]['type'])
print('raw modul_1 q3 options length:', len(mod1[3].get('options') or []))

lvl0 = mod2[3]['levels'][0]
lvl0_opts = lvl0.get('options')
if isinstance(lvl0_opts, str) and lvl0_opts == 'options_scale':
    lvl0_opts = options_scale

print('modul_2 q3 level[0].options type:', type(lvl0_opts), 'len=', len(lvl0_opts))
print('modul_2 q3 level[0].options first:', lvl0_opts[0])

for qid in [3,4,5,6]:
    q = mod1[qid]
    print(f"modul_1 q{qid} type={q.get('type')} options_len={len(q.get('options') or [])}")
