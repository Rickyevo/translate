# Stage 3: Electron + Python foundation, focus verification, resource measurements

## What was built

```
Translate.exe (Electron 44, main process)          Python backend (child process, stdlib + ctypes)
├─ no window at startup                             ├─ JSON Lines on stdio  (docs/protocol.md)
├─ panel window ── created on first candidate list  ├─ simulated candidate source  ← WeChat adapter next
│   └─ lead preview = child window (window.open):  ├─ insertion: SendInput KEYEVENTF_UNICODE
│       same renderer process, same React tree     ├─ Alt-release guard (no stray menu activation)
├─ settings window ── on demand, destroyed on close └─ restart with backoff; clean shutdown
├─ global hotkeys ── Alt+N etc. only while a list is visible
└─ single instance: launching again opens settings
```

- **Windows.** All three surfaces are non-activating (`focusable:false` gives `WS_EX_NOACTIVATE`)
  and appear with `showInactive`. Transparent margins pass clicks through to the app underneath
  (`setIgnoreMouseEvents` with forwarding). When a menu opens, the window grows to fit it rather than
  clipping it.
- **Layout.** Main positions everything in DIP per monitor work area. The approved
  `placePreview()` from the prototype is reused unchanged.
- **Packaging.** `app/out/Translate-win32-x64`:
  - asar with integrity validation;
  - fuses: no RunAsNode, no NODE_OPTIONS, no inspector flags, app loads only from asar;
  - Overlap icon;
  - only 4 Chromium locales;
  - renderers sandboxed with context isolation and a CSP;
  - window.open limited to the preview; navigation blocked.
- **Disk.** 323 MB, mostly the Electron binary (246 MB). The backend still runs on the system Python;
  freezing it is part of the release step.

## Real focus verification

`app/scripts/focus_test.py` injects **real** mouse and keyboard input (`SendInput`) into real
applications and checks the result in the target app itself. Input is only sent while the expected
test window is in the foreground; twice the guard aborted safely when another window came forward.

| Check | Tk (Win32) | Edge (Chromium) |
|---|---|---|
| Real typing reaches the target | ✓ | ✓ |
| Click a panel row → inserted; **target keeps foreground and keyboard focus** | ✓ | ✓ |
| Alt+3 (real key chord) → inserted; focus kept | ✓ | ✓ |
| Alt+Shift+2 → clipboard, nothing inserted | ✓ | ✓ |
| Lead preview appears for a long #1 | ✓ | ✓ |
| Click the preview body → nothing inserted; focus kept | ✓ | ✓ |
| Wheel over the preview → focus kept | ✓ | ✓ |
| Alt+` hide / show → focus kept both times | ✓ | ✓ |
| Alt+1 inserts the full sentence | ✓ | ✓ |
| Right-click menu → Insert → inserted; focus kept | ✓ | ✓ |
| Click in the transparent margin reaches the app (not swallowed) | ✓ | ✓ |
| Unicode incl. emoji: `Hello — naïve café ✓ 😀` | ✓ | ✓ |
| **Total** | **19/19** | **19/19** |

Environment: Windows 11 Pro 26200, one 1920×1080 monitor at 100% scaling, dev (unpacked) build,
your interactive session. Screenshots are in `screenshots/stage3/focus/` and
`screenshots/stage3/real-*.png`.

**Not covered yet**:
- the packaged build (same code; not re-run, so as not to disturb your session again);
- the real WeChat IME composition, where insertion must cancel the composition first;
- Word, the WeChat desktop client, terminals and elevated (admin) apps;
- multi-monitor and mixed DPI;
- keyboard navigation inside the panel's menus (impossible by design in a non-activating window,
  so they are mouse-only).

## How resources were measured

`app/scripts/measure.py` launches the **packaged** app. Every 1 s (every 2 s in the sustained part)
it walks the whole process tree under `Translate.exe`: main, GPU, network utility, renderers, crash
helper, and the Python backend. For each process it records:

- **Working set (WS):** physical RAM pages mapped into the process, *including shared pages*
  (Electron/Chromium DLLs, shared memory). This is what Task Manager's "Memory" column has
  historically shown. Summing it across processes double-counts the shared DLLs, so it overstates
  the app's real cost.
- **Private committed (Private bytes):** memory committed exclusively to this process, backed by RAM
  or the page file. It is not shared and not double-counted. **This is the number that represents
  what the app costs**, and the right one for leak trends.
- **USS (unique set size):** private pages currently resident in RAM, i.e. what you would get back by
  closing the app right now.
- **CPU:** user + kernel time per interval, as % of **one** logical core. The machine has 24 logical
  CPUs, so 24% of a core ≈ 1% of the machine.

The scenarios are driven through the test endpoint. Continuous typing uses the backend's own
simulator: a new candidate list every 150 ms (6.7 keystrokes/s), each followed by 5 asynchronous
translations, a moving caret, and a commit every 7 keystrokes. So main sees real protocol traffic.
Settings opened without taking focus, and no input was injected.

## Results: default build (software rendering)

| Scenario | Processes | Working set | **Private** | USS | Backend (private) | CPU avg / p95, % of one core |
|---|---|---|---|---|---|---|
| Background idle (no window yet) | 5 | 198 MB | **70 MB** | 48 MB | 11 MB | 0.1 / 0.0 |
| Continuous typing | 6 | 351 MB | **141 MB** | 105 MB | 11 MB | 15.9 / 36.2 |
| Idle after typing (panel kept alive) | 6 | 351 MB | **141 MB** | 105 MB | 11 MB | 0.1 / 0.0 |
| Long-translation preview open | 6 | 349 MB | **136 MB** | 99 MB | 11 MB | 0.3 / 1.6 |
| Settings open | 7 | 458 MB | **175 MB** | 125 MB | 11 MB | 0.2 / 1.6 |
| Settings closed again | 6 | 353 MB | **136 MB** | 98 MB | 11 MB | 0.3 / 1.6 |

Private memory by process (MB):

| Scenario | main | GPU (software) | network utility | panel renderer (+ preview) | settings renderer | backend |
|---|---|---|---|---|---|---|
| Background idle | 33 | 14 | 11 | — | — | 11 |
| Continuous typing | 39 | 15 | 11 | 63 | — | 11 |
| Preview open | 40 | 15 | 11 | 57 | — | 11 |
| Settings open | 41 | 17 | 11 | 54 | **39** | 11 |
| Settings closed | 41 | 17 | 11 | 54 | **— (process exited)** | 11 |

**Sustained session** (17 min of typing bursts, previews, and settings opened and closed every
~1.5 min; 20 idle checkpoints):
- Private memory at the checkpoints went from 148.9 MB to 154.1 MB, a fitted slope of about
  17 MB/h. Most of it is main (41→44 MB); the panel renderer oscillates with garbage collection
  (68–70 MB); the backend is flat (+0.04 MB/h).
- A plateau with a small upward drift in main is consistent with V8 heap growth, not a clear leak. A
  17-minute run can't distinguish the two, so a multi-hour soak test is on the list for the release
  step.

Chart: `measurements/stage3/timeline-default.png`. Raw samples and summaries:
`measurements/stage3/`.

**Panel show latency** (compose → visible): **22 ms** median when warm; **160 ms** when the panel
renderer has to be created (first use, or after it was released).

## Cost of separate windows (measured variants)

| Variant | Idle, no window | Typing | After typing | Preview open | Settings open | Settings closed | Typing CPU |
|---|---|---|---|---|---|---|---|
| **Default** (software, preview shares the panel renderer) | 70 | 141 | 141 | 136 | 175 | 136 | 15.9 % |
| GPU rendering (`--gpu`) | 117 | 214 | 208 | 213 | 278 | 224 | 9.5 % |
| Preview in its **own** renderer | 74 | 145 | 133 | **162** | 202 | 162 | 17.8 % |
| Release the panel renderer after **30 s** idle | 73 | 145 | **102** | 110 | 125 | **86** | 14.1 % |

All figures are total private MB.

- **Panel window**: one renderer, 55–64 MB. Keeping it alive costs that much between typing sessions
  and buys a 22 ms show instead of 160 ms.
- **Preview as a child window**: about 0 MB extra, because it shares the panel's process. As its own
  renderer it costs **+30 MB** for as long as it exists. The child-window approach is clearly
  better.
- **Settings**: +39 MB while open, **fully returned when closed**; its renderer process exits.
- **GPU process with hardware acceleration**: +47 to +88 MB everywhere. It halves typing CPU, but
  that saving only applies while typing, whereas the memory is paid all the time. Software rendering
  is pixel-identical here (`screenshots/stage3/real-panel-preview-{software,gpu}.png`), so it is the
  default.

## Problems the measurements found and fixed

| Found | Effect | Fix |
|---|---|---|
| Renderer↔main layout feedback loop | **~150% of a core** with the preview open; renderer memory climbing | Size, rows and placement are only sent when they change, on both sides |
| De-dup exposed two ordering bugs: the preview was never placed if its window was created after the request, and the panel didn't re-show with an unchanged size | Preview missing; panel missing on the next composition | Place on window creation; lay out on every new list (verified across repeated compositions) |
| GPU process with hardware acceleration | +75 MB private, more typing CPU | Software rendering by default (`--gpu` to opt in) |
| Animated shimmer and `backdrop-filter` in transparent windows | Constant whole-window repaints while loading | Static placeholders; no backdrop-filter (no visual loss: an Electron window can't blur the desktop) |
| Every keystroke caused up to 6 renders (list plus 5 translations) | Typing CPU | State pushes coalesced to one per frame |

Net effect on typing CPU: **49% → 16% of one core** (≈0.7% of this machine). Idle memory: **118 →
70 MB** private.

## Assessment

For a resident utility, the numbers mean:
- **Idle CPU is effectively zero** (0.1% of one core, no polling, nothing animating). Short typing
  bursts cost 16% of a core on average, with a 36% p95, on a 24-thread machine. That's acceptable.
- **Memory is the weak point.** Electron's fixed floor (main 33 + GPU 14 + network service 11 MB)
  plus the backend (11 MB) is **~70 MB private before anything appears**. Once the panel has been
  used it is **~135–150 MB** for as long as the panel renderer is kept. That's typical for an Electron
  utility, but 3–5× a native one: IMEs and native helpers typically sit at 15–40 MB private.

**Recommendation:** keep Electron + Python, and make releasing the panel renderer after idle the
default.
- **Release after 3 minutes without typing.** Typical resident memory is then **~85 MB private**,
  ~70 MB right after start. During a typing session it is ~140 MB, and the first keystroke after a
  long pause shows the panel in ~160 ms instead of ~22 ms.
- **Keep the preview as a child window**, and keep settings on demand.
- **Run a multi-hour soak test** before release to settle the 17 MB/h question.

This keeps the approved design pixel-for-pixel and every verified behaviour. If ~85 MB idle /
~140 MB active is still more than you want for a utility, see the alternatives.

## Alternatives that keep the approved design (not implemented)

| Option | What changes | Expected resident private | Cost / risk |
|---|---|---|---|
| **A. Electron + idle release** (recommended) | One default flag | ~70–85 MB idle, ~140 MB typing | None; measured |
| B. WebView2 host (small C#/.NET or Rust/Tauri shell) reusing the same React UI | Shell only; UI code unchanged | Estimated 60–110 MB; WebView2 is still Chromium (browser + GPU + renderer processes), its runtime is shared on disk, and the installer drops to a few MB | Rewrite main process + IPC (~1 week); must re-run focus tests; memory gain uncertain, measure before committing |
| C. **Native panel + preview** (Win32 + Direct2D/DirectWrite, or WinUI 3), settings as an on-demand web window | Panel/preview re-implemented natively to the same tokens and spec; settings unchanged | ~25–40 MB resident (+~70 MB only while settings is open) | 1–2 weeks; pixel parity needs side-by-side review; two UI stacks to maintain |

I'd only take B or C if a resident budget under ~80 MB is a hard requirement. C is the one that
reaches native-utility levels.

## Still open (later stages)

- WeChat IME adapter (Frida), real composition cancel before insertion, and caret/UIA position
  sources.
- Translation providers, cache and dictionary.
- Frozen backend.
- Soak test.
- Alt-held key highlighting (needs a low-level keyboard hook).
- Thin scrollbar in the settings window. It shows the classic Windows scrollbar, visible in
  `real-settings-overview.png`.
- Overview status text wired to the real adapter state.
- Multi-monitor and DPI verification on hardware.
