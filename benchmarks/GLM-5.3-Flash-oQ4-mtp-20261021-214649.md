# GLM-5.3-Flash-oQ4-mtp — oMLX throughput benchmark

3 recorded run(s) aggregated. Profile: `code_python`, gen: 256.

Raw results:
- `GLM-5.3-Flash-oQ4-mtp-20261021-214649-run1.json` (bench `bench-49990c3aac7a`)
- `GLM-5.3-Flash-oQ4-mtp-20261021-214649-run2.json` (bench `bench-6f0610b73b87`)
- `GLM-5.3-Flash-oQ4-mtp-20261021-214649-run3.json` (bench `bench-3247cb34d44f`)

## Single request — mean ± stddev (CV%) [min–max], n=3

| pp | tg | Prefill tok/s | Decode tok/s | TTFT ms |
|---|---|---|---|---|
| 1024 | 256 | 503.7 ± 3.0 (CV 0.6%) [500.6–506.6] | 51.6 ± 3.1 (CV 6.1%) [49.7–55.2] | 2033.2 ± 12.2 (CV 0.6%) [2021.2–2045.6] |
| 4096 | 256 | 573.4 ± 2.2 (CV 0.4%) [571.4–575.7] | 44.8 ± 1.2 (CV 2.6%) [44.1–46.2] | 7143.7 ± 26.6 (CV 0.4%) [7115.2–7168.0] |
| 32768 | 256 | 514.0 ± 0.4 (CV 0.1%) [513.6–514.4] | 55.9 ± 4.1 (CV 7.3%) [51.7–59.8] | 63749.8 ± 51.3 (CV 0.1%) [63698.4–63801.0] |
| 131072 | 256 | 496.6 ± 0.6 (CV 0.1%) [496.2–497.3] | 87.0 ± 0.3 (CV 0.3%) [86.8–87.3] | 263940.5 ± 309.8 (CV 0.1%) [263585.0–264153.2] |

## Batching (pp1024) — mean ± stddev, n=3

Note: `scheduler.max_concurrent_requests` is 4 — the 8× run sends 8 requests but the scheduler admits 4 and queues the rest, so "8×" is 8 requests through a 4-wide pipe (multiple waves), not true parallelism. "vs 1x" is aggregate speedup; per-request latency spans the waves.

| Batch | pp | Aggregate decode tok/s | vs 1x |
|---|---|---|---|
| 1x (single) | 1024 | 51.6 ± 0.0 (CV 0.0%) | 1.00 |
| 2x | 1024 | 48.7 ± 0.8 (CV 1.7%) [48.2–49.7] | 0.95 |
| 4x | 1024 | 63.3 ± 0.7 (CV 1.0%) [62.6–63.9] | 1.23 |
| 8x | 1024 | 138.7 ± 1.5 (CV 1.0%) [137.2–140.1] | 2.69 |

## Per-run tables (n=3)

### GLM-5.3-Flash-oQ4-mtp-20261021-214649-run1.json (`bench-49990c3aac7a`)

| pp | tg | Prefill tok/s | Decode tok/s | TTFT ms |
|---|---|---|---|---|
| 1024 | 256 | 506.6 | 49.7 | 2021.2 |
| 4096 | 256 | 575.7 | 46.2 | 7115.2 |
| 32768 | 256 | 513.6 | 59.8 | 63801.0 |
| 131072 | 256 | 496.3 | 87.3 | 264083.3 |

### GLM-5.3-Flash-oQ4-mtp-20261021-214649-run2.json (`bench-6f0610b73b87`)

| pp | tg | Prefill tok/s | Decode tok/s | TTFT ms |
|---|---|---|---|---|
| 1024 | 256 | 503.8 | 55.2 | 2032.7 |
| 4096 | 256 | 571.4 | 44.2 | 7168.0 |
| 32768 | 256 | 514.0 | 56.1 | 63750.0 |
| 131072 | 256 | 496.2 | 86.8 | 264153.2 |

### GLM-5.3-Flash-oQ4-mtp-20261021-214649-run3.json (`bench-3247cb34d44f`)

| pp | tg | Prefill tok/s | Decode tok/s | TTFT ms |
|---|---|---|---|---|
| 1024 | 256 | 500.6 | 49.8 | 2045.6 |
| 4096 | 256 | 573.0 | 44.1 | 7147.9 |
| 32768 | 256 | 514.4 | 51.7 | 63698.4 |
| 131072 | 256 | 497.3 | 86.8 | 263585.0 |

> oMLX throughput benchmark via the admin API, MTP enabled, server defaults, code_python prompts, 256 generated tokens, decode = single-request gen_tps, batch = aggregate tg_tps at pp1024. n=3 run(s), reported as mean ± stddev (CV%) [min–max].

## Findings

- Prefill is flat from pp1024 to pp131072 (504 → 497 tok/s, peak 573 at pp4096) — the flattest long-context prefill TTFT profile would suggest, but TTFT at 128K is ~264 s, the worst of the set.
- Decode is unique here: it *rises* with context (51.6 at pp1024 → 87.0 at pp131072), opposite of every other model. Suits its role as the 1M-context reviewer.
- Batch scaling is the weakest of the set under the 4-wide scheduler: 2× actually regresses (0.95×), 4× only reaches 1.23×.
- Numbers are very repeatable: prefill CV ≤ 0.6% everywhere; decode CV ≤ 7.3%.
