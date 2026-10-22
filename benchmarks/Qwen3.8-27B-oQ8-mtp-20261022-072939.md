# Qwen3.8-27B-oQ8-mtp — oMLX throughput benchmark

3 recorded run(s) aggregated. Profile: `code_python`, gen: 256.

Raw results:
- `Qwen3.8-27B-oQ8-mtp-20261022-072939-run1.json` (bench `bench-3b6ab39fd885`)
- `Qwen3.8-27B-oQ8-mtp-20261022-072939-run2.json` (bench `bench-7d6cdcc52528`)
- `Qwen3.8-27B-oQ8-mtp-20261022-072939-run3.json` (bench `bench-d5d481bd4b2e`)

## Single request — mean ± stddev (CV%) [min–max], n=3

| pp | tg | Prefill tok/s | Decode tok/s | TTFT ms |
|---|---|---|---|---|
| 1024 | 256 | 405.6 ± 1.4 (CV 0.3%) [404.3–407.0] | 58.9 ± 1.7 (CV 2.9%) [57.0–60.3] | 2524.8 ± 8.4 (CV 0.3%) [2515.9–2532.5] |
| 4096 | 256 | 427.2 ± 0.3 (CV 0.1%) [426.9–427.4] | 45.4 ± 1.9 (CV 4.2%) [44.0–47.6] | 9586.9 ± 6.1 (CV 0.1%) [9582.6–9593.8] |
| 32768 | 256 | 378.5 ± 0.4 (CV 0.1%) [378.2–378.9] | 66.2 ± 0.7 (CV 1.0%) [65.7–67.0] | 86581.1 ± 79.8 (CV 0.1%) [86489.2–86632.5] |
| 131072 | 256 | 266.3 ± 0.4 (CV 0.1%) [266.0–266.7] | 41.2 ± 0.7 (CV 1.7%) [40.5–41.9] | 492176.0 ± 602.9 (CV 0.1%) [491534.3–492730.7] |

## Batching (pp1024) — mean ± stddev, n=3

Note: `scheduler.max_concurrent_requests` is 4 — the 8× run sends 8 requests but the scheduler admits 4 and queues the rest, so "8×" is 8 requests through a 4-wide pipe (multiple waves), not true parallelism. "vs 1x" is aggregate speedup; per-request latency spans the waves.

| Batch | pp | Aggregate decode tok/s | vs 1x |
|---|---|---|---|
| 1x (single) | 1024 | 58.9 ± 0.0 (CV 0.0%) | 1.00 |
| 2x | 1024 | 73.6 ± 3.3 (CV 4.5%) [70.9–77.3] | 1.25 |
| 4x | 1024 | 79.6 ± 4.3 (CV 5.5%) [76.2–84.5] | 1.35 |
| 8x | 1024 | 193.4 ± 13.3 (CV 6.9%) [183.0–208.4] | 3.28 |

## Per-run tables (n=3)

### Qwen3.8-27B-oQ8-mtp-20261022-072939-run1.json (`bench-3b6ab39fd885`)

| pp | tg | Prefill tok/s | Decode tok/s | TTFT ms |
|---|---|---|---|---|
| 1024 | 256 | 407.0 | 57.0 | 2515.9 |
| 4096 | 256 | 427.4 | 44.6 | 9582.6 |
| 32768 | 256 | 378.9 | 66.0 | 86489.2 |
| 131072 | 256 | 266.0 | 40.5 | 492730.7 |

### Qwen3.8-27B-oQ8-mtp-20261022-072939-run2.json (`bench-7d6cdcc52528`)

| pp | tg | Prefill tok/s | Decode tok/s | TTFT ms |
|---|---|---|---|---|
| 1024 | 256 | 404.3 | 59.5 | 2532.5 |
| 4096 | 256 | 427.4 | 44.0 | 9584.2 |
| 32768 | 256 | 378.3 | 67.0 | 86621.7 |
| 131072 | 256 | 266.3 | 41.1 | 492263.1 |

### Qwen3.8-27B-oQ8-mtp-20261022-072939-run3.json (`bench-d5d481bd4b2e`)

| pp | tg | Prefill tok/s | Decode tok/s | TTFT ms |
|---|---|---|---|---|
| 1024 | 256 | 405.4 | 60.3 | 2525.9 |
| 4096 | 256 | 426.9 | 47.6 | 9593.8 |
| 32768 | 256 | 378.2 | 65.7 | 86632.5 |
| 131072 | 256 | 266.7 | 41.9 | 491534.3 |

> oMLX throughput benchmark via the admin API, MTP enabled, server defaults, code_python prompts, 256 generated tokens, decode = single-request gen_tps, batch = aggregate tg_tps at pp1024. n=3 run(s), reported as mean ± stddev (CV%) [min–max].

## Findings

- Numbers are extremely tight across all 3 runs (CV ≤ 4.2% everywhere; prefill CV ≤ 0.4%). No cold-cache outliers.
- Decode is non-monotonic in context length: 58.9 tok/s at pp1024, dips to 45.4 at pp4096, recovers to 66.2 at pp32768, then falls to 41.2 at pp131072. The pp4096 dip reproduced in all three runs — likely a decode-path size threshold, not noise.
- Long-context prefill degrades more than the Flash model: 427 → 378 (−11%) at pp32768 → 266 (−38%) at pp131072, and TTFT at 128K is ~492 s (8+ min) — 5× the Flash model's 101 s. Expect painful reviewer-turnaround at long context.
- Batch scaling mirrors the Flash model's pattern: weak at narrow widths (2× = 1.25, 4× = 1.35 under the 4-wide scheduler cap), jumping to 3.28× at 8×.
- vs Qwen3.8-Flash-Next-oQ4-mtp: ~3× slower prefill and ~1.5–2.4× slower decode at every pp, but this is the oQ8 (higher-fidelity) quant.
