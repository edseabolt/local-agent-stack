# GLM-5.3-Flash-oQ6-mtp — oMLX throughput benchmark

3 recorded run(s) aggregated. Profile: `code_python`, gen: 256.

Raw results:
- `GLM-5.3-Flash-oQ6-mtp-20261115-125007-run1.json` (bench `bench-de44c74c7501`)
- `GLM-5.3-Flash-oQ6-mtp-20261115-125007-run2.json` (bench `bench-6d8c452c0836`)
- `GLM-5.3-Flash-oQ6-mtp-20261115-125007-run3.json` (bench `bench-a3b1f2752c29`)

## Single request — mean ± stddev (CV%) [min–max], n=3

| pp | tg | Prefill tok/s | Decode tok/s | TTFT ms |
|---|---|---|---|---|
| 1024 | 256 | 486.0 ± 1.9 (CV 0.4%) [483.8–487.2] | 41.4 ± 1.9 (CV 4.6%) [40.1–43.6] | 2106.9 ± 8.4 (CV 0.4%) [2101.7–2116.6] |
| 4096 | 256 | 560.1 ± 2.4 (CV 0.4%) [557.4–562.1] | 43.2 ± 1.9 (CV 4.3%) [41.0–44.3] | 7312.6 ± 32.3 (CV 0.4%) [7286.4–7348.6] |
| 32768 | 256 | 521.6 ± 0.7 (CV 0.1%) [520.9–522.2] | 50.7 ± 1.5 (CV 2.9%) [49.4–52.3] | 62816.5 ± 82.9 (CV 0.1%) [62747.1–62908.3] |
| 131072 | 256 | 505.3 ± 0.3 (CV 0.1%) [505.0–505.6] | 70.6 ± 0.1 (CV 0.1%) [70.6–70.7] | 259404.2 ± 162.8 (CV 0.1%) [259237.5–259562.7] |

## Batching (pp1024) — mean ± stddev, n=3

Note: `scheduler.max_concurrent_requests` is 4 — the 8× run sends 8 requests but the scheduler admits 4 and queues the rest, so "8×" is 8 requests through a 4-wide pipe (multiple waves), not true parallelism. "vs 1x" is aggregate speedup; per-request latency spans the waves.

| Batch | pp | Aggregate decode tok/s | vs 1x |
|---|---|---|---|
| 1x (single) | 1024 | 41.4 ± 0.0 (CV 0.0%) | 1.00 |
| 2x | 1024 | 42.4 ± 1.5 (CV 3.6%) [40.7–43.7] | 1.02 |
| 4x | 1024 | 56.7 ± 0.7 (CV 1.2%) [56.0–57.4] | 1.37 |
| 8x | 1024 | 121.5 ± 1.7 (CV 1.4%) [120.2–123.5] | 2.94 |

## Per-run tables (n=3)

### GLM-5.3-Flash-oQ6-mtp-20261115-125007-run1.json (`bench-de44c74c7501`)

| pp | tg | Prefill tok/s | Decode tok/s | TTFT ms |
|---|---|---|---|---|
| 1024 | 256 | 487.2 | 43.6 | 2101.7 |
| 4096 | 256 | 562.1 | 41.0 | 7286.4 |
| 32768 | 256 | 521.8 | 52.3 | 62794.0 |
| 131072 | 256 | 505.0 | 70.7 | 259562.7 |

### GLM-5.3-Flash-oQ6-mtp-20261115-125007-run2.json (`bench-6d8c452c0836`)

| pp | tg | Prefill tok/s | Decode tok/s | TTFT ms |
|---|---|---|---|---|
| 1024 | 256 | 483.8 | 40.1 | 2116.6 |
| 4096 | 256 | 557.4 | 44.3 | 7348.6 |
| 32768 | 256 | 522.2 | 50.4 | 62747.1 |
| 131072 | 256 | 505.3 | 70.6 | 259412.3 |

### GLM-5.3-Flash-oQ6-mtp-20261115-125007-run3.json (`bench-a3b1f2752c29`)

| pp | tg | Prefill tok/s | Decode tok/s | TTFT ms |
|---|---|---|---|---|
| 1024 | 256 | 487.0 | 40.5 | 2102.5 |
| 4096 | 256 | 560.9 | 44.2 | 7302.7 |
| 32768 | 256 | 520.9 | 49.4 | 62908.3 |
| 131072 | 256 | 505.6 | 70.6 | 259237.5 |

> oMLX throughput benchmark via the admin API, MTP enabled, server defaults, code_python prompts, 256 generated tokens, decode = single-request gen_tps, batch = aggregate tg_tps at pp1024. n=3 run(s), reported as mean ± stddev (CV%) [min–max].
