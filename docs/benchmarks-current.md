# Benchmarks — oMLX v0.7.3 (2026-11-15)

Benchmark runs on the M3 Ultra server, oMLX v0.7.3, on 2026-11-15. Each
number is the aggregate of 3 runs per model. The companion chart is
[benchmarks/benchmarks.svg](../benchmarks/benchmarks.svg). Historical
results from oMLX v0.7.2 are in
[benchmarks-historical.md](benchmarks-historical.md).

Methodology line, verbatim from the reports:

> oMLX throughput benchmark via the admin API, MTP enabled, server defaults, code_python prompts, 256 generated tokens, decode = single-request gen_tps, batch = aggregate tg_tps at pp1024. n=3 run(s), reported as mean ± stddev (CV%) [min–max].

In the tables below, each cell reads `mean ± sd / median / min–max`. The
median is the middle of the 3 per-run values.

## GLM-5.3-Flash (oQ6)

Single request:

| pp | Prefill tok/s | Decode tok/s | TTFT ms |
|---|---|---|---|
| 1024 | 486.0 ± 1.9 / 487.0 / 483.8–487.2 | 41.4 ± 1.9 / 40.5 / 40.1–43.6 | 2106.9 ± 8.4 / 2102.5 / 2101.7–2116.6 |
| 4096 | 560.1 ± 2.4 / 560.9 / 557.4–562.1 | 43.2 ± 1.9 / 44.2 / 41.0–44.3 | 7312.6 ± 32.3 / 7302.7 / 7286.4–7348.6 |
| 32768 | 521.6 ± 0.7 / 521.8 / 520.9–522.2 | 50.7 ± 1.5 / 50.4 / 49.4–52.3 | 62816.5 ± 82.9 / 62794.0 / 62747.1–62908.3 |
| 131072 | 505.3 ± 0.3 / 505.3 / 505.0–505.6 | 70.6 ± 0.1 / 70.6 / 70.6–70.7 | 259404.2 ± 162.8 / 259412.3 / 259237.5–259562.7 |

Batching at pp1024 (aggregate decode tok/s):

| 1x | 2x | 4x | 8x |
|---|---|---|---|
| 41.4 ± 0.0 / 41.4–41.4 | 42.4 ± 1.5 / 40.7–43.7 | 56.7 ± 0.7 / 56.0–57.4 | 121.5 ± 1.7 / 120.2–123.5 |

The scheduler admits 4 concurrent requests, so 2× and 4× are the widest
true-parallel widths; 8× sends 8 requests through that 4-wide pipe
(multiple waves), so its aggregate number reflects queueing, not 8-way
parallelism.

- GLM-5.3-Flash (oQ6) decode rises with context: 41.4 tok/s at pp1024 to
  70.6 tok/s at pp131072, the only model in this run that does so.
- GLM-5.3-Flash (oQ6) prefill stays flat across the whole range (486.0 to
  505.3 tok/s, peak 560.1 at pp4096).
- GLM-5.3-Flash (oQ6) pays for long context in TTFT: about 259 s at
  pp131072, the second-worst of the four models.

## Ornith-1.5-35B-A3B (oQ8)

Single request:

| pp | Prefill tok/s | Decode tok/s | TTFT ms |
|---|---|---|---|
| 1024 | 2331.1 ± 62.9 / 2349.2 / 2261.1–2383.0 | 131.5 ± 10.9 / 128.5 / 122.4–143.5 | 439.5 ± 12.0 / 435.9 / 429.7–452.9 |
| 4096 | 3085.8 ± 211.0 / 3200.1 / 2842.3–3215.1 | 154.3 ± 30.1 / 151.4 / 125.7–185.7 | 1331.7 ± 94.8 / 1280.0 / 1274.0–1441.1 |
| 32768 | 2290.5 ± 7.8 / 2289.4 / 2283.3–2298.7 | 157.5 ± 6.9 / 155.2 / 152.1–165.3 | 14306.4 ± 48.5 / 14313.2 / 14254.8–14351.1 |
| 131072 | 1107.8 ± 2.4 / 1107.8 / 1105.5–1110.2 | 102.2 ± 2.1 / 101.5 / 100.6–104.6 | 118316.3 ± 255.4 / 118322.3 / 118058.0–118568.7 |

Batching at pp1024 (aggregate decode tok/s):

| 1x | 2x | 4x | 8x |
|---|---|---|---|
| 131.5 ± 0.0 / 131.5–131.5 | 208.3 ± 24.7 / 184.8–234.0 | 264.8 ± 18.8 / 243.3–278.0 | 558.7 ± 10.1 / 547.7–567.5 |

The scheduler admits 4 concurrent requests, so 2× and 4× are the widest
true-parallel widths; 8× sends 8 requests through that 4-wide pipe
(multiple waves), so its aggregate number reflects queueing, not 8-way
parallelism.

- Ornith-1.5-35B-A3B (oQ8) is the fastest model at short context: prefill
  2331.1–3085.8 tok/s through pp4096 and decode 131.5–157.5 tok/s.
- Ornith-1.5-35B-A3B (oQ8) decode rises with context up to pp32768
  (131.5 to 157.5 tok/s) before dropping to 102.2 at pp131072.
- Ornith-1.5-35B-A3B (oQ8) prefill falls 52% past pp32768 (2290.5 to
  1107.8 tok/s), but its long-context TTFT (about 118 s) stays second-best.
- Ornith-1.5-35B-A3B (oQ8) short-context numbers are the loosest of the
  run (decode CV up to 19.5% at pp4096); long-context numbers are tight
  (CV ≤ 2.1%).

## Qwen3.8-27B (oQ8)

Single request:

| pp | Prefill tok/s | Decode tok/s | TTFT ms |
|---|---|---|---|
| 1024 | 410.4 ± 2.4 / 409.6 / 408.6–413.1 | 59.6 ± 4.1 / 59.4 / 55.7–63.8 | 2495.0 ± 14.3 / 2499.8 / 2478.9–2506.2 |
| 4096 | 435.3 ± 0.1 / 435.3 / 435.2–435.3 | 50.1 ± 0.8 / 50.5 / 49.2–50.7 | 9410.1 ± 1.1 / 9409.5 / 9409.4–9411.3 |
| 32768 | 385.0 ± 0.0 / 385.0 / 385.0–385.0 | 70.6 ± 1.9 / 71.0 / 68.5–72.3 | 85107.6 ± 9.4 / 85103.9 / 85100.7–85118.3 |
| 131072 | 270.5 ± 0.1 / 270.5 / 270.4–270.6 | 42.9 ± 1.0 / 42.9 / 41.9–43.9 | 484559.2 ± 100.9 / 484566.0 / 484455.1–484656.5 |

Batching at pp1024 (aggregate decode tok/s):

| 1x | 2x | 4x | 8x |
|---|---|---|---|
| 59.6 ± 0.0 / 59.6–59.6 | 85.3 ± 0.7 / 84.7–86.0 | 112.9 ± 0.8 / 112.2–113.8 | 252.7 ± 6.1 / 245.9–257.7 |

The scheduler admits 4 concurrent requests, so 2× and 4× are the widest
true-parallel widths; 8× sends 8 requests through that 4-wide pipe
(multiple waves), so its aggregate number reflects queueing, not 8-way
parallelism.

- Qwen3.8-27B (oQ8) is the slowest model at long context: 270.5 tok/s
  prefill, 42.9 tok/s decode, and about 485 s TTFT at pp131072.
- Qwen3.8-27B (oQ8) decode is non-monotonic in context length (59.6 →
  50.1 → 70.6 → 42.9 tok/s); the pp4096 dip reproduced in all 3 runs.
- Qwen3.8-27B (oQ8) numbers are extremely repeatable: prefill CV ≤ 0.6%
  and decode CV ≤ 6.8% everywhere.

## Qwen3.8-Flash-Next (oQ4)

Single request:

| pp | Prefill tok/s | Decode tok/s | TTFT ms |
|---|---|---|---|
| 1024 | 1125.9 ± 8.9 / 1130.4 / 1115.7–1131.7 | 103.6 ± 7.4 / 101.0 / 97.9–111.9 | 909.5 ± 7.2 / 905.9 / 904.8–917.8 |
| 4096 | 1339.0 ± 77.3 / 1382.2 / 1249.7–1385.1 | 88.1 ± 12.9 / 85.8 / 76.6–102.0 | 3066.1 ± 183.2 / 2963.5 / 2957.1–3277.6 |
| 32768 | 1358.2 ± 2.8 / 1357.2 / 1356.0–1361.3 | 92.1 ± 0.3 / 92.0 / 91.8–92.4 | 24126.7 ± 49.7 / 24144.5 / 24070.5–24165.0 |
| 131072 | 1317.5 ± 1.6 / 1317.2 / 1316.1–1319.3 | 58.2 ± 0.9 / 58.0 / 57.4–59.2 | 99485.0 ± 120.7 / 99511.1 / 99353.3–99590.5 |

Batching at pp1024 (aggregate decode tok/s):

| 1x | 2x | 4x | 8x |
|---|---|---|---|
| 103.6 ± 0.0 / 103.6–103.6 | 100.4 ± 15.3 / 82.7–109.2 | 160.7 ± 7.4 / 153.8–168.5 | 347.2 ± 10.7 / 335.2–355.9 |

The scheduler admits 4 concurrent requests, so 2× and 4× are the widest
true-parallel widths; 8× sends 8 requests through that 4-wide pipe
(multiple waves), so its aggregate number reflects queueing, not 8-way
parallelism.

- Qwen3.8-Flash-Next (oQ4) has the flattest prefill of the run: about
  1.3K tok/s from pp4096 to pp131072 with CV ≤ 5.8% (≤ 0.8% outside
  pp4096).
- Qwen3.8-Flash-Next (oQ4) has the lowest long-context TTFT of the four
  (about 99 s at pp131072).
- Qwen3.8-Flash-Next (oQ4) decode is the noisiest metric in the run
  (CV up to 14.6% at pp4096) and falls from 103.6 to 58.2 tok/s as
  context grows.

## Observations

- GLM was benchmarked as oQ6 in this run but as oQ4 in the October run,
  so GLM numbers are not directly comparable across the two runs (see
  [benchmarks-historical.md](benchmarks-historical.md)).
- Ornith-1.5-35B-A3B (oQ8) remains the speed king below ~64K context
  despite being the largest model; MoE with ~3B active parameters buys
  roughly 2–3× the prefill of the dense models.
- Long-context cost is model-specific: Qwen3.8-Flash-Next (oQ4) keeps
  prefill flat and TTFT lowest, GLM-5.3-Flash (oQ6) keeps decode rising
  but pays in TTFT, and Qwen3.8-27B (oQ8) pays in everything.
- Batch scaling at true-parallel widths (2×/4×) is real but modest under
  the 4-wide scheduler; the 8× rows are queueing artifacts, not 8-way
  parallelism.
