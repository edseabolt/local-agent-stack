# local-agent-stack

My local agentic coding setup: open-weight LLMs served by oMLX on a Mac Studio, driven by [OpenCode](https://opencode.ai) with a multi-agent pipeline where each role gets the model that suits it. Nothing leaves the machine.

The pipeline gates themselves (plan approval, test evidence before review, reviewer round caps) are enforced by [turnstile](https://github.com/edseabolt/turnstile). This repo is the model and server side. The [`omlx-benchmark` skill](opencode/skills/omlx-benchmark/SKILL.md) runs oMLX's admin-API throughput benchmark (single-request prefill/decode at chosen context lengths, plus 2x/4x/8x concurrent batches) and prints README-ready tables; the [`omlx-install` skill](opencode/skills/omlx-install/SKILL.md) applies any template change to the live config.

## Hardware

- Mac Studio, M3 Ultra, 512 GB unified memory
- One oMLX server on port 8000, reachable on the LAN, API-key protected

## Models

All four are quantized with oMLX's oQ format, and all run with MTP (multi-token prediction) speculative decoding. See [Benchmarks](#benchmarks) for the full measured data.

| Model | Quant | Context | Input | Prefill tok/s | Decode tok/s | Notes |
|---|---|---|---|---|---|---|
| GLM-5.3-Flash | oQ4 | 1M | text, image | ~500–570 | ~45–87 | Adaptive MTP depth 3. Pinned in memory. Decode is the only model here that *rises* with context (44.8 at pp4096 → 87.0 at pp131072). |
| Qwen3.8-Flash-Next | oQ4 | 256K | text, image | ~1350 flat to 131072 | ~100 dropping to 58 at pp131072 | Fastest flat prefill; decode is noisy (CV 8–11%). |
| Ornith-1.5-35B-A3B | oQ8 | 256K | text, image, video | 2410–3095, falling to 1092 at pp131072 | 133–158, 101 at pp131072 | MoE, about 3B active parameters. Fastest short-context model. Pinned in memory. |
| Qwen3.8-27B | oQ8 | 128K | text, image, video | 405–427, 266 at pp131072 | 41–66 | Dense. Slowest across the board; decode is non-monotonic (58.9 → 45.4 → 66.2 → 41.2 across pp1024/4096/32768/131072). Runs executor and test-runner. |

All numbers are mean of 3 recorded benchmark runs at `code_python` profile, gen 256, via the admin-API benchmark (see [Benchmarks](#benchmarks) for methodology). The prefill range in the table spans pp1024–pp131072; the decode range spans the same. The GLM numbers in the table come from a run of the same shape (October 21, 2026).

Server-side defaults for every model: temperature 1.0, top-p 0.95, top-k 20 (not set for GLM), thinking enabled with `reasoning_effort: low`. `force_sampling` is off, so the temperature OpenCode sends with each request wins. (oMLX also has a global fallback sampling profile for models without a per-model entry; the per-model values above are what matter here.)

## Agent roles

Defined in [`opencode/opencode.jsonc`](opencode/opencode.jsonc).

| Role | Model | Why |
|---|---|---|
| default, plan-reviewer, reviewer, debugger | GLM-5.3-Flash | The judging roles. It's the slowest model here, but these roles produce short verdicts, and the 1M context holds a whole plan, diff, and test log at once. |
| planner | Qwen3.8-Flash-Next | Fast drafting of plans and decompositions. |
| executor, test-runner | Qwen3.8-27B | High-volume edit and test loops. Dense oQ8 keeps quality up; capped at 128K context. |
| title, summary | Ornith-1.5-35B-A3B | Cheap housekeeping calls. |

Each model also has three OpenCode variants: `precise` (0.1), `balanced` (0.5), and `creative` (0.9). turnstile further clamps executor, test-runner, and debugger to ≤ 0.2 and both reviewers to 0.

## oMLX tuning

From [`omlx/settings.json`](omlx/settings.json) and [`omlx/model_settings.json`](omlx/model_settings.json):

- **Memory:** aggressive memory guard. (A 384 GB `memory_guard_custom_ceiling_gb` is set but only applies with tier `custom`, so it's inert here.)
- **Cache:** 37 GB hot (in-memory) prefix cache plus a 128 GB SSD cache directory (hot-cache-only mode is off). `preserve_mid_system_cache` keeps the shared system prompt cached across agent turns.
- **Scheduler:** 4 concurrent requests with chunked prefill, context-priority prefill, and decode fairness, so several agents (or several Orca worktrees) can share one server without one starving the others.
- **Decode:** aggressive burst decode, with the GPU kept warm every 0.5 s.
- **Context:** the global default is 64K, overridden per model to 256K (1M for GLM, 128K for Qwen3.8-27B). The OpenCode `limit.context` values match, so OpenCode compacts at the right point.

## Setup

1. Install oMLX and download the models into your oMLX models directory.
2. Run the install skill (or `python3 opencode/skills/omlx-install/scripts/install.py`): it creates `.env` (harvesting keys/hostname from an existing install, or generating them), substitutes the sentinels, backs up and installs `~/.omlx/settings.json`, `~/.omlx/model_settings.json`, `~/.config/opencode/opencode.jsonc`, and `~/.config/opencode/skills/`. The installed client config gets a literal `baseURL`/`apiKey`, so no `.env` sourcing is needed at launch.

3. Export `.env` if other tools need the values (`set -a; source .env; set +a`), then run `opencode`.

## Notes

- The server binds `0.0.0.0` so other machines on the LAN can use it. If you only use it locally, set `host` to `127.0.0.1`.
- The permission list auto-allows read-only shell commands (`git log`, `rg`, `jq`, and similar) plus `npm run *` and `gh *`; destructive git operations (`git push --force*`, `git worktree remove/prune`, `gh pr merge`) ask first, and everything else (edits, any other shell command) asks.
- `model_settings.json` also keeps entries for the unsuffixed base checkpoints (for example `GLM-5.3-Flash`). Only the `-oQ4-mtp` / `-oQ8-mtp` entries are used by this setup.

## Benchmarks

Measured with the [`omlx-benchmark` skill](opencode/skills/omlx-benchmark/SKILL.md) (oMLX admin-API throughput benchmark), 3 recorded runs per model, MTP enabled, `code_python` prompts, 256 generated tokens. Raw JSON and full reports live in [`benchmarks/`](benchmarks/). Run date: 2026-10-21/22, M3 Ultra.

Methodology line, verbatim from the reports:

> oMLX throughput benchmark via the admin API, MTP enabled, server defaults, code_python prompts, 256 generated tokens, decode = single-request gen_tps, batch = aggregate tg_tps at pp1024. n=3 run(s), reported as mean ± stddev (CV%) [min–max].

### Single request — prefill / decode tok/s (mean, n=3)

| pp | GLM-5.3-Flash oQ4 | Qwen3.8-Flash-Next oQ4 | Ornith-1.5-35B-A3B oQ8 | Qwen3.8-27B oQ8 |
|---|---|---|---|---|
| 1024 | 504 / 52 | 1102 / 100 | 2411 / 133 | 406 / 59 |
| 4096 | 573 / 45 | 1358 / 100 | 3095 / 136 | 427 / 45 |
| 32768 | 514 / 56 | 1342 / 89 | 2254 / 158 | 379 / 66 |
| 131072 | 497 / 87 | 1301 / 58 | 1092 / 102 | 266 / 41 |

### Single request — TTFT (mean ms, n=3)

| pp | GLM-5.3-Flash oQ4 | Qwen3.8-Flash-Next oQ4 | Ornith-1.5-35B-A3B oQ8 | Qwen3.8-27B oQ8 |
|---|---|---|---|---|
| 1024 | 2033 | 929 | 425 | 2525 |
| 4096 | 7144 | 3017 | 1324 | 9587 |
| 32768 | 63750 | 24419 | 14539 | 86581 |
| 131072 | 263941 | 100743 | 120071 | 492176 |

### Batching at pp1024 — aggregate decode tok/s, vs 1x (mean, n=3)

The scheduler admits 4 concurrent requests, so only 2× and 4× are valid signals here — 4× is the widest true-parallel width. (The benchmark tool also fires an 8× test, but with this config that's 8 requests queued through a 4-wide pipe — multiple waves, not 8-way parallelism — so its numbers are omitted as misleading.)

| Batch | GLM-5.3-Flash oQ4 | Qwen3.8-Flash-Next oQ4 | Ornith-1.5-35B-A3B oQ8 | Qwen3.8-27B oQ8 |
|---|---|---|---|---|
| 1x (single) | 51.6 | 99.7 | 133.3 | 58.9 |
| 2x | 48.7 (0.95) | 101.5 (1.02) | 188.0 (1.41) | 73.6 (1.25) |
| 4x | 63.3 (1.23) | 140.6 (1.41) | 200.5 (1.50) | 79.6 (1.35) |

### Observations

- **Ornith-1.5-35B-A3B (oQ8) is the speed king below ~64K context** despite being the largest model — MoE with ~3B active parameters buys ~2–3× the prefill and the best decode of the set. Its decode even *rises* with context (133 → 158 tok/s from pp1024 to pp32768), unlike every other model here.
- **Qwen3.8-Flash-Next (oQ4) has the flattest prefill**: ~1.35K tok/s from pp4096 to pp131072 with ≤ 1% CV. Its long-context TTFT is the lowest of all four (101 s at pp131072 vs GLM's 264 s).
- **GLM-5.3-Flash's decode improves with context length** (45 → 87 tok/s from pp4096 to pp131072) — the opposite of everything else, which suits its role as the 1M-context reviewer. Its TTFT at long context is the worst of the set, though.
- **Long-context cost is model-specific**: GLM pays in TTFT (264 s at pp131072), Qwen3.8-27B pays in everything (266 tok/s prefill, 41 tok/s decode, 492 s TTFT — 8+ minutes). Ornith's prefill falls off a 52% cliff past pp32768 but its TTFT stays reasonable.
- **Batch scaling is real but modest under the 4-wide scheduler**: Ornith gains most from true parallelism (1.41× at 2×, 1.50× at 4×), while GLM barely benefits (1.23× at 4×, and actually regresses at 2×) and Qwen3.8-Flash-Next sees nothing at 2× (1.02×). Even 4 concurrent decode streams cost per-request latency everywhere — aggregate throughput improves, single-stream speed does not.
- **Qwen3.8-27B's decode is non-monotonic** (59 → 45 → 66 → 41 tok/s across pp1024/4096/32768/131072); the pp4096 dip reproduced in all 3 runs and looks like a decode-path size threshold rather than noise.
- Reproducibility: prefill CV is ≤ 1.7% for Qwen3.8-27B, Qwen3.8-Flash-Next, and GLM at every length; Ornith's short-pp prefill is looser (4.6% at pp1024, ≤ 1.7% elsewhere). Decode CV runs higher at short pp (up to ~11% for Qwen3.8-Flash-Next) and is the noisier metric.

## License

MIT
