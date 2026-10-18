# Native WeType transport

Build from the repository root with `cmd /c backend\native\build.cmd` using the x64 MSVC Build Tools.
The build vendors MinHook 1.3.4 under `vendor/minhook`, produces a content-versioned observer DLL and
`TranslateInject.exe`, and selects that DLL in `translate_backend/wetype/native/manifest.json`.
Packaging runs the build and includes the MinHook license. Native artifacts are ignored by Git.

The injector checks the target's executable name, x64 architecture and process creation time. It loads
the DLL from a content-versioned per-user runtime cache, avoiding installation-directory locks.
The default target is the current-session `wetype_server.exe`; integration tests use the owned
`feasibility_fixture.exe`. No shell or candidate parser runs in the target process.

The observer copies matching pipe writes into a 2,099,776-byte ring. Sixty-four 32 KiB chunks and a
maximum 256 KiB write keep allocations bounded. Python dispatch permits at most eight pending byte/gap
events. Overflow or ambiguous concurrent writes increments a generation counter. Python rejects stale
insertion immediately, clears the old composition and requires a fresh composition after acknowledging
the gap. The original write proceeds even when the observer drops data.

Every connection is a lease with unique IPC names and an increasing source epoch. Reconnect resolves
the PID again; creation-time checking prevents attaching to a reused PID. Stop or five seconds without
a controller heartbeat disables the hook, waits for active calls, then releases IPC views and handles.
The DLL and trampoline remain resident until the input method exits, because unloading hook code while
another thread may hold an instruction pointer is unsafe. A blocked original write can delay final lease
cleanup; Python does not block indefinitely or free memory under that call.

The fallback is explicit: `TRANSLATE_WETYPE_TRANSPORT=frida`. The default does not load Frida.
Microsoft Pinyin still uses the stable full UI Automation path; its slim ABI experiment is opt-in only.

Synthetic integration: set `TRANSLATE_NATIVE_CACHE` to a workspace scratch directory, build the owned
fixture from `backend/native/tests/fixture.c` with `cmd /c backend\native\build.cmd --tests`, then run
`python -X utf8 -B backend/tools/native_transport_check.py`. No desktop keystrokes or external service
requests are used. The separate paired memory comparison is
`python -X utf8 -B app/scripts/native_memory_compare.py --baseline <extracted-0.2.3-folder>`;
download the baseline release separately from GitHub. It uses a localhost mock translation service.
