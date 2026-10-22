#!/usr/bin/env python3
"""Run an oMLX throughput benchmark via the admin API and print results.

Reads host/port/api_key from ~/.omlx/settings.json (or --host/--port/--api-key
overrides). Starts a bench, polls until completion, writes raw JSON, prints a
markdown summary.

Usage:
  run_bench.py --model MODEL [--pp 1024 4096 ...] [--batch 2 4 8]
               [--gen 256] [--profile code_python] [--warmup 1] [--runs 3]
               [--timeout 3600]

With `--runs N` (N > 1) the recorded bench runs N times sequentially; each run
writes its own raw JSON (`-runK` suffix) and an aggregate stats table (mean ±
stddev (CV%) [min–max]) is printed at the end. Use at least 3 runs for stable
stats.

A warm-up bench (pp1024 only, no batches, gen 128) is run first by default and
its results discarded, so JIT/shader caches are hot before recording. Observed
effect (2026-10-21): first short test after idle ran prefill 44% slower
(293.9 vs ~517 tok/s) without this.
"""

import argparse
import json
import statistics
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

VALID_PP = [1024, 4096, 8192, 16384, 32768, 65536, 131072, 200000]
VALID_BATCH = [2, 4, 8]
VALID_PROFILES = ["code_python", "code_mixed", "novel_en", "novel_ja", "novel_ko"]


def project_output_dir():
    """Default output dir: <git-repo-root>/benchmarks, else ./benchmarks."""
    d = Path.cwd()
    for p in (d, *d.parents):
        if (p / ".git").exists():
            return p / "benchmarks"
    return d / "benchmarks"


def load_connection(args):
    settings_path = Path.home() / ".omlx" / "settings.json"
    host, port, api_key = "127.0.0.1", 8000, None
    if settings_path.exists():
        data = json.loads(settings_path.read_text())
        server = data.get("server", data)
        host = server.get("host", host)
        if host == "0.0.0.0":
            host = "127.0.0.1"  # binding address, not a client target
        port = int(server.get("port", port))
        api_key = data.get("auth", {}).get("api_key") or data.get("api_key")
    return args.host or host, args.port or port, args.api_key or api_key


def api(method, url, api_key, body=None, timeout=60):
    req = urllib.request.Request(url, method=method)
    req.add_header("Authorization", f"Bearer {api_key}")
    data = None
    if body is not None:
        req.add_header("Content-Type", "application/json")
        data = json.dumps(body).encode()
    with urllib.request.urlopen(req, data=data, timeout=timeout) as resp:
        return json.loads(resp.read())


def load_context_limit(model_id):
    """Return max_context_window for the model, or None if unknown."""
    settings_path = Path.home() / ".omlx" / "model_settings.json"
    if not settings_path.exists():
        return None
    try:
        entry = json.loads(settings_path.read_text()).get("models", {}).get(model_id, {})
        return entry.get("max_context_window")
    except (json.JSONDecodeError, OSError):
        return None


def model_exists(base, api_key, model_id):
    """Pre-flight: check the model id against the server's list. Returns
    (True, None) if present, (False, available-ids) if not, (None, None) if
    the check itself fails (server unreachable etc. — let the real call decide)."""
    try:
        data = api("GET", f"{base}/models", api_key)
    except Exception:
        return None, None
    items = data.get("models", data.get("data", []))
    ids = [m.get("id") for m in items if isinstance(m, dict) and m.get("id")]
    if model_id in ids:
        return True, None
    return False, ids


def loaded_model_ids(base, api_key):
    """Snapshot the ids of currently loaded models (None if unknown)."""
    try:
        data = api("GET", f"{base}/models", api_key)
    except Exception:
        return None
    items = data.get("models", data.get("data", []))
    return [
        m["id"]
        for m in items
        if isinstance(m, dict) and m.get("id") and m.get("loaded")
    ]


def restore_loaded_models(base, api_key, model_ids, timeout):
    """Re-load models the benchmark unloaded (POST /models/{id}/load).

    The server's benchmark unloads every loaded model and only unloads the
    bench model at the end — nothing restores prior state. Best effort:
    failures are reported but never mask the bench results."""
    from urllib.parse import quote

    for model_id in model_ids:
        try:
            api(
                "POST",
                f"{base}/models/{quote(model_id, safe='')}/load",
                api_key,
                {},
                timeout=timeout,
            )
            print(f"Restored loaded model: {model_id}")
        except Exception as e:
            print(f"WARNING: failed to restore {model_id}: {e}")


def run_one(base, api_key, body, timeout, poll_interval=5):
    """Start one bench and poll to a terminal status. Returns results dict."""
    try:
        start = api("POST", f"{base}/bench/start", api_key, body)
    except urllib.error.HTTPError as e:
        sys.exit(f"bench/start failed: HTTP {e.code} {e.read().decode(errors='replace')}")

    bench_id = start["bench_id"]
    total = start.get("total_tests")
    print(f"Bench {bench_id} started: {body['model_id']}, tests={total} (pp={body.get('prompt_lengths')}, batch={body.get('batch_sizes')}, gen={body.get('generation_length')})")

    deadline = time.time() + timeout
    while time.time() < deadline:
        time.sleep(poll_interval)
        try:
            data = api("GET", f"{base}/bench/{bench_id}/results", api_key)
        except urllib.error.HTTPError as e:
            sys.exit(f"poll failed: HTTP {e.code} {e.read().decode(errors='replace')}")
        if data.get("status") in ("completed", "cancelled", "error"):
            return data
    print("Timed out; cancelling")
    try:
        api("POST", f"{base}/bench/{bench_id}/cancel", api_key, {})
    except Exception:
        pass
    sys.exit(1)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--model", required=True)
    p.add_argument("--pp", type=int, nargs="*", default=[1024, 4096, 32768, 131072])
    p.add_argument("--batch", type=int, nargs="*", default=[2, 4, 8])
    p.add_argument("--gen", type=int, default=256)
    p.add_argument("--profile", default="code_python", choices=VALID_PROFILES)
    p.add_argument("--warmup", type=int, default=1,
                   help="number of throwaway warm-up benches before recording (0 = off)")
    p.add_argument("--runs", type=int, default=1,
                   help="number of recorded bench runs; stats are printed for >1 (use at least 3 for stable stats)")
    p.add_argument("--label", default=None,
                   help="file id shared by all outputs of this invocation (default: <model>-<YYYYmmdd-HHMMSS>)")
    p.add_argument("--host"), p.add_argument("--port", type=int), p.add_argument("--api-key")
    p.add_argument("--timeout", type=int, default=3600)
    p.add_argument("--out", default=None, help="path for raw JSON results")
    args = p.parse_args()

    bad_pp = [x for x in args.pp if x not in VALID_PP]
    bad_batch = [x for x in args.batch if x not in VALID_BATCH]
    if bad_pp or bad_batch or (not args.pp and not args.batch):
        sys.exit(f"Invalid: pp={bad_pp} (valid {VALID_PP}), batch={bad_batch} (valid {VALID_BATCH})")

    limit = load_context_limit(args.model)
    if limit is not None:
        too_big = [x for x in args.pp if x > limit]
        if too_big:
            args.pp = [x for x in args.pp if x <= limit]
            print(f"Dropping pp {too_big} — exceeds {args.model} max_context_window ({limit})")
            if not args.pp:
                sys.exit(f"No pp values left after dropping those above the {limit}-token context window")
        if args.batch and 1024 > limit:
            sys.exit(f"Batch tests always run at pp1024, which exceeds the {limit}-token context window")

    host, port, api_key = load_connection(args)
    if not api_key:
        sys.exit("No api_key found in ~/.omlx/settings.json and none passed via --api-key")
    base = f"http://{host}:{port}/admin/api"

    ok, ids = model_exists(base, api_key, args.model)
    if ok is False:
        sys.exit(
            f"Model not found on server: {args.model}\n"
            f"Available: {', '.join(ids)}\n"
            "(Model ids must use the exact server form, e.g. GLM-5.3-Flash-oQ4-mtp)"
        )

    # The server-side benchmark unloads ALL loaded models (and the bench model
    # at the end) without restoring anything, so snapshot the resident set now
    # and bring it back after the run — including on failure paths.
    previously_loaded = loaded_model_ids(base, api_key)
    if previously_loaded:
        print(
            "Loaded models (restored after bench): "
            + ", ".join(previously_loaded)
        )

    try:
        if args.warmup > 0:
            warm_body = {
                "model_id": args.model,
                "prompt_lengths": [1024],
                "batch_sizes": [],
                "generation_length": 128,
                "context_profile": args.profile,
            }
            for i in range(args.warmup):
                res = run_one(base, api_key, warm_body, args.timeout)
                if res.get("status") != "completed" or res.get("error"):
                    sys.exit(f"warm-up bench {i + 1} failed: {res.get('error') or res.get('status')}")
                print(f"Warm-up bench {i + 1}/{args.warmup} completed (results discarded)")

        body = {
            "model_id": args.model,
            "prompt_lengths": args.pp,
            "batch_sizes": args.batch,
            "generation_length": args.gen,
            "context_profile": args.profile,
        }

        all_runs = []
        label = args.label or f"{args.model.replace('/', '_')}-{time.strftime('%Y%m%d-%H%M%S')}"
        for run_i in range(1, args.runs + 1):
            if run_i > 1:
                print(f"\n=== Run {run_i}/{args.runs} ===")
            results = run_one(base, api_key, body, args.timeout)

            out = out_path_for(args, run_i, results, label)
            out.write_text(json.dumps(results, indent=2))
            print(f"Raw results: {out}\nStatus: {results.get('status')}")
            if results.get("error"):
                sys.exit(f"Bench error: {results['error']}")
            if results.get("status") != "completed":
                sys.exit(f"Bench ended with status: {results.get('status')}")
            all_runs.append(results)

        print_tables(all_runs)
        if args.runs > 1:
            print_stats(all_runs)
    finally:
        if previously_loaded:
            print("\nRestoring previously loaded models...")
            restore_loaded_models(base, api_key, previously_loaded, args.timeout)


def out_path_for(args, run_i, results, label):
    if args.out:
        p = Path(args.out)
        if args.runs > 1:
            return p.with_name(f"{p.stem}-run{run_i}{p.suffix}")
        return p
    name = f"{label}.json" if args.runs == 1 else f"{label}-run{run_i}.json"
    out_dir = project_output_dir()
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir / name


def fmt_stats(vals):
    m = statistics.mean(vals)
    s = statistics.stdev(vals) if len(vals) > 1 else 0.0
    return f"{m:.1f} ± {s:.1f} (CV {100 * s / m:.1f}%) [{min(vals):.1f}–{max(vals):.1f}]"


def print_stats(all_runs):
    def collect(test_type, key, pp=None, batch_size=None):
        return [
            r[key]
            for res in all_runs
            for r in res["results"]
            if r.get("test_type") == test_type
            and (pp is None or r.get("pp") == pp)
            and (batch_size is None or r.get("batch_size") == batch_size)
        ]

    print(f"\n### Aggregate over {len(all_runs)} runs (mean ± stddev (CV%) [min–max])")
    print("\n| pp | Prefill tok/s | Decode tok/s | TTFT ms |")
    print("|---|---|---|---|")
    for pp in sorted({r.get("pp", 0) for res in all_runs for r in res["results"] if r.get("test_type") == "single"}):
        print(
            f"| {pp} | {fmt_stats(collect('single', 'processing_tps', pp=pp))} "
            f"| {fmt_stats(collect('single', 'gen_tps', pp=pp))} "
            f"| {fmt_stats(collect('single', 'ttft_ms', pp=pp))} |"
        )
    batch_sizes = sorted({r.get("batch_size", 0) for res in all_runs for r in res["results"] if r.get("test_type") == "batch"})
    if batch_sizes:
        print("\n| Batch | Aggregate decode tok/s |")
        print("|---|---|")
        for b in batch_sizes:
            print(f"| {b}x | {fmt_stats(collect('batch', 'tg_tps', batch_size=b))} |")


def print_tables(all_runs):
    """Print per-run tables; the last run's baseline is used for speedup."""
    last = all_runs[-1]
    singles = [r for r in last["results"] if r.get("test_type") == "single"]
    batches = [r for r in last["results"] if r.get("test_type") == "batch"]

    print("\n| pp | tg | Prefill tok/s | Decode tok/s | TTFT ms |")
    print("|---|---|---|---|---|")
    for r in sorted(singles, key=lambda r: r.get("pp", 0)):
        print(
            f"| {r.get('pp')} | {r.get('tg')} | {r.get('processing_tps')} "
            f"| {r.get('gen_tps')} | {r.get('ttft_ms')} |"
        )

    baseline = next(
        (
            r.get("gen_tps")
            for r in singles
            if r.get("pp") == 1024 or r.get("requested_pp") == 1024
        ),
        None,
    )
    if batches:
        print("\n| Batch | pp | Aggregate decode tok/s | vs 1x |")
        print("|---|---|---|---|")
        if baseline:
            print(f"| 1x (single) | 1024 | {baseline} | 1.00 |")
        for r in sorted(batches, key=lambda r: r.get("batch_size", 0)):
            speedup = f"{r['tg_tps'] / baseline:.2f}" if baseline else "-"
            print(f"| {r.get('batch_size')}x | {r.get('pp')} | {r.get('tg_tps')} | {speedup} |")


if __name__ == "__main__":
    main()