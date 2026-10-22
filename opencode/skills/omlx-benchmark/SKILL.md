---
description: Run oMLX throughput benchmarks (single-request prefill/decode at chosen context lengths plus 2x/4x/8x concurrent batches) via the admin API and print README-ready tables. Use when the user asks to benchmark models, measure tok/s, or refresh the README performance table.
---

# Skill: omlx-benchmark

## /omlx-benchmark

Run oMLX throughput benchmarks against the local oMLX server and turn the
results into a README-ready table. Follow each step in order.

## Prerequisites

- [ ] Read the server connection info from `~/.omlx/settings.json`: `auth.api_key`,
      `server.host` (treat `0.0.0.0` as `127.0.0.1` for the client), `server.port`
      (fallback 8000). All admin API calls use `Authorization: Bearer <api_key>`.
- [ ] Ask the user (or infer from context) which model(s) to benchmark. Model IDs
      as listed by the server, e.g. `GLM-5.3-Flash-oQ4-mtp`.
- [ ] The bundled script `scripts/run_bench.py` handles start/poll/parse. Verify it
      is next to this SKILL.md; all paths below are relative to this skill's base dir.
- [ ] Keep the default cache warm-up enabled (`--warmup 1`). Do not pass
      `--warmup 0` unless the user explicitly asks for cold numbers — the server's
      built-in quick warm-up leaves the first short test ~44% slower after idle.

## How the oMLX throughput benchmark works (source of truth: `omlx/admin/benchmark.py` in the oMLX repo)

- Driven entirely through the admin API:
  - `POST /admin/api/bench/start` — body: `{model_id, prompt_lengths, generation_length, batch_sizes, context_profile, warmup_mode, align_prompt_to_ane, force_lm_engine}`. Returns `{bench_id, status, total_tests}`. Rejects with **409** if any throughput/context/ANE benchmark is already running.
  - `GET /admin/api/bench/{bench_id}/results` — poll until `status` is `completed`
      (terminal statuses are `completed`, `cancelled`, `error`; on `error` the
      `error` field carries the message).
  - `POST /admin/api/bench/{bench_id}/cancel` — cancel a stuck run.
- The server **loads the model itself**, runs a JIT/shader warm-up, runs the tests,
  then **unloads the model** at the end. Worse, at the start of every bench it
  **unloads ALL currently loaded models** and restores none of them — after a
  bench the engine pool is empty and client traffic (e.g. OpenCode) has nothing
  to talk to until a model loads on demand. Do not pre-load or unload manually;
  do not send other requests to the server during a run (they contend with the
  measurement). `run_bench.py` mitigates this: it snapshots the loaded model
  ids before benching and re-loads them after (also on failure paths). Pinned
  models in `model_settings.json` are only re-preloaded at server startup or
  via `POST /admin/api/reload` — a bench does not re-pin them.
- **Single-request tests**: prompt lengths must be from
  `[1024, 4096, 8192, 16384, 32768, 65536, 131072, 200000]` (validated server-side).
  Each yields `pp` (prompt length), `tg` (generation length), `processing_tps`
  (prefill tok/s), `gen_tps` (decode tok/s), `ttft_ms`, `peak_memory_bytes`.
- **Batch tests**: `batch_sizes` from `[2, 4, 8]`. Batch tests ALWAYS run at
  **pp1024** with unique UUID-prefixed prompts (no cache hits) — you cannot batch
  at other prompt lengths with this endpoint. Each yields aggregate `pp_tps`
  (total prefill tok/s) and `tg_tps` (total decode tok/s across the batch).
- `generation_length` default is 128. Prefer **256** for stable decode numbers;
  longer is fine but linearly slows the run.
- `context_profile` picks the prompt corpus: `code_python` (default, 4.0
  chars/token), `code_mixed` (3.5), `novel_en` (4.0), `novel_ja` (1.6),
  `novel_ko` (1.35). Use `code_python` for agentic-workload numbers.
- Warm-up is built in (`warmup_mode: "quick"`) but is not sufficient for the
  first short test after an idle period — that is why `run_bench.py` runs its
  own throwaway warm-up bench first (see Step 2). Models pinned in
  `model_settings.json` stay pinned; the bench still unloads and reloads
  around itself.

## Execution Order

### Step 1 — Plan the run set

Default set per model (matches the README methodology — ask to override):

- Single: `pp = [1024, 4096, 32768, 131072]` — short turn, typical agent prompt,
  half the 64K default context, long-context reviewer workload.
- Batch: `[2, 4, 8]` at pp1024 (fixed by the tool).
- `generation_length: 256`, `context_profile: code_python`.

Skip pp lengths above the model's configured `max_context_window`
(`~/.omlx/model_settings.json`, per-model key). `run_bench.py` enforces this
itself — it drops out-of-range pp values with a warning and aborts if nothing
is left, so an explicit user override is the only way to test beyond the
window. pp200000 only for the 1M-context model, and only on request.

One bench run = one POST covering all requested pp values and batch sizes
(`total_tests = len(prompt_lengths) + len(batch_sizes) * 2`). Do not split.

### Step 2 — Run

Run warm-up + recording in a single `run_bench.py` invocation — the script
fires its throwaway warm-up bench(es) automatically before the first recorded
run (do not disable; see Prerequisites):

```
python3 <skill_dir>/scripts/run_bench.py \
  --model "<model_id>" \
  --pp 1024 4096 32768 131072 \
  --batch 2 4 8 \
  --gen 256 \
  --runs 3
```

`--runs N` runs the recorded bench N times sequentially (default 1). Use **at
least 3** when the numbers will be published or compared against: each run
writes its own raw JSON and the script prints an aggregate table of
mean ± stddev (CV%) [min–max] per metric at the end. `--runs 1` prints the
per-run tables only, no stats.

File naming: every output of one invocation shares a label (default
`<model>-<YYYYmmdd-HHMMSS>`, override with `--label`). Files are written to
`<repo-root>/benchmarks/` (the git repo root, found by walking up from the
working directory; created if missing) as `<label>.json` for a single run or
`<label>-run1.json` … `<label>-runN.json` for multiple runs; `--out` still
overrides. The label ties a collection together — pass all `<label>*.json`
files to `summarize.py` (Step 3).

Before the recorded run, the script fires a throwaway warm-up bench (pp1024
only, no batches, gen 128, same model and profile) and discards its results, so
JIT/shader caches are hot when recording starts. Measured effect (2026-10-21,
GLM-5.3-Flash-oQ4-mtp): the first short test of an idle server ran prefill ~44%
slower cold (293.9 vs ~517 tok/s) without warm-up. `--warmup 0` disables it;
`--warmup N` runs N throwaway benches. Each warm-up costs ~10 s plus model
load; a failed warm-up aborts before recording (never record cold numbers
silently).

The script reads connection settings from `~/.omlx/settings.json`, runs the
warm-up benches (if enabled), starts each recorded bench, polls results, and
prints per-run summary tables plus the raw JSON paths, then the aggregate stats
table when `--runs > 1`.
Timeouts: a full 4-pp + 3-batch run can take several minutes (pp131072 prefill
dominates); let it run, do not poll with separate curl calls.

For multiple models, run them sequentially — the endpoint enforces one bench at
a time anyway (409).

### Step 3 — Report

Run the summarizer on the raw JSONs from Step 2 — it produces the full markdown
report (aggregate stats table, batch table, per-run tables, methodology line)
and derives its output filename from the shared label:

```
python3 <skill_dir>/scripts/summarize.py <label>-run1.json <label>-run2.json <label>-run3.json
# writes <repo-root>/benchmarks/<label>.md
```

`summarize.py` reads `scheduler.max_concurrent_requests` from
`~/.omlx/settings.json` and adds the batching note automatically when a batch
size exceeds it. It does not judge outliers or add commentary — after running
it, the agent should read the per-run tables and append any findings (e.g. a
first-run cold-cache outlier) as a short note under the affected section.

The summarizer's aggregate columns (single-request `pp` is the server's
measured prompt-token count, `requested_pp` is what was asked):

| pp | tg | Prefill tok/s | Decode tok/s | TTFT ms |
|---|---|---|---|---|
| 1024 | 256 | mean ± σ (CV%) [min–max] of processing_tps | ... of gen_tps | ... of ttft_ms |

and a batching table:

| Batch | pp | Aggregate decode tok/s | vs 1x |
|---|---|---|---|
| 2x | 1024 | mean ± σ of tg_tps | mean tg_tps / mean single pp1024 gen_tps |

The `1x (single)` baseline row is derived from the pp1024 single result — it is
kept in the table so the speedup column has its reference. The methodology line
is emitted verbatim by the summarizer, adapted to what was actually run:

> oMLX throughput benchmark via the admin API, MTP enabled, server defaults,
> Code (Python) prompts, 256 generated tokens, decode = single-request gen_tps,
> batch = aggregate tg_tps at pp1024.

## Hard Rules

- Never fire the benchmark while another benchmark, ANE tune, or context bench is
  active — the server returns 409; report it and wait rather than retrying blindly.
- Do not send chat/agent traffic to the server during a run.
- Do not edit `~/.omlx/*` from this skill (read-only).
- Report measured numbers verbatim — never round up to hit an expectation, and
  label decode numbers with their pp (decode tok/s degrades with context length).
- If a run fails, read `error` from the results payload and surface it verbatim.