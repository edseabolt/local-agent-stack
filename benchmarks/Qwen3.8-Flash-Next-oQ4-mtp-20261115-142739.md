# Qwen3.8-Flash-Next-oQ4-mtp — oMLX throughput benchmark

3 recorded run(s) aggregated. Profile: `code_python`, gen: 256.

Raw results:
- `Qwen3.8-Flash-Next-oQ4-mtp-20261115-142739-run1.json` (bench `bench-d618a1b19ea3`)
- `Qwen3.8-Flash-Next-oQ4-mtp-20261115-142739-run2.json` (bench `bench-42d73caa5fb3`)
- `Qwen3.8-Flash-Next-oQ4-mtp-20261115-142739-run3.json` (bench `bench-95cdd44fb01d`)

## Single request — mean ± stddev (CV%) [min–max], n=3

| pp | tg | Prefill tok/s | Decode tok/s | TTFT ms |
|---|---|---|---|---|
| 1024 | 256 | 1125.9 ± 8.9 (CV 0.8%) [1115.7–1131.7] | 103.6 ± 7.4 (CV 7.1%) [97.9–111.9] | 909.5 ± 7.2 (CV 0.8%) [904.8–917.8] |
| 4096 | 256 | 1339.0 ± 77.3 (CV 5.8%) [1249.7–1385.1] | 88.1 ± 12.9 (CV 14.6%) [76.6–102.0] | 3066.1 ± 183.2 (CV 6.0%) [2957.1–3277.6] |
| 32768 | 256 | 1358.2 ± 2.8 (CV 0.2%) [1356.0–1361.3] | 92.1 ± 0.3 (CV 0.3%) [91.8–92.4] | 24126.7 ± 49.7 (CV 0.2%) [24070.5–24165.0] |
| 131072 | 256 | 1317.5 ± 1.6 (CV 0.1%) [1316.1–1319.3] | 58.2 ± 0.9 (CV 1.6%) [57.4–59.2] | 99485.0 ± 120.7 (CV 0.1%) [99353.3–99590.5] |

## Batching (pp1024) — mean ± stddev, n=3

Note: `scheduler.max_concurrent_requests` is 4 — the 8× run sends 8 requests but the scheduler admits 4 and queues the rest, so "8×" is 8 requests through a 4-wide pipe (multiple waves), not true parallelism. "vs 1x" is aggregate speedup; per-request latency spans the waves.

| Batch | pp | Aggregate decode tok/s | vs 1x |
|---|---|---|---|
| 1x (single) | 1024 | 103.6 ± 0.0 (CV 0.0%) | 1.00 |
| 2x | 1024 | 100.4 ± 15.3 (CV 15.2%) [82.7–109.2] | 0.97 |
| 4x | 1024 | 160.7 ± 7.4 (CV 4.6%) [153.8–168.5] | 1.55 |
| 8x | 1024 | 347.2 ± 10.7 (CV 3.1%) [335.2–355.9] | 3.35 |

## Per-run tables (n=3)

### Qwen3.8-Flash-Next-oQ4-mtp-20261115-142739-run1.json (`bench-d618a1b19ea3`)

| pp | tg | Prefill tok/s | Decode tok/s | TTFT ms |
|---|---|---|---|---|
| 1024 | 256 | 1130.4 | 111.9 | 905.9 |
| 4096 | 256 | 1249.7 | 76.6 | 3277.6 |
| 32768 | 256 | 1357.2 | 92.4 | 24144.5 |
| 131072 | 256 | 1319.3 | 58.0 | 99353.3 |

### Qwen3.8-Flash-Next-oQ4-mtp-20261115-142739-run2.json (`bench-42d73caa5fb3`)

| pp | tg | Prefill tok/s | Decode tok/s | TTFT ms |
|---|---|---|---|---|
| 1024 | 256 | 1115.7 | 97.9 | 917.8 |
| 4096 | 256 | 1385.1 | 102.0 | 2957.1 |
| 32768 | 256 | 1356.0 | 92.0 | 24165.0 |
| 131072 | 256 | 1316.1 | 57.4 | 99590.5 |

### Qwen3.8-Flash-Next-oQ4-mtp-20261115-142739-run3.json (`bench-95cdd44fb01d`)

| pp | tg | Prefill tok/s | Decode tok/s | TTFT ms |
|---|---|---|---|---|
| 1024 | 256 | 1131.7 | 101.0 | 904.8 |
| 4096 | 256 | 1382.2 | 85.8 | 2963.5 |
| 32768 | 256 | 1361.3 | 91.8 | 24070.5 |
| 131072 | 256 | 1317.2 | 59.2 | 99511.1 |

> oMLX throughput benchmark via the admin API, MTP enabled, server defaults, code_python prompts, 256 generated tokens, decode = single-request gen_tps, batch = aggregate tg_tps at pp1024. n=3 run(s), reported as mean ± stddev (CV%) [min–max].
