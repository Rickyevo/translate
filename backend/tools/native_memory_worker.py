"""Paired real-pipe native/Frida memory worker, launched with a packaged Python runtime.

All input is synthetic. Frida attaches only to this worker's own child. A real
UIA observer discards events; only counts, sizes and timing statistics leave the
worker. The coordinator supplies a localhost translation service and scratch data.
"""
from __future__ import annotations

import argparse
import ctypes
from ctypes import wintypes as wt
import json
from pathlib import Path
import queue
import statistics
import subprocess
import sys
import threading
import time

parser = argparse.ArgumentParser()
parser.add_argument('--variant', required=True)
parser.add_argument('--endpoint', required=True)
parser.add_argument('--data', required=True)
parser.add_argument('--pilot', action='store_true')
parser.add_argument('--transport',choices=['frida','native'],required=True)
parser.add_argument('--fixture',required=True)
args = parser.parse_args()
assert args.endpoint.startswith('http://127.0.0.1:')

class Counters(ctypes.Structure):
    _fields_ = [('cb', wt.DWORD), ('faults', wt.DWORD)] + [
        (name, ctypes.c_size_t) for name in (
            'peak_ws', 'ws', 'peak_paged', 'paged', 'peak_nonpaged',
            'nonpaged', 'pagefile', 'peak_pagefile', 'private')]

kernel = ctypes.WinDLL('kernel32')
kernel.GetCurrentProcess.restype = wt.HANDLE
psapi = ctypes.WinDLL('psapi')
psapi.GetProcessMemoryInfo.argtypes = [wt.HANDLE, ctypes.POINTER(Counters), wt.DWORD]

def emit(record):
    print(json.dumps({'variant': args.variant, **record}), flush=True)

sys.argv.append('--translator=live')
from translate_backend.__main__ import Backend
from translate_backend import protocol
from translate_backend.wetype import encode
from translate_backend.mspinyin.observer import Observer, _load_uia
from translate_backend.translate.http import _ssl

class Sink:
    def write(self, data):
        return len(data)
    def flush(self):
        pass

protocol._stdout = Sink()
backend = Backend(True, source='wetype-replay')
backend.handle({'type': 'config.set', 'config': {
    'ime': 'auto', 'target': 'en', 'count': 5, 'localOnly': False,
    'localDict': True, 'provider': 'custom', 'dataDir': args.data,
    'timeout': 2, 'services': {'custom': {
        'endpoint': args.endpoint + '/v1', 'model': 'memory-fixture',
        'protocol': 'openai', 'auth': 'none'}}}})
backend.handle({'type': 'debug.wetype.connection', 'state': 'connected', 'epoch': 1})
backend.handle({'type': 'debug.wetype.window',
                'rect': {'x': 100, 'y': 200, 'w': 600, 'h': 43},
                'foreground': {'hwnd': 1, 'pid': 4242, 'exe': 'synthetic.exe'}})

# Similar index cardinality to the inspected real profile, using public dictionary
# headwords and synthetic translations. No user profile is opened.
dictionary = backend.pipeline.dictionary
for line in dictionary._map()[:].splitlines():
    word = line.split(b'\t', 1)[0].decode('utf-8')
    if 1 <= len(word) <= 4:
        backend.pipeline.cache.put('en', word, 'fixture')
    if len(backend.pipeline.cache._disk) >= 3559:
        break
_ssl()  # load the normal HTTPS certificate context without external requests

stop = threading.Event()
observer_ready = threading.Event()
observer_errors = []
def observe(event):
    if event.get('kind') == 'connection':
        if event.get('state') == 'connected':
            observer_ready.set()
        elif event.get('state') == 'failed':
            observer_errors.append(event.get('code'))
observer = Observer(observe, stop)
observer_thread = threading.Thread(target=observer.run, daemon=True)
observer_thread.start()
if not observer_ready.wait(10):
    raise RuntimeError('UIA observer failed: ' + repr(observer_errors))

# A second apartment performs repeatable cached reads, independent of real typing.
comtypes, U = _load_uia()
comtypes.CoInitializeEx(0)
uia = comtypes.CoCreateInstance(U.CUIAutomation._reg_clsid_, interface=U.IUIAutomation)
root_element = uia.GetRootElement()
condition = uia.CreatePropertyCondition(30002, root_element.CurrentProcessId)
read_cache = uia.CreateCacheRequest()
read_cache.AddProperty(U.UIA_NamePropertyId)

phases = [('warmup', 3), ('typing_1', 25), ('idle_1', 10), ('typing_2', 25), ('idle_2', 10)]
child = subprocess.Popen([args.fixture],stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True,creationflags=0x08000000)
assert json.loads(child.stdout.readline())['pid']==child.pid
native = None
native_stop = threading.Event()
native_thread = None
pending_sequences = queue.Queue()
write_times = []
session = None
candidate_times = []
dispatch_times = []
translation_times = []
uia_times = []
phase_stats = []
sent_times = {}
new_generations = 0
settled_generations = 0
failed_rows = 0
input_count = 0
group = 0
sequence = 0
started = time.perf_counter()
current_sent = None
generation_started = {}
generation_settled = set()
previous_generation = 0

def quantiles(values):
    if not values:
        return None
    ordered = sorted(values)
    return {'n': len(values), 'median_ms': round(statistics.median(values), 4),
            'p95_ms': round(ordered[int((len(ordered)-1)*.95)], 4),
            'max_ms': round(ordered[-1], 4)}

def snapshot(phase):
    counters = Counters()
    counters.cb = ctypes.sizeof(counters)
    if not psapi.GetProcessMemoryInfo(kernel.GetCurrentProcess(), ctypes.byref(counters), counters.cb):
        raise ctypes.WinError()
    emit({'type': 'sample', 'phase': phase, 'elapsed_s': round(time.perf_counter()-started, 2),
          'private_mb': round(counters.private/2**20, 3), 'ws_mb': round(counters.ws/2**20, 3),
          'cpu_s': round(time.process_time(), 4), 'inputs': input_count,
          'generations': new_generations, 'settled': settled_generations,
          'failed_rows': failed_rows, 'event_queue': backend.events.qsize(),
          'jobs': backend.pipeline._jobs.qsize(), 'scheduled': len(backend.scheduler._heap),
          'cache_memory': len(backend.pipeline.cache._mem),
          'cache_disk': len(backend.pipeline.cache._disk)})

def handle(event):
    global previous_generation, new_generations, settled_generations, failed_rows
    begin = time.perf_counter()
    if event.get('type') == '_source':
        source_event = event['event']
        sent = sent_times.pop(source_event.pop('_sequence', -1), None)
        backend.source.accept(source_event)
        candidate = backend.source.current
        if candidate and candidate.gen != previous_generation:
            previous_generation = candidate.gen
            new_generations += 1
            generation_started.clear()
            generation_settled.clear()
            if sent is not None:
                candidate_times.append((time.perf_counter()-sent)*1000)
                generation_started[candidate.gen] = sent
    elif event.get('type') in ('_svc_flush', '_svc_result', '_svc_hedge', '_cache_save'):
        backend.pipeline.accept(event)
    else:
        backend.handle(event)
    dispatch_times.append((time.perf_counter()-begin)*1000)
    candidate = backend.source.current
    if candidate and candidate.gen not in generation_settled:
        if all(item.state == 'done' and item.source in ('cache', 'ai') for item in candidate.items):
            generation_settled.add(candidate.gen)
            settled_generations += 1
            if candidate.gen in generation_started:
                translation_times.append((time.perf_counter()-generation_started[candidate.gen])*1000)
        failed_rows += sum(item.state == 'failed' for item in candidate.items)

def transmit(data):
    global sequence
    sequence += 1
    sent_times[sequence] = time.perf_counter()
    pending_sequences.put(sequence)
    child.stdin.write('write 1 '+data.hex()+'\n');child.stdin.flush()
    result = json.loads(child.stdout.readline())
    assert not result['errors'] and result['delivered']==len(data)
    write_times.append(result['p95_us'])

def on_message(message, data):
    if message.get('type') == 'send' and data:
        backend._post_source({'kind': 'bytes', 'epoch': 1, 'handle': 'synthetic',
                              'data': data, '_sequence': pending_sequences.get_nowait()})

try:
    if args.transport=='frida':
        import frida
        session = frida.attach(child.pid)
        agent = Path(sys.modules['translate_backend.__main__'].__file__).parent/'wetype/agent.js'
        script = session.create_script(agent.read_text(encoding='utf8'))
        script.on('message',on_message);script.load()
    else:
        from translate_backend.wetype.native_transport import Connection
        native = Connection(child.pid)
        def post(event):
            if event['kind']=='bytes':event['_sequence']=pending_sequences.get_nowait()
            backend._post_source(event)
        def drain():
            while not native_stop.is_set():
                if not native.poll(post,1):native.wait(20)
        native_thread=threading.Thread(target=drain);native_thread.start()
    emit({'type': 'ready', 'backend_path': sys.modules['translate_backend.__main__'].__file__,
          'duration_s': sum(seconds for _, seconds in phases)})
    next_sample = time.perf_counter()
    next_read = time.perf_counter()
    for phase, seconds in phases:
        phase_start = time.perf_counter()
        phase_cpu = time.process_time()
        end = phase_start + seconds
        step = 0
        next_input = phase_start
        input_before = input_count
        completed_before = settled_generations
        snapshot(phase + '_start')
        while time.perf_counter() < end:
            now = time.perf_counter()
            if phase.startswith('typing') and now >= next_input:
                if step < 5:
                    words = ['时间'] + [f'合成测试{group}-{step}-{n}' for n in range(4)]
                    transmit(encode.composition('ni' + 'a'*step) + encode.candidates(words))
                    input_count += 1
                    step += 1
                    next_input += .45 if step == 5 else .12
                else:
                    transmit(encode.commit())
                    group += 1
                    step = 0
                    next_input += .12
            if now >= next_read:
                tick = time.perf_counter()
                root_element.CurrentAutomationId
                root_element.CurrentProcessId
                root_element.CurrentBoundingRectangle
                root_element.CurrentIsOffscreen
                matches = root_element.FindAllBuildCache(1, condition, read_cache)
                assert matches.Length == 1
                matches.GetElement(0).CachedName
                uia_times.append((time.perf_counter()-tick)*1000)
                next_read = now + 1
            if now >= next_sample:
                snapshot(phase)
                next_sample = now + 5
            deadlines = [end, next_read, next_sample]
            if phase.startswith('typing'):
                deadlines.append(next_input)
            timeout = max(0, min(.05, min(deadlines)-time.perf_counter()))
            try:
                event = backend.events.get(timeout=timeout)
            except queue.Empty:
                continue
            handle(event)
        # End the composition without allowing a real keystroke out of the process.
        if phase.startswith('typing'):
            transmit(encode.commit())
        snapshot(phase + '_end')
        phase_stats.append({'phase': phase, 'elapsed_s': round(time.perf_counter()-phase_start, 3),
                            'cpu_core_percent': round((time.process_time()-phase_cpu)/seconds*100, 3),
                            'inputs': input_count-input_before,
                            'settled': settled_generations-completed_before})
    emit({'type': 'summary', 'phases': phase_stats, 'candidate': quantiles(candidate_times),
          'dispatch': quantiles(dispatch_times), 'translation': quantiles(translation_times),
          'uia': quantiles(uia_times), 'failed_rows': failed_rows,
          'observer_errors': observer_errors, 'events': backend.events.qsize(),
          'jobs': backend.pipeline._jobs.qsize(), 'write_call':quantiles([v/1000 for v in write_times]),'inputs': input_count,
          'generations': new_generations, 'settled': settled_generations})
finally:
    stop.set()
    observer._wake.set()
    observer_thread.join(3)
    if native:
        native_stop.set();native_thread.join(1);native.close()
    if session:
        session.detach()
    child.terminate()
    child.wait()
    backend.source.close()
    backend.pipeline.close()
    backend.scheduler.close()
    comtypes.CoUninitialize()
