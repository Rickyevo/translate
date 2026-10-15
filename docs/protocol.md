# Host ↔ backend protocol (v1)

The Electron main process (**host**) launches the Python backend as a child process and talks to it
over **JSON Lines on stdio**.

| Channel | Carries |
|---|---|
| backend **stdout** | Protocol messages only: one JSON object per line, UTF-8, `\n`-terminated |
| backend **stdin** | Host → backend messages, same framing |
| backend **stderr** | Diagnostics only. The host forwards them to its log and never parses them |

Implementation:
- Host side: `app/src/main/backend.ts`.
- Backend side: `backend/translate_backend/protocol.py` and `__main__.py`.

## Envelope

```json
{"v": 1, "type": "candidates", "id": 7, "...": "..."}
```

- `v`: protocol version (integer). The backend announces it in `ready`, and the host refuses
  versions it does not know.
- `type`: message type, listed below.
- `id`: optional. Set on host requests that expect a reply; the reply echoes it. Unsolicited events
  have no `id`.
- `gen`: **candidate-list generation**. It is a monotonically increasing integer set by the backend,
  one per new candidate list. Translation results and insert requests carry it, and anything with an
  outdated `gen` is ignored on both sides.

Rules:
- A malformed line never ends the session. The backend answers with
  `error{code:"bad_message"}` and continues.
- The host discards unparseable lines and logs only their length.
- Lines longer than 1 MiB are a framing error.

## Backend → host

| type | Fields | When |
|---|---|---|
| `ready` | `version`, `protocol`, `pid`, `dpiAware`, `testMode`, `adapters[]` (`wetype` · `wetype-replay` · `sim`), `translationMode` (`simulated` · `fixture`) | Once at start, before any other message |
| `candidates` | `gen`, `pinyin`, `items[{n,text,state}]`, `anchor{x,y,w,h}`, `foreground{pid,exe}` | Every new candidate list. `anchor` is the IME candidate **row** in **physical** pixels. A `candidates` with the **current** `gen` is a reposition (the IME window moved): the host keeps its items and translations and only re-lays out |
| `translation` | `gen`, `n`, `state` (`done`·`failed`·`noEntry`·`loading` after Retry), `text?`, `source?` (`cache`·`dict`·`ai`; `sim` in replay tests), `reason?` (`timeout`·`network`·`auth`·`rate`·`http`·`parse`·`refused`·`internal`·`noEntry`·`noEntryLang`) | Per item, as soon as it is known: cache and dictionary hits in the same tick as the list, service results after one batch request |
| `composition.end` | `gen` | The composition really ended: committed, cleared/cancelled, candidate window hidden, focus moved, IME disconnected, or paused. The panel hides. **Not** sent for pinyin edits (see below) |
| `insert.result` | `id`, `ok`, `gen`, `n`, `error?` (`stale`·`unavailable`·`denied`·`blocked`·`ime`·`modifiers`), `target{exe}` | Reply to `insert` |
| `config.ack` | `id`, `config` | Reply to `config.set` (the effective backend config) |
| `status` | `paused` / `ime{state,code}` (`connected`·`waiting`·`failed`) + `translationMode` (`live`·`simulated`·`fixture`) / `service{state}` (`ok`·`noService`·`localOnly`·`offline`·`auth`·`failed`) | State changes the user may need to know about; `service` drives the panel footer |
| `secret.ack` | `id`, `ok`, `provider` | Reply to `secret.set` |
| `secret.status` | `id`, `keys{provider: bool}` | Which providers have a key stored (never the keys) |
| `service.test` | `id`, `ok`, `ms?`, `error?` (`noKey`·`badUrl`·`noModel`·`auth`·`network`·`timeout`·`rate`·`http`·`parse`·`refused`), `status?` | Reply to `service.test` (one real request) |
| `service.models` | `id`, `ok`, `models[]?`, `error?` | Reply to `service.models` |
| `cache.stats` | `id`, `count`, `bytes`, `memory` | Reply to `cache.stats` / `cache.clear` (disk entries, file size, session entries) |
| `error` | `code`, `message` (user-presentable), `detail?` (diagnostic, no user text) | Anything explainable |
| `pong` | `id`, `t` | Reply to `ping` |
| `bye` | `id` | Reply to `shutdown`, just before exit |

## Host → backend

| type | Fields | Effect |
|---|---|---|
| `config.set` | `id`, `config{target,count,denylist,localOnly,localDict,provider,services{id:{endpoint,model,protocol,auth,authName}},timeout,jsonMode,dataDir}` | Merge into the backend config; replies `config.ack`. Never contains keys |
| `secret.set` | `id`, `provider`, `key` | Store the key in Windows Credential Manager (`Translate:service:<provider>`); an empty key deletes it. **Keys travel only here**, host → backend, and never go back to the host or any renderer |
| `secret.status` | `id` | Which providers have a key |
| `service.test` / `service.models` | `id`, `service{provider,endpoint,model,protocol,auth,authName,jsonMode}`, `key?` | Test connection / list models with draft settings; `key` is a key typed but not yet saved (used for this call only), else the stored key. Runs off the dispatch thread |
| `cache.stats` / `cache.clear` | `id` | Translation cache size / clear it (memory and disk) |
| `retry` | `gen`, `n` | Translate a failed or no-entry item again (row click, context menu, preview *Retry*) |
| `insert` | `id`, `gen`, `n` | Insert item `n` of list `gen` into the focused control (see below) |
| `composition.cancel` | — | Drop the current list |
| `pause` / `resume` | `id?` | Stop or start producing candidates |
| `ping` | `id` | Liveness |
| `shutdown` | `id` | Reply `bye`, then exit 0 |
| `debug.*` | | **Test mode only** (`--test`), refused otherwise. Fixture source: `debug.compose`, `debug.end`, `debug.typing`, `debug.foreground`. Replay source (`--test --source=wetype-replay`): `debug.wetype.connection{state,epoch?}`, `debug.wetype.window{rect,foreground}`, `debug.wetype.bytes{steps[]\|b64, chunk?, epoch?}`, `debug.wetype.typing{interval,duration}`, `debug.input{onEscape?,held?,clear?}` (insertion is recorded, never sent to the desktop) |

## Generations within one composition

Each keystroke changes the pinyin and produces a new list. The backend invalidates the current list the
moment the pinyin changes (an `insert` against it is answered `stale`), but it does not send
`composition.end`: the host keeps the panel up, with its grow-only width and lead-preview state, until the
replacement `candidates` arrives a few milliseconds later. The host ignores a `candidates` older than the one
it shows. `translation` results are applied only if their `gen` is current, in the backend and again in the host.

## Insertion

1. Reject if `gen` is stale (`stale`), the item has no translation (`unavailable`), the foreground
   app is on the denylist or the focused control is a password field (`denied`), or the foreground
   window is no longer the one the composition belongs to (`stale`).
2. If Alt is still held (Alt+N hotkey), tap an unassigned virtual key (0xE8) so the later Alt-up is
   not a lone Alt tap, which would open the target app's menu bar. Then wait up to 1 s for all
   modifiers to be released; if any is still down, refuse (`modifiers`), because Esc with Alt held
   would be Alt+Esc.
3. Cancel the IME's pinyin composition: send **Esc**, only while WeType's candidate window is visible
   (so the IME, not the app, receives it). Then wait up to 500 ms for confirmation — the pipe reports the
   composition cleared, or the candidate window hides — processing only IME events meanwhile (other
   messages are deferred in order). No confirmation → refuse (`ime`) and type nothing. Then 15 ms settle,
   and re-check the foreground window.
4. Type the text with `SendInput` `KEYEVENTF_UNICODE` (UTF-16 units, surrogate pairs included;
   `\n` becomes Enter).
5. If Windows accepts fewer events than sent, report `blocked`. This is typically UIPI: the target is
   elevated and we are not.

## Lifecycle and supervision

- The host spawns `python -E -s -B -m translate_backend` with `cwd` = the backend directory. A frozen
  executable replaces it in the release build.
- The backend never polls. One dispatch loop blocks on a queue fed by the stdin reader and timers.
- **Shutdown**: the host sends `shutdown`, closes stdin, and waits 1.5 s, then kills the process.
  EOF on stdin also makes the backend exit. The backend leaves via `os._exit` after flushing, because
  CPython can crash on Windows when it finalizes while a daemon thread is blocked reading stdin.
- **Crash**: the host restarts with exponential backoff (0.25 s → 8 s). After 5 crashes in 60 s it
  stops and reports `failed` to the user.
- **Logs**:
  - The backend logs counts, generations, timings and error classes only — candidate text, pinyin and
    translations are never logged, at any level. Uncaught exceptions are logged by type only (their
    messages could carry text). At each composition end it logs `lists/pinyin/dup/dropped` counts, used to
    verify the IME's event ordering.
  - The host log lives in `%APPDATA%/Translate/logs` and is capped at 1 MiB with one rotation.
