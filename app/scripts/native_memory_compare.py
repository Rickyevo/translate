"""Compare original and experimental packaged backends without desktop input."""
from __future__ import annotations

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
import uuid

parser = argparse.ArgumentParser()
parser.add_argument('--pilot', action='store_true')
parser.add_argument('--baseline', type=Path, required=True,
                    help='Extracted baseline release folder, downloaded separately from GitHub')
args = parser.parse_args()
root = Path(__file__).resolve().parents[2]
builds = [('baseline', args.baseline.resolve()),
          ('optimized', root / 'release/Translate-0.2.4-win-x64')]
for variant, directory in builds:
    if not (directory / 'resources/python/TranslateEngine.exe').is_file():
        parser.error(f'{variant} release is missing its bundled engine: {directory}')
run_id = uuid.uuid4().hex[:8]
scratch = root / '.cache' / 'memory-endurance' / run_id
scratch.mkdir(parents=True)
output = root / 'measurements' / 'native-memory-paired-20261018.json'

class Handler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'
    def log_message(self, *a):
        pass
    def handle(self):
        try:
            super().handle()
        except (ConnectionResetError, BrokenPipeError):
            pass  # workers close their keep-alive connections at shutdown
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        texts = json.loads(body['messages'][1]['content'])
        translations = {key: 'fixture-' + hashlib.sha256(value.encode()).hexdigest()[:12]
                        for key, value in texts.items()}
        time.sleep(.03)
        data = json.dumps({'choices': [{'message': {'content': json.dumps(translations)}}]}).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
threading.Thread(target=server.serve_forever, daemon=True).start()
endpoint = f'http://127.0.0.1:{server.server_address[1]}'
records = []
processes = []
readers = []
lock = threading.Lock()

def read(process, variant):
    for line in process.stdout:
        try:
            row = json.loads(line)
        except ValueError:
            continue
        with lock:
            records.append(row)
            output.write_text(json.dumps({'run_id': run_id, 'pilot': args.pilot, 'records': records},
                                         ensure_ascii=False, indent=2), encoding='utf-8')
        if row['type'] in ('ready', 'summary') or row.get('phase', '').endswith(('_start', '_end')):
            print(json.dumps(row), flush=True)

try:
    for variant, directory in builds:
        engine = directory / 'resources/python/TranslateEngine.exe'
        command = [str(engine), '-B', '-u', str(root/'backend/tools/native_memory_worker.py'),
                   '--variant', variant, '--endpoint', endpoint,
                   '--transport', 'frida' if variant=='baseline' else 'native',
                   '--fixture',str(root/'.cache/feasibility-bin/feasibility_fixture.exe'),
                   '--data', str(scratch/variant)]
        if args.pilot:
            command.append('--pilot')
        stderr = open(scratch/(variant+'.stderr.log'), 'w', encoding='utf-8')
        process = subprocess.Popen(command, cwd=root, stdout=subprocess.PIPE, stderr=stderr,
                                   text=True, encoding='utf-8',
                                   env={**os.environ, 'TRANSLATE_SECRETS': 'memory', 'TRANSLATE_NATIVE_CACHE':str(root/'.cache/native-runtime')},
                                   creationflags=0x08000000)
        processes.append((variant, process, stderr))
        reader = threading.Thread(target=read, args=(process,variant), daemon=True)
        reader.start()
        readers.append(reader)
    failed = False
    for variant, process, stderr in processes:
        code = process.wait(timeout=120 if args.pilot else 780)
        stderr.close()
        if code:
            failed = True
            print(variant + ' failed: ' + (scratch/(variant+'.stderr.log')).read_text(encoding='utf-8')[-3000:], flush=True)
    for reader in readers:
        reader.join(10)
    summaries = [row for row in records if row['type']=='summary']
    if len(summaries)!=2 or any(row['failed_rows'] or row['observer_errors'] for row in summaries):
        failed = True
    print(json.dumps({'output':str(output),'success':not failed,'scratch':str(scratch)}),flush=True)
    if failed:
        sys.exit(1)
finally:
    for _,process,stderr in processes:
        if process.poll() is None:
            process.terminate()
            process.wait(5)
        if not stderr.closed:
            stderr.close()
    server.shutdown()
    server.server_close()
