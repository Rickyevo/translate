"""A real Win32 text target (Tk). Prints its geometry, then answers 'get' on stdin with the text as JSON.

Run: python target_tk.py  → first stdout line: {"hwnd":..., "text_rect": {...}} (physical px)
"""
import ctypes
import json
import sys
import threading
import tkinter as tk

ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
root = tk.Tk()
root.title("Translate focus target (Tk)")
import os
root.geometry(os.environ.get("TARGET_GEOMETRY", "640x260+120+120"))  # physical px (per-monitor DPI aware)
root.attributes("-topmost", True)
txt = tk.Text(root, font=("Segoe UI", 12), wrap="word")
txt.pack(fill="both", expand=True, padx=8, pady=8)
txt.focus_set()


def announce():
    root.update_idletasks()
    hwnd = ctypes.windll.user32.GetParent(root.winfo_id()) or root.winfo_id()
    out = {"hwnd": hwnd, "text_rect": {"x": txt.winfo_rootx(), "y": txt.winfo_rooty(), "w": txt.winfo_width(), "h": txt.winfo_height()}, "text_hwnd": txt.winfo_id()}
    print(json.dumps(out), flush=True)


def stdin_loop():
    for line in sys.stdin:
        cmd = line.strip()
        if cmd == "get":
            value = {}
            ev = threading.Event()

            def read():
                value["text"] = txt.get("1.0", "end-1c")
                value["insert"] = txt.bbox("insert")
                ev.set()

            root.after(0, read)
            ev.wait(2)
            print(json.dumps({"text": value.get("text", ""), "caret": value.get("insert")}, ensure_ascii=False), flush=True)
        elif cmd == "focus":
            value = {}
            ev = threading.Event()

            def read_focus():
                value["focus"] = str(root.focus_get()) if root.focus_get() else ""
                ev.set()

            root.after(0, read_focus)
            ev.wait(2)
            print(json.dumps({"focus": value.get("focus", ""), "text": str(txt)}), flush=True)
        elif cmd == "clear":
            ev = threading.Event()
            root.after(0, lambda: (txt.delete("1.0", "end"), ev.set()))
            ev.wait(2)
            print("{}", flush=True)
        elif cmd == "quit":
            root.after(0, root.destroy)
            return


root.after(200, announce)
threading.Thread(target=stdin_loop, daemon=True).start()
root.mainloop()
