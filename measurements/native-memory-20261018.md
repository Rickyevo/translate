# Native backend memory comparison — 2026-10-18

The native transport adds bounded queues, explicit gap invalidation, automatic reconnection, process-identity
checks and safe shutdown. This record describes the 0.2.3 candidate that became 0.2.4. To repeat the comparison,
pass an extracted 0.2.3 release folder with `--baseline`. Source paths in the result files are repository-relative.

## Memory

Both builds ran for 73 seconds: three seconds of warmup, two 25-second typing phases and two ten-second idle phases.
Both loaded the full Microsoft UI Automation implementation, the HTTPS context and 3,559 public-dictionary cache
fixtures. They received identical real pipe writes and used the same localhost mock translation service.
Each processed 240 candidate updates and 48 completed translation batches, with zero failed rows and empty
candidate and translation queues at the end.

| Backend working set, MiB | Original | Native candidate | Reduction |
|---|---:|---:|---:|
| After warmup | 116.47 | 57.64 | 50.51% |
| Typing | 117.01 | 58.72 | 49.81% |
| Idle after typing | 117.07 | 58.84 | 49.74% |

Private memory was about 73.12 → 34.93 MiB while typing and 73.08 → 34.96 MiB while idle.
A separate single reading after real desktop testing showed 52.74 MiB backend working set.

Figures include the backend and measurement driver, and exclude the host, WebView2 and input-method processes.
They must not be presented as a 50% reduction for the entire application. The earlier approximately 150 MB
observation came from a different session and usage history. This is a short comparison, not a long-duration soak.

## Performance and compatibility

| Matched-load timing | Original | Native candidate |
|---|---:|---:|
| Candidate arrival median | 16.206 ms | 16.235 ms |
| Candidate arrival P95 | 17.593 ms | 17.577 ms |
| Translation completion median | 304.126 ms | 302.793 ms |
| Translation completion P95 | 317.452 ms | 313.616 ms |
| Pipe write P95 | 0.247 ms | 0.038 ms |

Candidate timings include fixture pipe creation and its rate limiter. Translation timings include debounce and
the localhost mock service, and do not predict cloud-service latency. No noticeable latency regression was observed.
Mean typing CPU use was approximately 1.03% → 1.75% of one core; idle CPU use was 0.08% → 0.78% of one core.
Other regression tests ran during the comparison, so these readings do not establish zero CPU overhead.

The real desktop check used an independent input field. WeChat Input Method and Microsoft Pinyin each produced
five candidates, completed local-dictionary translations, and successfully inserted the first translation with Alt+1.
Microsoft Pinyin's first composition after switching also worked. No candidate or inserted text was saved.

The tested candidate reused the original frontend executable, SHA256:
`6b5342f57bcc507139e1fe9f8a5ca7f2e4dc72eeea73f74dcee20411d35e36ea`.
The 0.2.4 version bump rebuilds that executable; this hash identifies the measured candidate, not the final release.
Interface, placement and Win32 candidate-position code were unchanged.

## Recovery checks

- Backend regression: 82/82. WeChat frontend replay: 40/40. Microsoft Pinyin frontend replay: 15/15.
- Three cycles of synchronous WriteFile, NtWriteFile and asynchronous writes: 60 writes per cycle matched byte for byte.
- A 256 KiB write split into eight packets and reassembled completely.
- With the consumer paused, all 100 original writes were delivered. The ring explicitly reported 36 dropped
  observations, insertion rejected stale candidates immediately, and a fresh composition recovered correctly.
- Python dispatch held at most eight unacknowledged byte/gap events.
- Process exit, a replacement PID, controller termination and heartbeat expiry all allowed reconnection.
- Shutdown cancelled attachment. Health checks and connection shutdown shared a lock to avoid accessing an unmapped view.

Microsoft Pinyin uses the full UI Automation path by default. The experimental minimal ABI's first-input issue
was excluded from the default implementation.

The observer DLL is approximately 116 KiB. Shutdown disables the hook and releases shared-memory views and handles;
code remains resident until the input method exits to avoid unloading instructions another thread could still use.
A cached DLL may therefore remain locked until that natural exit.

Evidence: `native-memory-paired-20261018.json`, `native-memory-summary-20261018.json` and
`native-transport-integration-20261018.json`.
