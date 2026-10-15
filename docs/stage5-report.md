# Stage 5: real translation (service, dictionary, cache, keys)

Status: **built and verified against a local mock service; not yet run against a real provider.** A real run
needs your key, entered by you in Settings › Translation (see *Next*). No external translation request has been
made by me or the tests.

## How a candidate list is translated

```
list (gen N) ─► cache (memory, then encrypted disk) ─► CC-CEDICT (target English only) ─► service (one batch)
                 instant                               instant, offline                   after 120 ms of no typing
```

- **Cache and dictionary** answer in the same tick as the list, so they render with it.
- **Everything else goes in one request per list.** The request is sent only once the list has been stable for 120 ms. A list replaced before a worker picks its job up is dropped. Fast typing therefore costs **one request per pause**: 8 keystrokes 40 ms apart produced 1 request.
- **Late results still count.** A result arriving for a replaced list is cached, and fills any current row with the same text.
- **Errors map to rows and the footer:**
  - timeout or unreachable → row *Failed* (timeout/network), footer *Offline — using local dictionary*;
  - 401/403 → *API key rejected — fix in settings*;
  - other errors → *Can't reach the service. Retrying.*
- **Retry:** clicking a failed row, its context menu or the preview's *Retry* re-requests that item.
- **No key or model** → footer *Dictionary only — set up a service* (new, all four UI languages). Other rows show *No local entry*.
- **Local-only mode:** nothing is sent.

## Services

| Service | Wire format | Endpoint | Default model | Authentication |
|---|---|---|---|---|
| OpenAI | Chat Completions | `https://api.openai.com/v1` | `gpt-6-luna` | API key (Bearer) |
| Claude | Messages API | `https://api.anthropic.com` | `claude-opus-5-5` | API key (`x-api-key`) or auth token (Bearer) |
| Gemini | generateContent | `https://generativelanguage.googleapis.com/v1beta` | `gemini-flash-latest` | API key (`x-goog-api-key`) |
| Grok (xAI) | Chat Completions | `https://api.x.ai/v1` | `grok-4.20` | API key (Bearer) |
| OpenCode Go | Chat Completions | `https://opencode.ai/zen/go/v1` | `deepseek-v4-flash` | Plan API key (Bearer) |
| DeepSeek | Chat Completions | `https://api.deepseek.com` | `deepseek-v4-flash` | API key (Bearer) |
| Custom | any of the three | yours | yours | Bearer · `x-api-key` · custom header · query parameter · none |

- **Configurable per service:** endpoint, model (*Load models* lists what the service offers), authentication, timeout and JSON output. Each provider keeps its own settings and its own key.
- **Sources:** endpoints and models come from each provider's documentation, checked with tavily-search; Claude's from the Claude API reference.
- **Claude settings:**
  - `output_config.effort: "low"` on models that support it (a short, simple task).
  - Server-side refusal fallback (`fallbacks: "default"`, beta `server-side-fallback-2026-07-01`) on the models that accept it, so a classifier decline is retried server-side.
  - `stop_reason: "refusal"` is handled.
  - The adapter calls the Messages API over HTTPS rather than through the Anthropic Python SDK. The backend is stdlib-only, for its resident-memory budget and the frozen build, and talks to six providers through one client. **If you prefer the official SDK for Claude, say so**; it would add its dependencies (httpx, pydantic) to the backend.
- **Plans:**
  - Plan keys that are issued as API keys (OpenCode Go) work as above.
  - Consumer chat subscriptions signed in with a browser (for example a Claude Pro/Max login) are **not** supported. Use an API key or token issued for API access.
- **Prompt:** one system instruction ("translate these Chinese IME candidates into <language>, as the user would type them, JSON only"). Candidates go as `{"1": …, "2": …}`, and the reply is parsed tolerantly (code fences, surrounding prose).

## Keys

- **Path:** typed in Settings → handed to the backend on **Save** → Windows Credential Manager (generic credential `Translate:service:<provider>`, this user, this PC) → cleared from the settings window. The field then shows a saved-key placeholder.
- **Never:** in config.json, logs, test-control output, or any renderer.
- **Old configs:** a key found in an older plaintext config.json is moved to the vault at startup.
- **Test connection** can use a typed, unsaved key for that one call.

## Local dictionary

CC-CEDICT (CC BY-SA 4.0, downloaded once from mdbg.net with your permission):
- **Build:** reduced to simplified headwords with one short gloss each; 121,511 headwords, 2.8 MB, sorted. Built by `backend/tools/build_cedict.py`.
- **Lookup:** binary search through a memory-mapped file, so no private memory.
- **Scope:** English target only; other languages go to the service.
- **Attribution:** in Settings › About and `translate_backend/data/cedict.LICENSE`.

## Hybrid cache (your choice: reuse common words, keep sentences out of storage)

| Kept | Where | Rule |
|---|---|---|
| Every translation | Memory, this session only (2,000 entries) | Gone when Translate quits |
| Reusable vocabulary | `%APPDATA%\Translate\cache\translations.bin`, **encrypted with Windows DPAPI** for your account, ≤ 20,000 entries, least-recently-used dropped | 1–4 Chinese characters only, **and** a CC-CEDICT headword, **and** a short translation |

- **Never persisted:** anything longer, anything with digits, Latin letters or symbols, and anything that isn't dictionary vocabulary (names, account names, made-up phrases).
- **Writes:** 5 s after changes, and at exit.
- **Controls:** *Clear cache* and the real entry count/size are in Settings › Privacy, and its text now says what is stored.

## Verification

| Suite | Result |
|---|---|
| Backend unit tests (incl. 17 new: wire formats, auth kinds, parsing, dictionary, cache rule + DPAPI, Credential Manager round trip with cleanup, pipeline against the mock) | **55 / 55** |
| End-to-end, packaged EXE, real pipeline vs local mock (`stage5_service_test.py`) | **19 / 19** |
| Stage-4 replay regression, packaged EXE | **40 / 40** |

The end-to-end suite checks, through the real app windows and the real Save path:
- **No key:** a dictionary word is translated and the footer shows *no service*.
- **Key handling:** saving a key leaves `config.json` without it, and requests carry it as Bearer.
- **Batching and cache:** one batch fills the rest of the list; the repeat list comes from the cache; 8 fast keys cost 1 request.
- **Errors:** a rejected key sets the footer and fails the row, and Retry recovers it. An unreachable service shows *offline* while dictionary words keep working. Local-only sends nothing.
- **Settings calls:** Test connection works in all three wire formats, and Load models works.
- **Languages:** a Japanese target uses the service.
- **Disk cache:**
  - only dictionary vocabulary is kept;
  - it survives a restart;
  - the sentence is not persisted;
  - the file is encrypted;
  - the log has no key and no candidate text.

Screenshots: `screenshots/stage5/settings-translation-{light,dark}.png`.

## Resources (packaged, same script and phases as stage 4; no real network calls, since no key)

| Scenario | Stage 4 after → Stage 5, private MB | CPU, % of one core |
|---|---|---|
| Live idle, attached to WeType | 119.0 → **117.5** (backend 58.8 → 57.5) | 0.04 → 0.14 (single-sample noise) |
| Idle, no window | 73.4 → 72.9 | 0.18 → 0.29 |
| Typing, 150 ms/keystroke | 145.3 → 157.9 * | 14.7 → 13.5–18.6 * |
| After idle release | 80.2 → 80.0 | 0.28 → 0.50 |

\* Within the noise band seen in Stage 4. Typing memory ranges 145–160 MB, and typing CPU was 13.5% and 13.7% in two quick runs and 18.6% in the full run.

One fix came out of measuring: the first build loaded `http.client`/SSL and the Windows certificate store at
startup, costing +3 to +5 MB even with no service configured. They now load on the first service call; import
cost went from 9.8 to 6.1 MB.

## Not verified yet

- **A real provider:** latency, quality, rate limits and real typing CPU/memory with network calls. This needs your key.
- **Corporate proxies and TLS interception:** the system proxy is honoured but untested.
- **The lower half of the Translation page** (model, *Load models*, *Test connection*) was not captured on screen, since scrolling needs input. The same code paths pass in the end-to-end suite.

## Next

1. **Rotate the OpenCode Go key you pasted in chat** (it is in the conversation history). Then open Settings › Translation and choose *OpenCode Go*:
   - Paste the new key into *Plan API key*.
   - Press **Test connection**, then **Save**. I can't type keys for you.
2. With your go-ahead, I'll run a live check with real typing against your service, plus the measurement with real network calls.

## 0.5.1 fixes (scrollbars, dropdowns, OpenCode Go, flicker)

All verified on a packaged EXE built to `app/out-next/` (`app/out/` was locked by the running app).

| Issue | Cause found | Fix | Verified |
|---|---|---|---|
| Model dropdown cut off, not scrollable | The shared Select popup had `overflow-hidden` and no height limit: 40 models started 844 px above the window | Popup capped to the room on its side (≤ 320 px) with a scrolling list; long names truncate; width bounded. Model controls no longer nested in one `<label>` | `settings_ui_probe.py`: 11/11 — every dropdown on Translation and General stays inside the window and in place for 60 frames; the 40-model list scrolls |
| Classic scrollbar with arrow buttons | `scrollbar-width: thin` makes Electron's Chromium on Windows draw the classic scrollbar | Thin themed `::-webkit-scrollbar` (4 px thumb in a 10 px gutter, no buttons); the standard properties only for engines without it. Also fixes the lead preview's scroll area | Same probe: gutter 10 px, standard `scrollbar-width: auto` |
| OpenCode Go fails (v1 and v2) | **Not the key.** (1) OpenCode Go rejects any request without an `x-opencode-session` header — 400 `MissingSessionID` before the key is checked. (2) It routes models to three endpoints (chat/completions; `/responses` for GPT/Grok/Muse; `/messages` for Claude/MiniMax/Qwen); we sent all to chat/completions. (3) `/zen/go/v2` doesn't exist (404); "OpenCode v2" on their site is their app, not an API version | Session header (stable id per app run) + our own user agent, as their docs ask; per-model routing incl. a new Responses API adapter; Settings › Test connection now shows the service's own error (HTTP status + type/message) and a specific message for a wrong endpoint (404) | Packaged app, fake key: chat, messages and responses routes all reach OpenCode's credential check (401 "Invalid credential"); v2 → 404 "endpoint not found". Your real key is not tested (it isn't saved — see below) |
| Flicker | Every keystroke turned each row back into a grey placeholder until the service answered (83 % of the time while typing at 300 ms service latency), and the 120 ms debounce was shorter than the gap between keystrokes, so each key sent a request (21 for 20 keys) whose late results re-rendered the panel. The always-on-top re-raise from 0.4 toggled the window's topmost state 250 ms after every update; no blink was measurable at ~40 fps, but it had no effect on WeType's UIAccess window and was removed | Rows still translating keep the previous text dimmed (≤ 600 ms after the last key; DESIGN §9); debounce 250 ms | `churn_probe.py`: placeholder time 83 % → 0 %, text→placeholder flips 4 → 0, requests 21 → 2. `flicker_probe.py` (black-backdrop frame grabs): 0 blink frames in 169 |

Regression on the same EXE: service suite 19/19, stage-4 replay 40/40, backend 57/57.

**Usage note on OpenCode Go.** Its docs say Go is designed for OpenCode and other coding agents ("Send typical coding agent
traffic"), and traffic is monitored for abuse. Translation requests from an input method are not coding-agent
traffic. The app now sends well-formed, self-identified requests, but whether this use is acceptable under your plan is
your call; OpenCode Zen (pay per use, same key per their docs) or a direct provider (DeepSeek, OpenAI…) avoid the question.

## Acceptance with the real service (OpenCode Go, your key) — 0.5.2

`app/scripts/stage5_real_test.py`: packaged EXE, replay source (synthetic candidates, no keyboard/mouse), real
pipeline, your saved provider settings and the key stored in Credential Manager (read by the app only). Model as you
configured it: `deepseek-v4.1-flash`. **15 / 15.**

| Check | Result |
|---|---|
| Short candidates (30 common words/phrases), as shipped | **30 / 30**: dictionary instantly, refined by the service in the same request |
| Same, service only | 30 / 30 |
| Long candidates (6 sentences, meaning keywords) | 6 / 6; lead preview opens for long #1 |
| Japanese / Korean targets | natural output in the target script (会議室 · 明日の午後3時に会議があります · 회의실 · 감사합니다), 1.8 / 2.3 s |
| Service response time | **p50 1.55 s, p95 2.16 s**, 14 requests, 0 errors |
| Continuous typing (12 keys, 150 ms apart) | **1 request**; final translation 2.1 s after the last key; 0 text → placeholder flips |
| Cache reuse | repeated list 5 / 5 from cache, 0 requests, 18 ms |
| Insertion sequence (recorded, not typed) | Esc, then exactly the translation shown in row 1 |

### Speed, memory and CPU on the real workload

| | Before (your log, 0.5.0) | After (0.5.2) |
|---|---|---|
| Service time per request | 1.6–7.2 s, two 8 s timeouts | p50 1.55 s, p95 2.16 s, max 2.0–2.2 s |
| Requests while typing 20 keys at 150 ms | 21 | 2 (12 keys: 1) |
| Rows blank while typing (300 ms service) | 83 % | 0 % |
| Typing CPU, % of one core (real service / simulated) | — / 16–17 | 12.6–14.8 / 16–17 |
| Typing memory, private | ≈ 150 MB | ≈ 150 MB (unchanged; within noise) |

What made the difference, measured per step:
1. **Reasoning off** (per model family; `docs` table in the 0.5.1 section): every OpenCode Go model thinks first by
   default — 3–10 s, 30 s worst. With it off: deepseek-v4-flash 1.7 s, deepseek-v4.1-flash 2.0 s, glm-5.3-flash 2.2 s,
   qwen3.8-flash 2.4 s, gpt-6-luna 2.4 s, kimi-k2.6 2.5 s. minimax-m2.7 can't turn it off (4.6 s). A service that refuses
   the switch gets one plain retry, and the model is remembered.
2. **Connection pre-warm + shared keep-alive pool**: the TLS handshake to opencode.ai is ≈ 480 ms; it now opens at the
   first keystroke that needs the service and overlaps the typing pause.
3. **Debounce 250 ms** (was 120, shorter than the gap between keystrokes) and **dimmed previous text** instead of
   placeholders.
4. **Dictionary refinement**: CC-CEDICT glosses (first sense, e.g. 加油 → "add oil") are shown at once and replaced by
   the service in the same request; glosses no longer start with "to ".

The remaining ≈ 1.5 s is the service's own time to first token (measured by streaming); words from the cache or
dictionary are instant.

## ⋯ menu "unclickable" — two causes, one fixed

1. **Bug (fixed):** the ⋯ menu opened, but the panel window didn't grow to fit it (121 px tall with the menu open), so
   the menu was drawn outside its window — invisible and unclickable. Regression from the stage-4 CPU change that
   measured a menu only when inserted, before floating-ui positions it. The panel now watches an open menu's position
   and size. Verified in the packaged EXE (`panel_menu_probe.py`, DOM events): the window grows (121 → 263 px), ⋯ and the
   row context menu open fully inside it, and ⋯ → Settings…, Pause, Hide panel all work.
2. **Placement (by design, your choice):** in the default position the ⋯ button lies under WeType's UIAccess window
   whenever the list has 1–3 rows (measured for 1–9 rows with the live window geometry); there no mouse click can reach
   it. With *Keep the panel clickable* it is reachable for every row count. The ⋯ actions also have shortcuts
   (Ctrl+Alt+P, Alt+0, Ctrl+Alt+O; Quit in Settings › About).

## Remaining issues before release packaging

- **Live run with the real IME and real service** (real typing, real click and Alt+N insertion) — needs your go-ahead.
- **Default placement vs. mouse**: rows and, for short lists, ⋯ can't be clicked under WeType's window. Options: make
  *Keep the panel clickable* the default, or keep it opt-in (current). A UIAccess build would remove the trade-off.
- **OpenCode Go usage policy**: designed for coding agents; this is translation traffic (see 0.5.1 section).
- **Model**: `deepseek-v4-flash` measured ≈ 0.3 s faster than your `deepseek-v4.1-flash`, same accuracy on this set.
- **Dictionary refinement** can change a word's text ≈ 1.5 s after it appears (when the service's choice differs);
  inserting before that inserts the dictionary gloss.
- **`app/out`** still holds 0.5.1 because Translate is running from it; 0.5.2 is in `app/out-next`.
- Not verified yet: Edge and other target apps, multi-monitor/DPI scaling, proxies, multi-hour soak, frozen backend
  (release step).

## Live runs with the real IME and real service (0.5.2, clickable mode)

| Run | Result | Notes |
|---|---|---|
| 1 | 20 / 24 | Click insertion: no insert (cause not captured); lead-preview check wrong for real text (fits its row — now N/A); stopped safely when the Claude window came to the front |
| 2 (instrumented) | 21 / 24 | **Click insertion worked** (pointer over the panel itself; test window not above it). New: one request hung → 2 rows failed after 8.2 s; **Alt+2 refused as stale** |

Both run-2 problems are fixed and covered by tests (backend 59 / 59):

1. **Stale after WeType re-segments the pinyin.** WeType re-sends the same keystrokes with new segmentation
   (`shijian` → `shi'jian`) without a new list; the adapter treated that as a keystroke and invalidated the list the
   panel still showed. Pinyin is now compared without segmentation marks.
2. **Service hangs (tail latency).** Requests normally take 1.5–2.4 s, but occasionally hang until the timeout (8 s in
   your settings). Requests still open after 3 s are **hedged**: the same request again on a fresh connection with a
   fresh OpenCode session id (a hang hit the duplicate too when it shared both); the first answer wins, late copies only
   fill the cache. After a timeout the session id is rotated. Logged per request: connection reused/new and age, so the
   next hang shows whether a dead kept-alive connection or a stuck route was the cause.

Real-service suite on the final build: 14 / 15 — all functional checks pass; p50 2.07 s against a 2.0 s target
(service variance; 1.55 s an hour earlier). 17 requests, 0 errors, no hedge needed in that run.

| 3 (final, after both fixes) | **24 / 24** | Real typing, real service: click and Alt+2 insertion (insert sequence 22 / 73 ms), Esc / Backspace / Space, Alt+0, idle release; 4 service requests 1.6–2.3 s, none hung |

Not observed live yet: a hang being rescued by a hedge (no request hung in run 3; covered by a unit test).
