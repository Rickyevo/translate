"""Before/after sheets: stage-1 direction B cells vs the refined panel.
Run from prototype/:  python scripts/compare_sheet.py"""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

S2 = Path(__file__).resolve().parents[2] / 'screenshots' / 'stage2'
IDS = ['short', 'long', 'loading', 'partial', 'failed', 'offline', 'localOnly', 'auth', 'paused', 'hover', 'hoverFail', 'alt', 'flash']
TITLES = {'short': 'Short candidates', 'long': 'Long translation', 'loading': 'Loading', 'partial': 'Partially complete',
          'failed': 'Service unreachable', 'offline': 'Offline', 'localOnly': 'Local-only mode', 'auth': 'Key rejected',
          'paused': 'Paused', 'hover': 'Hover → full text', 'hoverFail': 'Hover a failure', 'alt': 'Alt held', 'flash': 'Inserted'}
bold = ImageFont.truetype(r'C:\Windows\Fonts\segoeuib.ttf', 15)
reg = ImageFont.truetype(r'C:\Windows\Fonts\segoeui.ttf', 13)
for theme in ['light', 'dark']:
    bg, fg = ((250, 250, 249), (30, 30, 30)) if theme == 'light' else ((22, 22, 24), (235, 235, 235))
    rows = [(i, Image.open(S2 / 'before' / f'b-{i}-{theme}.png'), Image.open(S2 / 'compare' / 'after' / f'{i}-{theme}.png')) for i in IDS]
    ca, cb = max(r[1].width for r in rows), max(r[2].width for r in rows)
    im = Image.new('RGB', (180 + ca + 24 + cb + 32, 60 + sum(max(a.height, b.height) + 20 for _, a, b in rows)), bg)
    d = ImageDraw.Draw(im)
    d.text((180, 20), 'Before (stage 1, B)', font=bold, fill=fg)
    d.text((180 + ca + 24, 20), 'After (refined)', font=bold, fill=fg)
    y = 60
    for i, a, b in rows:
        d.text((20, y + 6), TITLES[i], font=reg, fill=fg)
        im.paste(a, (180, y))
        im.paste(b, (180 + ca + 24, y))
        y += max(a.height, b.height) + 20
    im.save(S2 / 'compare' / f'before-after-{theme}.png')
    print(theme, im.size)
