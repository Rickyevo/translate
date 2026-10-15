"""Capture tool: records everything wetype_server writes to the renderer pipe, plus candidate-window
show/hide/move events, with timestamps — raw material for protocol analysis.

Run from backend/:  python -X utf8 tools/wetype_capture.py SECONDS OUT.jsonl
Read-only: the agent observes WriteFile; nothing in WeType is modified.
"""
from __future__ import annotations

import base64
import ctypes
import ctypes.wintypes as wt
import json
import sys
import threading
import time
from pathlib import Path

import frida
import psutil

BROAD = "--broad" in sys.argv
GATE_HWND = int(next((a.split("=")[1] for a in sys.argv if a.startswith("--only-hwnd=")), "0"))
META_ONLY = "--meta-only" in sys.argv  # privacy: lengths/timings only, never the user's text
AGENT = (Path(__file__).resolve().parents[1] / "translate_backend" / "wetype" / "agent.js").read_text(encoding="utf-8")
u32 = ctypes.windll.user32
u32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))


def main():
    pos = [a for a in sys.argv[1:] if not a.startswith("--")]
    secs = float(pos[0]) if pos else 60
    out = open(pos[1] if len(pos) > 1 else "capture.jsonl", "w", encoding="utf-8")
    lock = threading.Lock()
    t0 = time.perf_counter()

    def rec(obj):
        obj["ts"] = round((time.perf_counter() - t0) * 1000, 2)
        obj["wall"] = time.time()
        with lock:
            out.write(json.dumps(obj, ensure_ascii=False) + "\n")
            out.flush()

    # Only the server: attaching to the renderer (it draws the candidate window) coincided with an
    # elevated prompt on the user's desktop, and it isn't needed — the server is the writer.
    targets = ["wetype_server.exe"]
    scripts = []
    for exe in targets:
        pid = next(p.pid for p in psutil.process_iter(["name"]) if (p.info["name"] or "").lower() == exe)
        session = frida.attach(pid)
        # Broad mode: every pipe whose name contains "wetype" (any channel) instead of only server_for_renderer.
        src = AGENT.replace("const TARGET = 'server_for_renderer';", "const TARGET = 'wetype';") if BROAD else AGENT
        script = session.create_script(src)

        def on_msg(msg, data, exe=exe):
            if msg["type"] == "send":
                p = msg["payload"]
                # Privacy gate: content only while our own test window has focus; otherwise lengths only.
                if p.get("t") == "w" and not META_ONLY and (GATE_HWND == 0 or u32.GetForegroundWindow() == GATE_HWND):
                    p["b64"] = base64.b64encode(data).decode()
                elif p.get("t") == "w":
                    p["gated"] = True
                rec({"src": exe, **p})
            else:
                rec({"src": exe + "-error", "msg": str(msg)[:500]})

        script.on("message", on_msg)
        script.load()
        scripts.append((session, script))
        rec({"src": "host", "attached": exe, "pid": pid})

    # Candidate window events (show/hide/location) for the renderer process.
    hwnd = u32.FindWindowW(None, "wetype_candidate")
    rpid = wt.DWORD()
    u32.GetWindowThreadProcessId(hwnd, ctypes.byref(rpid))
    WinEventProc = ctypes.WINFUNCTYPE(None, wt.HANDLE, wt.DWORD, wt.HWND, wt.LONG, wt.LONG, wt.DWORD, wt.DWORD)

    def on_event(_hook, event, h, id_obj, id_child, _thread, _time):
        if id_obj != 0 or h != hwnd:
            return
        r = wt.RECT()
        u32.GetWindowRect(h, ctypes.byref(r))
        rec({"src": "win", "event": {0x8002: "show", 0x8003: "hide", 0x800B: "move"}.get(event, hex(event)), "rect": [r.left, r.top, r.right - r.left, r.bottom - r.top], "visible": bool(u32.IsWindowVisible(h))})

    cb = WinEventProc(on_event)

    def pump():
        hook = u32.SetWinEventHook(0x8002, 0x800B, None, cb, rpid.value, 0, 0)
        rec({"src": "host", "winhook": bool(hook), "hwnd": hwnd, "renderer_pid": rpid.value})
        msg = wt.MSG()
        end = time.time() + secs
        while time.time() < end:
            if u32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 1):
                u32.TranslateMessage(ctypes.byref(msg))
                u32.DispatchMessageW(ctypes.byref(msg))
            else:
                time.sleep(0.005)
        u32.UnhookWinEvent(hook)

    th = threading.Thread(target=pump)
    th.start()
    th.join()
    for session, script in scripts:
        rec({"src": "host", "stats": script.exports_sync.stats()})
        script.unload()
        session.detach()
    out.close()


if __name__ == "__main__":
    main()
