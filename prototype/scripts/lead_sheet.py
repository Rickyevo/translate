"""Contact sheet of the lead-preview placement cases (from lead_shots.mjs).
Run from prototype/:  python scripts/lead_sheet.py"""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

D = Path(__file__).resolve().parents[2] / 'screenshots' / 'stage2' / 'lead-preview'
CASES = [
    ('1-normal', 'Normal: below the panel (outer side)'),
    ('2-bottom-edge', 'Bottom edge: stack flips up, preview above'),
    ('3-bottom-right', 'Bottom-right: above, slid inside the right edge'),
    ('4-small-display-beside', 'Small display: outer too short, so beside (left)'),
    ('5-very-small-scroll', 'Very small: best fit, height-limited, scrolls'),
    ('8-cramped-overlay-on-request', 'Cramped: nothing fits, so overlay on Alt+`'),
]
bold = ImageFont.truetype(r'C:\Windows\Fonts\segoeuib.ttf', 20)
W, H, S = 1140, 816, 0.5
tw, th = int(W * S), int(H * S)
sheet = Image.new('RGB', (2 * tw + 60, 3 * (th + 50) + 20), (250, 250, 249))
d = ImageDraw.Draw(sheet)
for i, (name, title) in enumerate(CASES):
    x, y = 20 + (i % 2) * (tw + 20), 20 + (i // 2) * (th + 50)
    d.text((x, y), title, font=bold, fill=(30, 30, 30))
    sheet.paste(Image.open(D / f'{name}.png').convert('RGB').resize((tw, th), Image.LANCZOS), (x, y + 32))
sheet.save(D / 'placement-sheet.png')
print(sheet.size)
