## Default build (software rendering) — 24 logical CPUs

| Phase | Processes | Working set (MB) | Private (MB) | USS (MB) | of which backend private | CPU avg (% of one core) | CPU p95 | Backend CPU |
|---|---|---|---|---|---|---|---|---|
| Background idle (no window yet) | 5 | 197.7 | **70.0** | 48.2 | 10.9 | 0.11 | 0.0 | 0.0 |
| Continuous typing | 6 | 350.9 | **141.3** | 104.8 | 11.2 | 15.92 | 36.16 | 1.28 |
| Idle after typing (panel kept) | 6 | 351.0 | **141.4** | 105.3 | 10.9 | 0.08 | 0.0 | 0.0 |
| Long-translation preview open | 6 | 349.2 | **135.5** | 99.4 | 10.9 | 0.32 | 1.61 | 0.0 |
| Settings open | 7 | 457.9 | **174.7** | 124.8 | 10.9 | 0.16 | 1.61 | 0.0 |
| Settings closed again | 6 | 352.8 | **135.9** | 97.5 | 11.0 | 0.32 | 1.61 | 0.0 |

Private memory by process (MB, average over the phase):

| Phase | main | gpu | utility:mojom | renderer:panel | renderer:settings | renderer:preview | backend |
|---|---|---|---|---|---|---|---|
| Background idle (no window yet) | 33.2 | 13.8 | 10.9 | — | — | — | 10.9 |
| Continuous typing | 39.0 | 15.4 | 11.3 | 63.4 | — | — | 11.2 |
| Idle after typing (panel kept) | 39.3 | 15.1 | 11.3 | 63.7 | — | — | 10.9 |
| Long-translation preview open | 39.7 | 15.3 | 11.3 | 57.1 | — | — | 10.9 |
| Settings open | 40.8 | 17.3 | 11.3 | 54.3 | 38.9 | — | 10.9 |
| Settings closed again | 40.8 | 17.3 | 11.3 | 54.3 | — | — | 11.0 |

Sustained session: 17.1 min of typing bursts, previews and settings open/close cycles.

- Private at idle checkpoints: first 148.9 MB, last 154.1 MB
- Linear trend: total private 16.97 MB/h, working set 25.43 MB/h, backend 0.04 MB/h
- Checkpoints (MB): 148.9, 148.5, 150.2, 148.8, 150.7, 153.6, 151.3, 151.2, 152.7, 151.4, 151.7, 154.4, 151.3, 152.2, 155.3, 153.3, 152.0, 153.2, 154.2, 154.1

## Variants (same phases)

| Variant | Idle, no window | Typing | Idle after typing | Preview open | Settings open | Settings closed | Typing CPU (% core) |
|---|---|---|---|---|---|---|---|
| Software rendering (default) | 70.0 | 141.3 | 141.4 | 135.5 | 174.7 | 135.9 | 15.92 |
| GPU rendering (`--gpu`) | 117.3 | 214.1 | 208.3 | 213.4 | 278.2 | 224.3 | 9.52 |
| Preview in its own renderer | 74.1 | 144.7 | 132.7 | 161.9 | 202.1 | 162.2 | 17.84 |
| Release panel after 30 s idle | 73.2 | 144.5 | 102.3 | 109.5 | 124.7 | 85.6 | 14.14 |

Values are total private MB (Electron group + backend), averaged over each phase.