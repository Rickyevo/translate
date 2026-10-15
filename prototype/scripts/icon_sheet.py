"""One-page comparison of all icon concepts from the exported PNGs.
Run from prototype/ after export_icons.mjs:  python scripts/icon_sheet.py"""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / 'assets' / 'icons' / 'concepts'
OUT = ROOT / 'screenshots' / 'stage2' / 'icons-sheet.png'
IDS = [('underlay', 'Underlay'), ('refraction', 'Refraction'), ('overlap', 'Overlap'), ('fold', 'Fold')]
APP = [256, 48, 32, 24, 16]
TRAY = [32, 24, 20, 16]
bold = ImageFont.truetype(r'C:\Windows\Fonts\segoeuib.ttf', 18)
reg = ImageFont.truetype(r'C:\Windows\Fonts\segoeui.ttf', 12)
COLW, ROWH = 820, 330
im = Image.new('RGB', (180 + COLW * 2, 50 + ROWH * len(IDS)), (255, 255, 255))
d = ImageDraw.Draw(im)
for ci, (bg, fg, label, tray) in enumerate([((243, 243, 243), (27, 27, 27), 'Light (Windows 11 light)', 'black'), ((32, 32, 32), (255, 255, 255), 'Dark (Windows 11 dark)', 'white')]):
    x0 = 180 + ci * COLW
    d.rectangle([x0, 0, x0 + COLW, im.height], fill=bg)
    d.text((x0 + 20, 16), label, font=reg, fill=fg)
    for ri, (cid, name) in enumerate(IDS):
        y0 = 50 + ri * ROWH
        if ci == 0:
            d.text((20, y0 + 20), f'{ri + 1}  {name}', font=bold, fill=(27, 27, 27))
        x = x0 + 20
        for s in APP:
            ic = Image.open(SRC / cid / f'app-{s}.png').convert('RGBA')
            im.paste(ic, (x, y0 + 20 + 256 - s), ic)
            d.text((x, y0 + 282), str(s), font=reg, fill=fg)
            x += s + 22
        # 16 px magnified ×6, nearest neighbour, to show pixel fit
        z = Image.open(SRC / cid / 'app-16.png').convert('RGBA').resize((96, 96), Image.NEAREST)
        im.paste(z, (x + 6, y0 + 20 + 256 - 96), z)
        d.text((x + 6, y0 + 282), '16 ×6', font=reg, fill=fg)
        x += 96 + 34
        for s in TRAY:
            g = Image.open(SRC / cid / f'tray-{s}-{tray}.png').convert('RGBA')
            im.paste(g, (x, y0 + 20 + 256 - s), g)
            d.text((x, y0 + 300 - 18), str(s), font=reg, fill=fg)
            x += s + 16
        d.text((x - 4 - sum(s + 16 for s in TRAY), y0 + 300), 'tray glyph', font=reg, fill=fg)
im.save(OUT)
print(OUT, im.size)
