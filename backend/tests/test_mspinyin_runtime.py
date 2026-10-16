"""UIA initialization must survive a Windows typelib timestamp change after packaging."""
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]


@unittest.skipUnless(sys.platform == "win32", "Windows UI Automation")
class RuntimeTests(unittest.TestCase):
    def test_stale_shipped_typelib_initializes_without_rewriting_files(self):
        vendor = ROOT / "backend/vendor/comtypes"
        if not vendor.is_dir():
            self.skipTest("vendored comtypes is not installed")
        scratch = ROOT / ".cache" / "uia-tests"
        scratch.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as folder:
            copy = Path(folder) / "comtypes"
            shutil.copytree(vendor, copy, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
            changed = 0
            for wrapper in (copy / "gen").glob("_*.py"):
                text = wrapper.read_text(encoding="utf-8")
                text, count = re.subn(r"(_check_version\('[^']+', )[^)]+\)", r"\g<1>1.0)", text)
                if count:
                    wrapper.write_text(text, encoding="utf-8")
                    changed += count
            self.assertGreater(changed, 0, "fixture must contain stale generated wrappers")
            before = {p.relative_to(copy): p.read_bytes() for p in copy.rglob("*") if p.is_file()}
            code = (
                "import sys; sys.coinit_flags=0; "
                f"sys.path[:0]=[{str(folder)!r},{str(ROOT / 'backend')!r}]; "
                "import comtypes.client; "
                "from translate_backend.mspinyin.observer import _load_uia; "
                "c,U=_load_uia(); a=c.client.CreateObject(U.CUIAutomation,interface=U.IUIAutomation); "
                "assert a.GetRootElement(); print('UIA_READY')"
            )
            result = subprocess.run([sys.executable, "-I", "-B", "-c", code],
                                    capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("UIA_READY", result.stdout)
            after = {p.relative_to(copy): p.read_bytes() for p in copy.rglob("*") if p.is_file()}
            self.assertEqual(before, after, "initialization must not write into the installation")


if __name__ == "__main__":
    unittest.main()
