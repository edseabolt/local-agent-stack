# Benchmarks — oMLX v0.7.2 (2026-10-21/22)

Benchmark runs on the M3 Ultra server, oMLX v0.7.2, on 2026-10-21 and
2026-10-22. Each number is the mean of 3 runs per model. Superseded by
[benchmarks-current.md](benchmarks-current.md) (oMLX v0.7.3,
2026-11-15); kept for trend comparison. Note: GLM was benchmarked as oQ4
in this run and oQ6 in the current run, so GLM numbers are not directly
comparable across the two.

The chart at [../benchmarks/benchmarks.svg](../benchmarks/benchmarks.svg)
compares this run with the current one.

Mean of 3 recorded runs per cell; see
[benchmarks-current.md](benchmarks-current.md) for the full methodology.

## Single request — prefill / decode tok/s (mean, n=3)

| pp | GLM-5.3-Flash oQ4 | Qwen3.8-Flash-Next oQ4 | Ornith-1.5-35B-A3B oQ8 | Qwen3.8-27B oQ8 |
|---|---|---|---|---|
| 1024 | 504 / 52 | 1102 / 100 | 2411 / 133 | 406 / 59 |
| 4096 | 573 / 45 | 1358 / 100 | 3095 / 136 | 427 / 45 |
| 32768 | 514 / 56 | 1342 / 89 | 2254 / 158 | 379 / 66 |
| 131072 | 497 / 87 | 1301 / 58 | 1092 / 102 | 266 / 41 |

## Single request — TTFT (mean ms, n=3)

| pp | GLM-5.3-Flash oQ4 | Qwen3.8-Flash-Next oQ4 | Ornith-1.5-35B-A3B oQ8 | Qwen3.8-27B oQ8 |
|---|---|---|---|---|
| 1024 | 2033 | 929 | 425 | 2525 |
| 4096 | 7144 | 3017 | 1324 | 9587 |
| 32768 | 63750 | 24419 | 14539 | 86581 |
| 131072 | 263941 | 100743 | 120071 | 492176 |

## Batching at pp1024 — aggregate decode tok/s, vs 1x (mean, n=3)

The scheduler admits 4 concurrent requests, so only 2× and 4× are valid
signals here — 4× is the widest true-parallel width. (The benchmark tool
also fires an 8× test, but with this config that's 8 requests queued
through a 4-wide pipe — multiple waves, not 8-way parallelism — so its
numbers are omitted as misleading.)

| Batch | GLM-5.3-Flash oQ4 | Qwen3.8-Flash-Next oQ4 | Ornith-1.5-35B-A3B oQ8 | Qwen3.8-27B oQ8 |
|---|---|---|---|---|
| 1x (single) | 51.6 | 99.7 | 133.3 | 58.9 |
| 2x | 48.7 (0.95) | 101.5 (1.02) | 188.0 (1.41) | 73.6 (1.25) |
| 4x | 63.3 (1.23) | 140.6 (1.41) | 200.5 (1.50) | 79.6 (1.35) |

## Observations

Observations below refer to the October 2026 run; several hold in the
November run as well — see the current tables.

- **Ornith-1.5-35B-A3B (oQ8) is the speed king below ~64K context** despite being the largest model — MoE with ~3B active parameters buys ~2–3× the prefill and the best decode of the set. Its decode even *rises* with context (133 → 158 tok/s from pp1024 to pp32768), unlike every other model here.
- **Qwen3.8-Flash-Next (oQ4) has the flattest prefill**: ~1.35K tok/s from pp4096 to pp131072 with ≤ 1% CV. Its long-context TTFT is the lowest of all four (101 s at pp131072 vs GLM's 264 s).
- **GLM-5.3-Flash's decode improves with context length** (45 → 87 tok/s from pp4096 to pp131072) — the opposite of everything else, which suits its role as the 1M-context reviewer. Its TTFT at long context is the worst of the set, though.
- **Long-context cost is model-specific**: GLM pays in TTFT (264 s at pp131072), Qwen3.8-27B pays in everything (266 tok/s prefill, 41 tok/s decode, 492 s TTFT — 8+ minutes). Ornith's prefill falls off a 52% cliff past pp32768 but its TTFT stays reasonable.
- **Batch scaling is real but modest under the 4-wide scheduler**: Ornith gains most from true parallelism (1.41× at 2×, 1.50× at 4×), while GLM barely benefits (1.23× at 4×, and actually regresses at 2×) and Qwen3.8-Flash-Next sees nothing at 2× (1.02×). Even 4 concurrent decode streams cost per-request latency everywhere — aggregate throughput improves, single-stream speed does not.
- **Qwen3.8-27B's decode is non-monotonic** (59 → 45 → 66 → 41 tok/s across pp1024/4096/32768/131072); the pp4096 dip reproduced in all 3 runs and looks like a decode-path size threshold rather than noise.
- Reproducibility: prefill CV is ≤ 1.7% for Qwen3.8-27B, Qwen3.8-Flash-Next, and GLM at every length; Ornith's short-pp prefill is looser (4.6% at pp1024, ≤ 1.7% elsewhere). Decode CV runs higher at short pp (up to ~11% for Qwen3.8-Flash-Next) and is the noisier metric.