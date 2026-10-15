"""Isolated legacy UI memory comparison. No IME hooks, network, or text insertion."""
import ast
import json
import os
from pathlib import Path
import random
import shutil
import statistics
import subprocess
import sys
import time

import psutil

OUT = Path(__file__).parent / "legacy-comparison"
OUT.mkdir(exist_ok=True)


def worker(source, folder):
    app = source.parent
    folder.mkdir(exist_ok=True)
    for name in ("translate-cache.json",):
        if (app / name).exists():
            shutil.copyfile(app / name, folder / name)
    (folder / "config.json").write_text(json.dumps({
        "ui_language": "en", "target_language": "English", "api_key": "",
        "local_only": True, "theme": "light", "autostart": False,
    }), encoding="utf-8")
    os.environ["WETYPE_CONFIG"] = str(folder / "config.json")
    os.environ["WETYPE_LOG"] = str(folder / "app.log")
    os.environ.pop("WETYPE_DEBUG", None)
    os.environ.pop("WETYPE_API_KEY", None)
    sys.path.insert(0, str(app))
    os.chdir(app)

    class Isolate(ast.NodeTransformer):
        def visit_Constant(self, node):
            if isinstance(node.value, str) and "Local\\wetype_translate_overlay" in node.value:
                node.value += "_memory_compare"
            return node

        def visit_Assign(self, node):
            names = [n.id for n in node.targets if isinstance(n, ast.Name)]
            paths = {"CONFIG_FILE": "config.json", "CACHE_FILE": "translate-cache.json",
                     "LOG_FILE": "app.log"}
            for name, path in paths.items():
                if name in names:
                    node.value = ast.Constant(str(folder / path))
            if "API_KEY" in names:
                node.value = ast.Constant("")
            if "translator" in names:
                return [node, ast.parse("_bind(root, ui_q, translator)").body[0]]
            return self.generic_visit(node)

        def visit_FunctionDef(self, node):
            code = {
                "connect": 'state["conn"] = True\nreturn True, "simulated"',
                "check_hotkeys": "return",
                "commit_en": "return",
                "privacy_verdict": 'return False, "memory comparison"',
                "find_candidate_window": 'return (100, 100, 800, 282, True) if _phase["typing"] else None',
                "_request": "return",
            }.get(node.name)
            if code is not None:
                node.body = ast.parse(code).body
                return node
            return self.generic_visit(node)

    phase = {"typing": False}

    def bind(root, q, tr):
        words = [k for k in tr.cache if "\x1f" not in k and len(k) <= 6]
        if len(words) < 7:
            words = ["你好", "我们", "可以", "今天", "时间", "问题", "工作"]
        for i, word in enumerate(words):
            tr.cache.setdefault(word, f"translation {i}")
        rng = random.Random(1)
        def feed():
            if phase["typing"]:
                q.put(("candidates", rng.sample(words, 7)))
            root.after(150, feed)
        def begin():
            (folder / "ready").write_text("ready")
            feed()
        def typing():
            phase["typing"] = True
            (folder / "typing").write_text("typing")
        root.after(1000, begin)
        root.after(9000, typing)
        root.after(25000, root.destroy)

    tree = Isolate().visit(ast.parse(source.read_text(encoding="utf-8")))
    ast.fix_missing_locations(tree)
    exec(compile(tree, str(source), "exec"), {
        "__name__": "__main__", "__file__": str(source), "_bind": bind, "_phase": phase})


def measure(label, source):
    folder = OUT / (label + "-" + str(int(time.time())))
    folder.mkdir()
    samples = []
    with (folder / "console.log").open("w", encoding="utf-8") as log:
        child = subprocess.Popen([sys.executable, __file__, "--worker", str(source), str(folder)],
                                 stdout=log, stderr=subprocess.STDOUT)
        try:
            proc = psutil.Process(child.pid)
            while child.poll() is None:
                if (folder / "ready").exists():
                    state = "typing" if (folder / "typing").exists() else "idle"
                    try:
                        mi = proc.memory_info()
                        samples.append({"phase": state, "private_MB": mi.private / 1048576,
                                        "working_set_MB": mi.rss / 1048576})
                    except psutil.NoSuchProcess:
                        break
                time.sleep(1)
        finally:
            if child.poll() is None:
                child.kill()
            child.wait()
    if child.returncode:
        raise RuntimeError((folder / "console.log").read_text(encoding="utf-8"))
    result = {"source": str(source), "samples": samples, "summary": {}}
    for state in ("idle", "typing"):
        rows = [r for r in samples if r["phase"] == state][2:]
        result["summary"][state] = {k: round(statistics.median(r[k] for r in rows), 1)
                                   for k in ("private_MB", "working_set_MB")}
    (folder / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({"version": label, **result["summary"]}), flush=True)


if __name__ == "__main__":
    if "--worker" in sys.argv:
        worker(Path(sys.argv[2]), Path(sys.argv[3]))
    else:
        measure("legacy-overlay", Path(r"D:\toy\wetype-probe\wetype_overlay.py"))
        measure("python-current", Path(r"D:\toy\wetype-translate\wetype_translate.py"))
