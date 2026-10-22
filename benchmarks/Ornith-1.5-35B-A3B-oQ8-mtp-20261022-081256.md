# Ornith-1.5-35B-A3B-oQ8-mtp — oMLX throughput benchmark

3 recorded run(s) aggregated. Profile: `code_python`, gen: 256.

Raw results:
- `Ornith-1.5-35B-A3B-oQ8-mtp-20261022-081256-run1.json` (bench `bench-f9b33a701e81`)
- `Ornith-1.5-35B-A3B-oQ8-mtp-20261022-081256-run2.json` (bench `bench-9b4dfd88e5ab`)
- `Ornith-1.5-35B-A3B-oQ8-mtp-20261022-081256-run3.json` (bench `bench-73ed2bed4d8b`)

## Single request — mean ± stddev (CV%) [min–max], n=3

| pp | tg | Prefill tok/s | Decode tok/s | TTFT ms |
|---|---|---|---|---|
| 1024 | 256 | 2411.2 ± 109.9 (CV 4.6%) [2298.3–2517.8] | 133.3 ± 11.6 (CV 8.7%) [122.2–145.3] | 425.3 ± 19.5 (CV 4.6%) [406.7–445.5] |
| 4096 | 256 | 3095.0 ± 53.2 (CV 1.7%) [3064.1–3156.4] | 136.1 ± 7.6 (CV 5.6%) [130.5–144.8] | 1323.7 ± 22.5 (CV 1.7%) [1297.7–1336.8] |
| 32768 | 256 | 2253.8 ± 1.6 (CV 0.1%) [2252.1–2255.1] | 157.9 ± 1.5 (CV 0.9%) [156.7–159.6] | 14538.7 ± 10.0 (CV 0.1%) [14530.6–14549.8] |
| 131072 | 256 | 1091.6 ± 0.8 (CV 0.1%) [1090.8–1092.4] | 101.5 ± 4.3 (CV 4.2%) [98.7–106.4] | 120071.1 ± 84.8 (CV 0.1%) [119989.7–120159.0] |

## Batching (pp1024) — mean ± stddev, n=3

Note: `scheduler.max_concurrent_requests` is 4 — the 8× run sends 8 requests but the scheduler admits 4 and queues the rest, so "8×" is 8 requests through a 4-wide pipe (multiple waves), not true parallelism. "vs 1x" is aggregate speedup; per-request latency spans the waves.

| Batch | pp | Aggregate decode tok/s | vs 1x |
|---|---|---|---|
| 1x (single) | 1024 | 133.3 ± 0.0 (CV 0.0%) | 1.00 |
| 2x | 1024 | 188.0 ± 11.4 (CV 6.0%) [176.9–199.6] | 1.41 |
| 4x | 1024 | 200.5 ± 6.6 (CV 3.3%) [193.5–206.5] | 1.50 |
| 8x | 1024 | 464.2 ± 23.9 (CV 5.1%) [437.0–481.8] | 3.48 |

## Per-run tables (n=3)

### Ornith-1.5-35B-A3B-oQ8-mtp-20261022-081256-run1.json (`bench-f9b33a701e81`)

| pp | tg | Prefill tok/s | Decode tok/s | TTFT ms |
|---|---|---|---|---|
| 1024 | 256 | 2298.3 | 145.3 | 445.5 |
| 4096 | 256 | 3064.5 | 133.0 | 1336.6 |
| 32768 | 256 | 2255.1 | 156.7 | 14530.6 |
| 131072 | 256 | 1092.4 | 106.4 | 119989.7 |

### Ornith-1.5-35B-A3B-oQ8-mtp-20261022-081256-run2.json (`bench-9b4dfd88e5ab`)

| pp | tg | Prefill tok/s | Decode tok/s | TTFT ms |
|---|---|---|---|---|
| 1024 | 256 | 2517.8 | 132.3 | 406.7 |
| 4096 | 256 | 3156.4 | 130.5 | 1297.7 |
| 32768 | 256 | 2254.3 | 157.5 | 14535.6 |
| 131072 | 256 | 1090.8 | 98.7 | 120159.0 |

### Ornith-1.5-35B-A3B-oQ8-mtp-20261022-081256-run3.json (`bench-73ed2bed4d8b`)

| pp | tg | Prefill tok/s | Decode tok/s | TTFT ms |
|---|---|---|---|---|
| 1024 | 256 | 2417.6 | 122.2 | 423.6 |
| 4096 | 256 | 3064.1 | 144.8 | 1336.8 |
| 32768 | 256 | 2252.1 | 159.6 | 14549.8 |
| 131072 | 256 | 1091.7 | 99.4 | 120064.7 |

> oMLX throughput benchmark via the admin API, MTP enabled, server defaults, code_python prompts, 256 generated tokens, decode = single-request gen_tps, batch = aggregate tg_tps at pp1024. n=3 run(s), reported as mean ± stddev (CV%) [min–max].

## Findings

- Fastest of the three models benchmarked today at nearly every point, despite being the largest (35B, A3B active): prefill 2.3–3.1K tok/s through pp32768, decode 133–158 tok/s. MoE with only 3B active parameters is doing the heavy lifting.
- Decode **rises** with context up to pp32768 (133 → 158 tok/s) — opposite of the other two models — before dropping to 101.5 at pp131072.
- Long-context prefill falls off a cliff: 2254 at pp32768 → 1092 at pp131072 (−52%). TTFT at 128K is ~120 s — better than Qwen3.8-27B's 492 s but 2× Flash's 101 s. Note Flash's prefill stays flat while this one collapses, so Flash wins prefill beyond ~64K-ish crossover.
- Batch scaling is the best of the three at narrow widths: 2× = 1.41, 4× = 1.50 (vs 1.02/1.41 Flash, 1.25/1.35 Qwen27B), 8× = 3.48.
- Run 1 short-pp numbers are slightly low (2298 vs 2518 prefill, 145.3 vs 132.3 decode — note the decode ordering flipped between runs); short-pp CV is 4.6–8.7% while pp32768/131072 are near-zero. Treat short-pp numbers with ±10% error bars; the long-context numbers are rock solid.
