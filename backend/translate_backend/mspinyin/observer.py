"""Microsoft Pinyin observer: reads its candidate window through UI Automation (the accessibility interface Narrator
uses). No injection into any process, no keyboard hooks. Candidate text is kept in memory and handed to the source;
nothing is logged or written.

Windows 11 draws Microsoft Pinyin's candidates in TextInputHost.exe as a Menu with AutomationId
"IME_Candidate_Window", holding a List ("TEMPLATE_PART_CandidatePanel") of ListItems whose names are the candidates.
MenuOpened / MenuClosed events tell when a composition's window opens and closes; while it is open the list is read
(one cached cross-process call, ~1–3 ms) every POLL_S and right after any event.
"""
from __future__ import annotations

import sys
import threading
from pathlib import Path

from .. import win32
from ..log import log

CANDIDATE_WINDOW_ID = "IME_Candidate_Window"
HOST_PROCESSES = {"textinputhost.exe", "chsime.exe"}
POLL_S = 0.04   # while the candidate window is open
IDLE_S = 1.0    # otherwise (events wake it up)


def _vendor():
    vendor = Path(__file__).resolve().parents[2] / "vendor"
    if vendor.is_dir() and str(vendor) not in sys.path:
        sys.path.insert(0, str(vendor))


def _rect(r) -> dict | None:
    w, h = r.right - r.left, r.bottom - r.top
    return {"x": r.left, "y": r.top, "w": w, "h": h} if w > 0 and h > 0 else None


class Observer:
    """Runs on its own thread; posts {"kind": "connection"} once, then {"kind": "mspy", texts, rect, canvas,
    foreground} whenever what Microsoft Pinyin shows changes (texts=[] when the window closes)."""

    def __init__(self, post, stop: threading.Event):
        self._post, self._stop = post, stop
        self._wake = threading.Event()
        self._lock = threading.Lock()
        self._menu = None        # the open candidate menu (IUIAutomationElement)
        self._closed = False     # a MenuClosed event arrived for it

    # ---- UI Automation event handlers (called on UIA's threads: keep them tiny) ------------------
    def _make_handler(self, U, comtypes):
        observer = self

        class Handler(comtypes.COMObject):
            _com_interfaces_ = [U.IUIAutomationEventHandler]

            def HandleAutomationEvent(self, sender, event_id):
                try:
                    if sender.CurrentAutomationId != CANDIDATE_WINDOW_ID:
                        return 0
                    if win32.process_exe(sender.CurrentProcessId).lower() not in HOST_PROCESSES:
                        return 0
                    with observer._lock:
                        if event_id == U.UIA_MenuOpenedEventId:
                            observer._menu, observer._closed = sender, False
                        elif event_id == U.UIA_MenuClosedEventId:
                            observer._closed = True
                    observer._wake.set()
                except Exception:  # noqa: BLE001 — an element that vanished mid-event
                    pass
                return 0

        return Handler()

    # ---- reading --------------------------------------------------------------------------------
    def _snapshot(self, uia, U, menu, cond, cache, walker) -> tuple | None:
        """(texts, bar rect, window rect) of the open candidate window, or None if it is closed/gone."""
        try:
            rect = _rect(menu.CurrentBoundingRectangle)
            if rect is None or menu.CurrentIsOffscreen:
                return None
            items = menu.FindAllBuildCache(U.TreeScope_Descendants, cond, cache)
            texts = []
            for i in range(items.Length):
                name = items.GetElement(i).CachedName
                if name:
                    texts.append(name)
            parent = walker.GetParentElement(menu)
            canvas = _rect(parent.CurrentBoundingRectangle) if parent else None
            return (tuple(texts), rect, canvas or rect)
        except Exception:  # noqa: BLE001 — the window closed while we read it
            return None

    def run(self) -> None:
        _vendor()
        # UI Automation events arrive on UIA's own threads: this thread must be in the multithreaded apartment.
        # comtypes initializes COM when imported, from sys.coinit_flags (0 = COINIT_MULTITHREADED).
        sys.coinit_flags = 0
        import logging
        logging.getLogger("comtypes").setLevel(logging.WARNING)
        try:
            import comtypes
            import comtypes.client
            from comtypes.gen import UIAutomationClient as U  # generated at build time (vendor/comtypes/gen)
        except Exception as e:  # noqa: BLE001
            log.info("mspinyin: UI Automation unavailable (%s)", type(e).__name__)
            self._post({"kind": "connection", "state": "failed", "epoch": 1, "code": "uia_missing"})
            return
        try:
            uia = comtypes.client.CreateObject(U.CUIAutomation, interface=U.IUIAutomation)
            root = uia.GetRootElement()
            handler = self._make_handler(U, comtypes)
            for ev in (U.UIA_MenuOpenedEventId, U.UIA_MenuClosedEventId):
                uia.AddAutomationEventHandler(ev, root, U.TreeScope_Descendants, None, handler)
            cond = uia.CreatePropertyCondition(U.UIA_ControlTypePropertyId, U.UIA_ListItemControlTypeId)
            cache = uia.CreateCacheRequest()
            cache.AddProperty(U.UIA_NamePropertyId)
            walker = uia.ControlViewWalker
        except Exception as e:  # noqa: BLE001
            log.info("mspinyin: UI Automation setup failed (%s)", type(e).__name__)
            self._post({"kind": "connection", "state": "failed", "epoch": 1, "code": type(e).__name__})
            return
        self._post({"kind": "connection", "state": "connected", "epoch": 1})
        last = None
        try:
            while not self._stop.is_set():
                with self._lock:
                    menu, closed = self._menu, self._closed
                self._wake.wait(POLL_S if menu is not None else IDLE_S)
                self._wake.clear()
                if self._stop.is_set():
                    break
                with self._lock:
                    menu, closed = self._menu, self._closed
                if menu is None:
                    continue
                snap = None if closed else self._snapshot(uia, U, menu, cond, cache, walker)
                if snap is None or not snap[0]:
                    with self._lock:
                        if self._menu is menu:
                            self._menu = None
                    if last is not None:
                        self._post({"kind": "mspy", "texts": [], "rect": None, "canvas": None, "foreground": win32.foreground()})
                        last = None
                    continue
                if snap != last:
                    last = snap
                    texts, rect, canvas = snap
                    self._post({"kind": "mspy", "texts": list(texts), "rect": rect, "canvas": canvas, "foreground": win32.foreground()})
        finally:
            try:
                uia.RemoveAllEventHandlers()
            except Exception:  # noqa: BLE001
                pass
