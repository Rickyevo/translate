"""Select the content-versioned observer built by MSVC; used only during builds."""
import hashlib
import json
from pathlib import Path
import sys

source, directory = map(Path, sys.argv[1:])
data = source.read_bytes()
name = 'TranslateObserver-' + hashlib.sha256(data).hexdigest()[:16] + '.dll'
target = directory / name
if not target.exists():
    target.write_bytes(data)
if target.read_bytes() != data:
    raise RuntimeError('Observer artifact does not match its content hash')
(directory / 'manifest.json').write_text(json.dumps({'observer': name}), encoding='utf-8')
