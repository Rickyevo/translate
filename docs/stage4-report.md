# Stage 4: real candidates in the app (simulated translations)

Status: **done.**
- The packaged EXE passes the live test with the real WeChat IME (25/25, Tk window, clickable setting on).
- Offline: the replay suite passes 40/40 and the backend unit tests 38/38.
- No translation service is connected.
- The earlier sections are kept as the record of the fixes the live runs led to.

## What changed

```
WeType (wetype_server.exe) ──pipe writes──▶ Frida observer (read-only, in IME) ──▶ backend WeTypeSource
wetype_renderer.exe candidate window ──WinEvent hooks (show/hide/move, focus, foreground)──▶ backend
backend: generations · stale rejection · simulated "[sim]" translations · insertion with composition cancel
   └─ JSON Lines ─▶ Electron main: panel/preview layout, render scheduling, idle release ─▶ panel renderer
```

| Area | Change |
|---|---|
| Composition handling | A pinyin edit **invalidates** the current list at once (insert → `stale`) but no longer sends `composition.end`. Before, the panel would have been hidden and re-shown on every keystroke, losing its grow-only width and lead-preview state. `composition.end` now only means a real end: commit, clear/cancel, window hidden, focus moved, IME disconnected, pause |
| Host list handling | Same `gen` = reposition (keep items + translations); older `gen` ignored; new `gen` in a running composition keeps the composition; backend restart clears the panel |
| Simulated translations | `simtranslate.py`: every result is `[sim] …` (sample dictionary word, else the candidate echoed), per-item latency 60 + 20·i ms, one scheduler thread instead of a timer thread per item. The footer shows **Simulated translations — not real** (DESIGN §9), localized in all four UI languages |
| Insertion (pinyin composition) | Check target window / denylist / password → Alt guard; refuse if a modifier is still held after 1 s (Esc with Alt = Alt+Esc) → **Esc only while the candidate window is visible** → wait ≤ 500 ms for the IME to confirm (pipe "cleared" or window hidden), processing only IME events → 15 ms settle → re-check foreground → type. No confirmation → `ime`, nothing typed |
| Window tracking | 80 ms polling replaced by **WinEvent hooks**: foreground + focus (global), show/hide/move scoped to the candidate window's process (`wetype_renderer.exe`). The only timer left is a 2 s rescan for the IME restarting |
| Privacy | No candidate text, pinyin or translation is logged at any level; uncaught exceptions are logged by type only; the observe/test endpoints expose counts, states and geometry only; the package no longer ships the research capture tools (they write raw pipe data to disk) or tests |
| Notices | Insert/copy notices are now i18n keys (were English literals) |
| Test seams | `--test-source=wetype-replay`: real `WeTypeSource` fed synthetic pipe bytes, insertion recorded instead of sent. `--observe=PORT`: read-only state endpoint for live runs |

## Verification

| Suite | Result |
|---|---|
| Backend unit tests (`backend/tests`, synthetic bytes, no IME, no input) | **38 / 38** |
| Replay end-to-end, dev build (`app/scripts/stage4_replay_test.py`) | **36 / 36** |
| Replay end-to-end, **packaged EXE** | **36 / 36** |
| Live attach, packaged EXE in normal mode | connected; **0 visible windows**; log has status/counts only |
| Live re-attach: backend killed 3× in the packaged app | restarted after 0.3–1.1 s each time, IME reconnected each time; `wetype_server` stayed at 200.3 MB (no stacked agents) and returned to 197.9 MB after quit |
| Event watcher, live | resolves the real candidate window (owned by `wetype_renderer.exe`) and reports metadata; stops cleanly |
| Stage-3 fixture mode regression | panel, preview, end: OK |

The replay suite covers, through the real adapter code and the real Electron windows:
- **Ordering:** generations strictly increase per keystroke.
- **Composition continuity:** the panel is not hidden between keystrokes, and composition state is kept.
- **Stale rejection:** in a 6-keystroke burst only the latest generation is shown, and 16 stale results were dropped. Inserting against an old generation is refused and types nothing.
- **Tracking:** the panel is placed under the row and follows window moves without changing generation; the lead preview opens for a long #1 and tracks moves. Near the bottom-right corner the panel flips above and slides left, and the preview stays on screen.
- **Hide/show:** the Alt+0 action works, and the panel ends on commit, clear, window hidden and focus change.
- **Insertion order:** Esc is sent strictly before the text. If the IME ignores Esc, insertion is refused and the list is kept. A held modifier is refused.
- **Pause/resume.**
- **IME disconnect/reconnect:** a mid-composition list after reconnect is ignored.
- **Idle release:** the panel renderer is released and recreated.
- **Backend crash restart.**

Screenshots (synthetic candidates only): `screenshots/stage4/replay-simulated-{short,long}.png`.

## Resources: before vs after optimization

Same packaged build except for the optimizations; same scripted workload; 45 s phases. 24 logical CPUs, so
24% of one core ≈ 1% of the machine. Raw: `measurements/stage4/summary-{before,after}.json`.

| Scenario | Private MB before → after | CPU % of one core, avg (p95) before → after |
|---|---|---|
| **Live idle, attached to WeType, no window** (normal mode) | 119.2 → 119.0 | 0.29 (1.6) → **0.04 (0.0)** |
| Replay idle, no window (no Frida) | 72.8 → 73.4 | 0.47 → 0.18 |
| **Typing** through the adapter path, 150 ms/keystroke | 162.5 → 145.3 * | 18.5 (31.9) → **14.7 (20.5)** |
| Long-translation preview open | 126.7 → 121.6 | 0.22 → 0.33 |
| After idle release | 79.0 → 80.2 | 0.18 → 0.28 |

\* Within run-to-run noise. Typing memory ranged 145–160 MB over ten 40 s runs; I don't claim a memory
gain. The "idle after typing" phase is left out: the after run was longer, and the panel was released inside
it, so it isn't comparable.

A/B runs of the typing phase (40 s each, two runs) attribute the CPU gain:

| Variant | CPU avg, % of a core |
|---|---|
| Baseline | 22.0 / 20.0 |
| Renderer observers created once; mutation observer only reacts to menus | 20.1 / 19.8 |
| + 33 ms coalescing of state pushes | 16.1 / 17.8 |
| + **new lists pushed immediately**, only translations coalesced (shipped) | **15.8 / 15.6** |
| + V8 `--max-semi-space-size=1` in the renderer | 15.6 / 17.4, no memory change → **not adopted** |

Speed: a new list now reaches the renderer with no coalescing delay; previously it waited up to 16 ms.
Translation updates wait up to 33 ms. Times below are host-state times, not painted frames:
- Panel creation: ~220 ms cold.
- A list in a running composition: ~2 ms.
- After an idle release: 166–222 ms. An earlier 19 ms figure was a bug: an empty window was shown with the old renderer's size. Fixed.
- Insertion sequence with a synthetic IME: 17–42 ms.

### Where the memory is

| Process | Live idle, private MB (USS) |
|---|---|
| Electron main | 34.3 (23.2) |
| GPU (software compositing) | 13.7 (7.5) |
| Network utility | 11.1 (6.5) |
| Crashpad | 1.2 (0.8) |
| **Backend (Python + Frida)** | **58.8 (19.7)**. Without Frida: 12.7 (10.8) |
| *Inside wetype_server* (not our process group) | +2.5 to +2.8; returns to baseline on quit |

**Frida is the new cost: +46 MB private commit, of which ~9 MB is resident.** It comes from importing
`_frida.pyd`: its 33 MB writable `.data` section is charged as commit at load. No in-process setting changes
that. Options, none implemented:
- **A. Keep as is.** ~119 MB idle, ~73 MB of it Electron + Python.
- **B. Short-lived injector + persistent agent writing to our named pipe.** Frida would load only to inject (−46 MB resident commit). The cost is an agent that must detect our exit and unhook itself, plus a new single-instance and reconnection design inside the IME process. This is a real risk to your input method if it goes wrong.
- **C. Small native observer DLL** (C/Rust, ~100 KB) in place of Frida. Lowest footprint; needs a native toolchain, and gives up Frida's tested hooking engine.

I'd stay with A until the translation provider and frozen backend land, then decide. C is the clean end
state if the idle budget matters.

## Live attempt 1 (aborted at preflight)

The first live run (Tk window, packaged EXE) typed one key, `s`, and no list reached the panel, so it stopped
without typing anything else. Cause, found in review: the adapter discarded pipe data until it knew the
candidate window was visible, and also whenever its cached foreground window lagged a focus change. WeType
very likely writes the composition and the list *before* it shows the window, so the first keystroke of every
composition was lost. Fixed:
- Data is always decoded (still gated on pause, password fields and the denylist).
- A list is shown as soon as the window appears, and the counter `late` counts these.
- The foreground is refreshed instead of dropping data.
- A direct window probe at 30, 100 and 300 ms covers a missed show notification.

Three new unit tests cover this (38/38), and the replay suite still passes 36/36 on the rebuilt EXE. The live
preflight now types `shi` and reports whether IME data arrived and whether the candidate window was visible.

## Live attempt 2: 21 / 24 with the real IME (Tk window, packaged EXE)

Verified live:
- **Generations:** a new generation for every keystroke, strictly increasing (7 keys → gens 4–10).
- **Composition continuity:** no panel hide during a composition, and one composition per word.
- **Placement:** the panel sits under the IME bar, with 5 candidates shown.
- **Alt+2 and Alt+1:** they insert `[sim] …` with no pinyin left, keep focus and trigger no menu activation. The long #1 inserted in full.
- **Cancel and commit:** Esc cancels (panel hidden, field empty), Backspace to empty ends the composition, and Space commits WeType's own candidate.
- **Lead preview:** it opens for a long #1, stays on screen and stays clear of the IME bar.
- **Alt+0:** it hides and shows the panel while the IME keeps composing.
- **Idle release:** the panel renderer was released and recreated in 199 ms.
- **Ordering counters** over 8 compositions: 63 lists, 58 pinyin changes, 1 duplicate, `late` 8 (a list arrived before its window, and was shown when the window appeared), `dropped` 7. The dropped lists arrived with no composition in progress, most likely WeType's post-commit suggestions. Dropping them is intended.

Failed, and fixed (not yet re-verified live):
1. **Clicking a panel row did nothing.** No insert request reached the app, and the composition stayed.
   - Cause: WeType's candidate window is a 628×314 mostly transparent topmost canvas (the bar is only its top ~180 px) that overlaps the panel. Among topmost windows the last one raised wins.
   - Fix: re-raise the panel and preview 250 ms after the IME update settles. This toggles topmost, which is a z-order change only, with no DIP/pixel risk.
   - Raising on every keystroke cost about 2% of a core, so it was debounced. Typing CPU is back at ~17% (in noise).
   - The live test now also checks which window is under the pointer before clicking.
2. **Bar geometry:** WeType draws at offset **109, height 70**, not 137/46. The bottoms differ by 4 px, so placement was already right; the anchor now covers the whole bar (pinyin line + candidates), so the preview avoids all of it. This is measured at 96 dpi only.

## Live attempt 3: 22 / 25. Click insertion blocked by the IME's UIAccess window

Everything that passed in attempt 2 passed again. The measured bar is now drawn at 112/67, against the new
109/70 model, which passes. The new pointer check shows the cause of the click failure: **the window under the
panel row is `wetype_renderer.exe`**, even after the re-raise.

Read without input: `wetype_renderer.exe` runs with **UIAccess** (token flag 1), and its candidate canvas is in
**z-band 2 (ZBID_UIACCESS)**. Normal topmost windows, ours included, are in band 1, so no ordinary app can be
above it. Its 628×314 canvas extends about 112 px above and 135 px below the drawn bar, and its transparent
parts still hit-test. Wherever the panel overlaps the canvas:
- it **displays correctly**, and the hotkeys work (Alt+N insert, Alt+0, Alt+` etc. are verified live);
- it **gets no mouse input**: no click, hover (so no hover preview), right-click menu or wheel.

The re-raise is therefore ineffective against this window. It is harmless and costs nothing while typing, and
it is kept for ordinary topmost windows. The ways out:
- placing the panel outside the canvas, which means a 112–135 px gap from the bar;
- giving our panel UIAccess. This needs the EXE signed with a trusted certificate, installed under Program Files, and a `uiAccess=true` manifest. It is a release-step task.

### Decision: opt-in "Keep the panel clickable"

You chose an opt-in setting. **Appearance › Keep the panel clickable** (off by default, previews live,
localized in all four UI languages):
- When on, the panel is placed below, or above near the screen bottom, the IME's whole window, and the lead preview avoids that window too. With no room on either side, it falls back to the bar.
- When off, the approved placement is unchanged, and hotkeys remain the way to insert.
- The backend now also reports the IME window (`anchor.canvas`).

Four replay checks were added; the packaged EXE passes **40 / 40**.

## Live attempt 4 (`--clickable`): 25 / 25 with the real IME

Tk window, packaged EXE, "Keep the panel clickable" on:
- **Placement:** the panel sits 4 px below WeType's window. `Translate.exe` is the window under the pointer at the row.
- **Click insertion:** it inserted `[sim] …` with no pinyin left, the IME composition was gone before typing, and the target kept foreground and keyboard focus.
- **Everything else passed again:** Alt+2, Esc, the bar geometry (112/67), Backspace, Space commit, the lead preview, Alt+1, Alt+0, and idle release/recreation (202 ms).
- **Ordering over 9 compositions:** 63 lists, 58 pinyin changes, 3 duplicates, `late` 9, `dropped` 8. Every dropped list arrived with no composition in progress; post-commit suggestions are the likely source, and dropping them is intended.

**Stage 4 live status:**
- Keyboard paths work in both placements.
- Mouse paths work with the clickable setting on. With it off (the default), clicks over WeType's window cannot work: the window is UIAccess, in z-band 2.

Still not covered live:
- Edge and other apps;
- restarting `wetype_server` itself;
- multi-monitor and DPI scaling other than 100%;
- real-typing CPU, including the observer's cost inside the IME;
- the right-click menu and wheel on the panel in clickable mode (same input path as the verified click).

## Not yet verified (needs your go-ahead: real keyboard/mouse)

`app/scripts/stage4_live_test.py` runs the **packaged** EXE live (`--observe`). It types pinyin, presses
Esc/Backspace/Space/Alt chords, and clicks the panel, only into its own Tk test window (or Edge with
`--edge`). It aborts if any other window comes to the foreground. It checks:

1. A generation per keystroke, no panel hide during a composition, the panel under the row, the candidate count.
2. Click insert: `[sim] …` inserted, no pinyin left, the IME composition gone, focus kept.
3. Alt+N insert, the same checks.
4. **Esc cancel**, and the **137/46 row offsets**: from two in-memory screen grabs of the IME window region, it measures where WeType actually draws. Nothing is saved.
5. Backspace to empty.
6. Space commit by the IME.
7. Long #1: lead preview on screen and clear of the row; Alt+1 inserts it.
8. Alt+0 hide/show while composing.
9. Idle release and recreation.
10. Ordering counters from the log (`dropped` should be 0).

Still open after that:
- Restarting `wetype_server` itself (vs. our backend, which is verified). This needs separate permission, since it interrupts your IME.
- Edge and other apps (Word, WeChat, terminals, elevated apps).
- Multi-monitor and mixed DPI.
- Real-typing CPU, including the observer's cost inside the IME.
- Whether WeType commits its own candidate when the panel is clicked, rather than leaving the composition for our Esc. The live test will show this.

## Known limitations

- **Typing and insertion window:** an insert pressed in the few milliseconds between a keystroke and its new list is refused as `stale`, silently, and the user simply presses again. This is deliberate: it is better than inserting the previous list's text.
- **Event ordering:** if WeType ever sent a list *before* its composition update, that list would be dropped. The `dropped` counter exists to catch this on real input.
- **Row geometry:** the 137/46 row offsets remain an assumption until check 4 runs.
- **Backend runtime:** the packaged backend still runs on the system Python 3.12. Freezing it is a release-step task carried over from stage 3.
