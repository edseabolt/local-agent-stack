# Ornith-1.5-35B-A3B-oQ8-mtp — oMLX throughput benchmark

3 recorded run(s) aggregated. Profile: `code_python`, gen: 256.

Raw results:
- `Ornith-1.5-35B-A3B-oQ8-mtp-20261115-132952-run1.json` (bench `bench-4a3b56296456`)
- `Ornith-1.5-35B-A3B-oQ8-mtp-20261115-132952-run2.json` (bench `bench-41e61f0c1383`)
- `Ornith-1.5-35B-A3B-oQ8-mtp-20261115-132952-run3.json` (bench `bench-03b3fbcff7cf`)

## Single request — mean ± stddev (CV%) [min–max], n=3

| pp | tg | Prefill tok/s | Decode tok/s | TTFT ms |
|---|---|---|---|---|
| 1024 | 256 | 2331.1 ± 62.9 (CV 2.7%) [2261.1–2383.0] | 131.5 ± 10.9 (CV 8.3%) [122.4–143.5] | 439.5 ± 12.0 (CV 2.7%) [429.7–452.9] |
| 4096 | 256 | 3085.8 ± 211.0 (CV 6.8%) [2842.3–3215.1] | 154.3 ± 30.1 (CV 19.5%) [125.7–185.7] | 1331.7 ± 94.8 (CV 7.1%) [1274.0–1441.1] |
| 32768 | 256 | 2290.5 ± 7.8 (CV 0.3%) [2283.3–2298.7] | 157.5 ± 6.9 (CV 4.4%) [152.1–165.3] | 14306.4 ± 48.5 (CV 0.3%) [14254.8–14351.1] |
| 131072 | 256 | 1107.8 ± 2.4 (CV 0.2%) [1105.5–1110.2] | 102.2 ± 2.1 (CV 2.1%) [100.6–104.6] | 118316.3 ± 255.4 (CV 0.2%) [118058.0–118568.7] |

## Batching (pp1024) — mean ± stddev, n=3

Note: `scheduler.max_concurrent_requests` is 4 — the 8× run sends 8 requests but the scheduler admits 4 and queues the rest, so "8×" is 8 requests through a 4-wide pipe (multiple waves), not true parallelism. "vs 1x" is aggregate speedup; per-request latency spans the waves.

| Batch | pp | Aggregate decode tok/s | vs 1x |
|---|---|---|---|
| 1x (single) | 1024 | 131.5 ± 0.0 (CV 0.0%) | 1.00 |
| 2x | 1024 | 208.3 ± 24.7 (CV 11.8%) [184.8–234.0] | 1.58 |
| 4x | 1024 | 264.8 ± 18.8 (CV 7.1%) [243.3–278.0] | 2.01 |
| 8x | 1024 | 558.7 ± 10.1 (CV 1.8%) [547.7–567.5] | 4.25 |

## Per-run tables (n=3)

### Ornith-1.5-35B-A3B-oQ8-mtp-20261115-132952-run1.json (`bench-4a3b56296456`)

| pp | tg | Prefill tok/s | Decode tok/s | TTFT ms |
|---|---|---|---|---|
| 1024 | 256 | 2383.0 | 128.5 | 429.7 |
| 4096 | 256 | 2842.3 | 125.7 | 1441.1 |
| 32768 | 256 | 2283.3 | 165.3 | 14351.1 |
| 131072 | 256 | 1105.5 | 101.5 | 118568.7 |

### Ornith-1.5-35B-A3B-oQ8-mtp-20261115-132952-run2.json (`bench-41e61f0c1383`)

| pp | tg | Prefill tok/s | Decode tok/s | TTFT ms |
|---|---|---|---|---|
| 1024 | 256 | 2349.2 | 122.4 | 435.9 |
| 4096 | 256 | 3200.1 | 185.7 | 1280.0 |
| 32768 | 256 | 2289.4 | 152.1 | 14313.2 |
| 131072 | 256 | 1107.8 | 104.6 | 118322.3 |

### Ornith-1.5-35B-A3B-oQ8-mtp-20261115-132952-run3.json (`bench-03b3fbcff7cf`)

| pp | tg | Prefill tok/s | Decode tok/s | TTFT ms |
|---|---|---|---|---|
| 1024 | 256 | 2261.1 | 143.5 | 452.9 |
| 4096 | 256 | 3215.1 | 151.4 | 1274.0 |
| 32768 | 256 | 2298.7 | 155.2 | 14254.8 |
| 131072 | 256 | 1110.2 | 100.6 | 118058.0 |

> oMLX throughput benchmark via the admin API, MTP enabled, server defaults, code_python prompts, 256 generated tokens, decode = single-request gen_tps, batch = aggregate tg_tps at pp1024. n=3 run(s), reported as mean ± stddev (CV%) [min–max].
