# Qwen3.8-27B-oQ8-mtp — oMLX throughput benchmark

3 recorded run(s) aggregated. Profile: `code_python`, gen: 256.

Raw results:
- `Qwen3.8-27B-oQ8-mtp-20261115-134417-run1.json` (bench `bench-e347f65eda13`)
- `Qwen3.8-27B-oQ8-mtp-20261115-134417-run2.json` (bench `bench-8a4ba3d2e722`)
- `Qwen3.8-27B-oQ8-mtp-20261115-134417-run3.json` (bench `bench-9e06f4668dd1`)

## Single request — mean ± stddev (CV%) [min–max], n=3

| pp | tg | Prefill tok/s | Decode tok/s | TTFT ms |
|---|---|---|---|---|
| 1024 | 256 | 410.4 ± 2.4 (CV 0.6%) [408.6–413.1] | 59.6 ± 4.1 (CV 6.8%) [55.7–63.8] | 2495.0 ± 14.3 (CV 0.6%) [2478.9–2506.2] |
| 4096 | 256 | 435.3 ± 0.1 (CV 0.0%) [435.2–435.3] | 50.1 ± 0.8 (CV 1.6%) [49.2–50.7] | 9410.1 ± 1.1 (CV 0.0%) [9409.4–9411.3] |
| 32768 | 256 | 385.0 ± 0.0 (CV 0.0%) [385.0–385.0] | 70.6 ± 1.9 (CV 2.7%) [68.5–72.3] | 85107.6 ± 9.4 (CV 0.0%) [85100.7–85118.3] |
| 131072 | 256 | 270.5 ± 0.1 (CV 0.0%) [270.4–270.6] | 42.9 ± 1.0 (CV 2.3%) [41.9–43.9] | 484559.2 ± 100.9 (CV 0.0%) [484455.1–484656.5] |

## Batching (pp1024) — mean ± stddev, n=3

Note: `scheduler.max_concurrent_requests` is 4 — the 8× run sends 8 requests but the scheduler admits 4 and queues the rest, so "8×" is 8 requests through a 4-wide pipe (multiple waves), not true parallelism. "vs 1x" is aggregate speedup; per-request latency spans the waves.

| Batch | pp | Aggregate decode tok/s | vs 1x |
|---|---|---|---|
| 1x (single) | 1024 | 59.6 ± 0.0 (CV 0.0%) | 1.00 |
| 2x | 1024 | 85.3 ± 0.7 (CV 0.8%) [84.7–86.0] | 1.43 |
| 4x | 1024 | 112.9 ± 0.8 (CV 0.7%) [112.2–113.8] | 1.89 |
| 8x | 1024 | 252.7 ± 6.1 (CV 2.4%) [245.9–257.7] | 4.24 |

## Per-run tables (n=3)

### Qwen3.8-27B-oQ8-mtp-20261115-134417-run1.json (`bench-e347f65eda13`)

| pp | tg | Prefill tok/s | Decode tok/s | TTFT ms |
|---|---|---|---|---|
| 1024 | 256 | 413.1 | 55.7 | 2478.9 |
| 4096 | 256 | 435.2 | 50.5 | 9411.3 |
| 32768 | 256 | 385.0 | 72.3 | 85103.9 |
| 131072 | 256 | 270.5 | 42.9 | 484566.0 |

### Qwen3.8-27B-oQ8-mtp-20261115-134417-run2.json (`bench-8a4ba3d2e722`)

| pp | tg | Prefill tok/s | Decode tok/s | TTFT ms |
|---|---|---|---|---|
| 1024 | 256 | 408.6 | 63.8 | 2506.2 |
| 4096 | 256 | 435.3 | 49.2 | 9409.4 |
| 32768 | 256 | 385.0 | 68.5 | 85100.7 |
| 131072 | 256 | 270.6 | 43.9 | 484455.1 |

### Qwen3.8-27B-oQ8-mtp-20261115-134417-run3.json (`bench-9e06f4668dd1`)

| pp | tg | Prefill tok/s | Decode tok/s | TTFT ms |
|---|---|---|---|---|
| 1024 | 256 | 409.6 | 59.4 | 2499.8 |
| 4096 | 256 | 435.3 | 50.7 | 9409.5 |
| 32768 | 256 | 385.0 | 71.0 | 85118.3 |
| 131072 | 256 | 270.4 | 41.9 | 484656.5 |

> oMLX throughput benchmark via the admin API, MTP enabled, server defaults, code_python prompts, 256 generated tokens, decode = single-request gen_tps, batch = aggregate tg_tps at pp1024. n=3 run(s), reported as mean ± stddev (CV%) [min–max].
