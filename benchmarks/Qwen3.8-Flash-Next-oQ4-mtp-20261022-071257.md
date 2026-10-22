# Qwen3.8-Flash-Next-oQ4-mtp — oMLX throughput benchmark

3 recorded run(s) aggregated. Profile: `code_python`, gen: 256.

Raw results:
- `Qwen3.8-Flash-Next-oQ4-mtp-20261022-071257-run1.json` (bench `bench-a51615d075e1`)
- `Qwen3.8-Flash-Next-oQ4-mtp-20261022-071257-run2.json` (bench `bench-af8741236a35`)
- `Qwen3.8-Flash-Next-oQ4-mtp-20261022-071257-run3.json` (bench `bench-9766d84f8772`)

## Single request — mean ± stddev (CV%) [min–max], n=3

| pp | tg | Prefill tok/s | Decode tok/s | TTFT ms |
|---|---|---|---|---|
| 1024 | 256 | 1102.2 ± 11.8 (CV 1.1%) [1089.1–1112.1] | 99.7 ± 8.4 (CV 8.4%) [93.9–109.3] | 929.1 ± 10.0 (CV 1.1%) [920.8–940.2] |
| 4096 | 256 | 1357.7 ± 7.9 (CV 0.6%) [1348.6–1362.7] | 99.6 ± 10.0 (CV 10.1%) [92.8–111.1] | 3016.9 ± 17.7 (CV 0.6%) [3005.8–3037.3] |
| 32768 | 256 | 1341.9 ± 2.0 (CV 0.2%) [1339.6–1343.4] | 89.0 ± 10.0 (CV 11.2%) [78.9–98.8] | 24418.7 ± 36.9 (CV 0.2%) [24391.3–24460.7] |
| 131072 | 256 | 1301.0 ± 2.6 (CV 0.2%) [1299.0–1304.0] | 58.3 ± 3.3 (CV 5.6%) [56.4–62.1] | 100742.9 ± 204.1 (CV 0.2%) [100511.9–100898.9] |

## Batching (pp1024) — mean ± stddev, n=3

Note: `scheduler.max_concurrent_requests` is 4 — the 8× run sends 8 requests but the scheduler admits 4 and queues the rest, so "8×" is 8 requests through a 4-wide pipe (multiple waves), not true parallelism. "vs 1x" is aggregate speedup; per-request latency spans the waves.

| Batch | pp | Aggregate decode tok/s | vs 1x |
|---|---|---|---|
| 1x (single) | 1024 | 99.7 ± 0.0 (CV 0.0%) | 1.00 |
| 2x | 1024 | 101.5 ± 4.1 (CV 4.0%) [98.2–106.1] | 1.02 |
| 4x | 1024 | 140.6 ± 15.6 (CV 11.1%) [122.9–152.6] | 1.41 |
| 8x | 1024 | 313.4 ± 21.9 (CV 7.0%) [288.2–328.0] | 3.14 |

## Per-run tables (n=3)

### Qwen3.8-Flash-Next-oQ4-mtp-20261022-071257-run1.json (`bench-a51615d075e1`)

| pp | tg | Prefill tok/s | Decode tok/s | TTFT ms |
|---|---|---|---|---|
| 1024 | 256 | 1112.1 | 109.3 | 920.8 |
| 4096 | 256 | 1348.6 | 92.8 | 3037.3 |
| 32768 | 256 | 1343.4 | 78.9 | 24391.3 |
| 131072 | 256 | 1304.0 | 56.5 | 100511.9 |

### Qwen3.8-Flash-Next-oQ4-mtp-20261022-071257-run2.json (`bench-af8741236a35`)

| pp | tg | Prefill tok/s | Decode tok/s | TTFT ms |
|---|---|---|---|---|
| 1024 | 256 | 1105.4 | 93.9 | 926.4 |
| 4096 | 256 | 1361.9 | 111.1 | 3007.5 |
| 32768 | 256 | 1342.7 | 89.4 | 24404.1 |
| 131072 | 256 | 1300.1 | 62.1 | 100817.8 |

### Qwen3.8-Flash-Next-oQ4-mtp-20261022-071257-run3.json (`bench-9766d84f8772`)

| pp | tg | Prefill tok/s | Decode tok/s | TTFT ms |
|---|---|---|---|---|
| 1024 | 256 | 1089.1 | 95.9 | 940.2 |
| 4096 | 256 | 1362.7 | 94.8 | 3005.8 |
| 32768 | 256 | 1339.6 | 98.8 | 24460.7 |
| 131072 | 256 | 1299.0 | 56.4 | 100898.9 |

> oMLX throughput benchmark via the admin API, MTP enabled, server defaults, code_python prompts, 256 generated tokens, decode = single-request gen_tps, batch = aggregate tg_tps at pp1024. n=3 run(s), reported as mean ± stddev (CV%) [min–max].

## Findings

- Prefill is remarkably flat: ~1.35K tok/s from pp4096 through pp131072 (only ~4% degradation at 128K). Very stable — CV ≤ 1.1% everywhere.
- Decode holds ~100 tok/s up to pp4096, then drops to ~89 tok/s at pp32768 and ~58 tok/s at pp131072 (long-context decode penalty).
- Batch scaling is weak at low widths: 2× gives essentially nothing (1.02×) and 4× only 1.41× — with the 4-request scheduler cap, 4× is true parallelism yet still far from linear. 8× (two 4-wide waves) reaches 3.14×, suggesting MTP decode benefits much more from wide batches than narrow ones.
- Decode CV is notably high (8–11% at short/medium pp) vs near-zero prefill variance; use the max-end numbers (≈110 tok/s) with caution and the means for comparisons.
