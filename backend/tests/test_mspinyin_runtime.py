"""UIA initialization must survive a Windows typelib timestamp change after packaging."""
from pathlib import Path
import re
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest


ROOT = Path(__file__).resolve().parents[2]


@unittest.skipUnless(sys.platform == "win32", "Windows UI Automation")
class RuntimeTests(unittest.TestCase):
    def test_minimal_interfaces_match_system_abi(self):
        code = textwrap.dedent(f'''
            import sys
            sys.coinit_flags = 0
            sys.path[:0] = [{str(ROOT / 'backend')!r}, {str(ROOT / 'backend/vendor')!r}]
            from translate_backend.mspinyin.observer import _load_uia
            c, slim = _load_uia()
            assert 'comtypes.client' not in sys.modules
            import comtypes.client
            c.client.gen_dir = None
            full = c.client.GetModule('UIAutomationCore.dll')
            checked = 0
            for name in vars(slim):
                if not name.startswith('IUIAutomation'):
                    continue
                minimal, original = getattr(slim, name), getattr(full, name)
                assert minimal._iid_ == original._iid_, name
                assert len(minimal._methods_) == len(original._methods_), name
                for slot, method in enumerate(minimal._methods_):
                    if method.name.startswith('_reserved_'):
                        continue
                    expected = original._methods_[slot]
                    assert method.name == expected.name, (name, slot)
                    assert method.idlflags == expected.idlflags, (name, slot)
                    assert method.paramflags == expected.paramflags, (name, slot)
                    assert [t.__name__ for t in method.argtypes] == [t.__name__ for t in expected.argtypes], (name, slot)
                    assert method.restype == expected.restype, (name, slot)
                    checked += 1
            assert checked >= 17
            assert slim.CUIAutomation._reg_clsid_ == full.CUIAutomation._reg_clsid_
            for name in vars(slim):
                if name.startswith(('UIA_', 'TreeScope_')):
                    assert getattr(slim, name) == getattr(full, name), name
            print('ABI_OK', checked)
        ''')
        result = subprocess.run([sys.executable, '-I', '-B', '-c', code], capture_output=True, text=True, timeout=30,
                                env={**os.environ, 'TRANSLATE_UIA_MINIMAL': '1'})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('ABI_OK', result.stdout)

    def test_observer_uses_uia_without_loading_full_typelib(self):
        code = textwrap.dedent(f'''
            import sys
            sys.coinit_flags = 0
            sys.path[:0] = [{str(ROOT / 'backend')!r}, {str(ROOT / 'backend/vendor')!r}]
            from unittest.mock import patch
            import comtypes.client
            from translate_backend.mspinyin.observer import _load_uia
            with patch.object(comtypes.client, 'GetModule', side_effect=AssertionError('full typelib loaded')):
                c, U = _load_uia()
                uia = c.CoCreateInstance(U.CUIAutomation._reg_clsid_, interface=U.IUIAutomation)
                root = uia.GetRootElement()
                assert root
                assert isinstance(root.CurrentProcessId, int)
                assert isinstance(root.CurrentAutomationId, str)
                assert isinstance(root.CurrentIsOffscreen, int)
                assert root.CurrentBoundingRectangle.right >= root.CurrentBoundingRectangle.left
                cache = uia.CreateCacheRequest()
                cache.AddProperty(U.UIA_NamePropertyId)
                condition = uia.CreatePropertyCondition(30002, root.CurrentProcessId)
                matches = root.FindAllBuildCache(1, condition, cache)
                assert matches.Length == 1
                assert isinstance(matches.GetElement(0).CachedName, str)
                assert not uia.ControlViewWalker.GetParentElement(root)
                class Handler(c.COMObject):
                    _com_interfaces_ = [U.IUIAutomationEventHandler]
                    def HandleAutomationEvent(self, sender, event_id):
                        self.received = (sender.CurrentProcessId, event_id)
                        return 0
                handler = Handler()
                callback = handler.QueryInterface(U.IUIAutomationEventHandler)
                callback.HandleAutomationEvent(root, U.UIA_MenuOpenedEventId)
                assert handler.received == (root.CurrentProcessId, U.UIA_MenuOpenedEventId)
                for event in (U.UIA_MenuOpenedEventId, U.UIA_MenuClosedEventId):
                    uia.AddAutomationEventHandler(event, root, U.TreeScope_Descendants, None, handler)
                uia.RemoveAllEventHandlers()
            print('MINIMAL_UIA_READY')
        ''')
        result = subprocess.run([sys.executable, '-I', '-B', '-c', code], capture_output=True, text=True, timeout=30,
                                env={**os.environ, 'TRANSLATE_UIA_MINIMAL': '1'})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('MINIMAL_UIA_READY', result.stdout)

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
