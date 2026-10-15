"""Builds the final app icon set for the selected concept (Overlap).
Output: ../assets/icons/app/ — translate.ico (exact hinted bitmaps per size), PNGs, SVGs, tray glyphs.
Run from prototype/ after export_icons.mjs:  python scripts/build_ico.py"""
from pathlib import Path
import shutil
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / 'assets' / 'icons' / 'concepts' / 'overlap'
OUT = ROOT / 'assets' / 'icons' / 'app'
OUT.mkdir(parents=True, exist_ok=True)
SIZES = [16, 20, 24, 32, 40, 48, 64, 256]

imgs = {s: Image.open(SRC / f'app-{s}.png').convert('RGBA') for s in SIZES}
for s, im in imgs.items():
    assert im.size == (s, s), (s, im.size)
    im.save(OUT / f'app-{s}.png')
# Largest first; Pillow writes each appended bitmap as-is when its size is listed.
imgs[256].save(OUT / 'translate.ico', format='ICO', sizes=[(s, s) for s in SIZES], append_images=[imgs[s] for s in SIZES if s != 256])
for name in ['app.svg', 'app-small.svg', 'glyph.svg']:
    shutil.copy(SRC / name, OUT / name)
for s in [16, 20, 24, 32]:
    for c in ['white', 'black']:
        shutil.copy(SRC / f'tray-{s}-{c}.png', OUT / f'glyph-{s}-{c}.png')

# Verify: every size present, and the 16 px frame is the hinted drawing (not a downscale of 256).
ico = Image.open(OUT / 'translate.ico')
found = sorted(ico.info.get('sizes', set()))
ico.size = (16, 16)
same16 = ico.convert('RGBA').tobytes() == imgs[16].tobytes()
print('sizes in ico:', found)
print('16 px frame is the hinted bitmap:', same16)
