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

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from bench_common import collect, fmt_stats, project_output_dir

VALID_PP: list[int] = [1024, 4096, 8192, 16384, 32768, 65536, 131072, 200000]
VALID_BATCH: list[int] = [2, 4, 8]
VALID_PROFILES: list[str] = ["code_python", "code_mixed", "novel_en", "novel_ja", "novel_ko"]


def api(
    method: str,
    url: str,
    api_key: str,
    body: dict[str, Any] | None = None,
    timeout: float = 60,
) -> dict[str, Any]:
    """Call one admin API endpoint and decode the JSON response.

    Args:
        method: HTTP method, e.g. "GET" or "POST".
        url: Absolute admin API URL.
        api_key: Bearer token for the Authorization header.
        body: Optional JSON-serializable request payload.
        timeout: Socket timeout in seconds.

    Returns:
        The decoded JSON response.

    Raises:
        urllib.error.HTTPError: On a non-2xx response.
        urllib.error.URLError: When the server is unreachable.
    """
    req = urllib.request.Request(url, method=method)
    req.add_header("Authorization", f"Bearer {api_key}")
    data = None
    if body is not None:
        req.add_header("Content-Type", "application/json")
        data = json.dumps(body).encode()
    with urllib.request.urlopen(req, data=data, timeout=timeout) as resp:
        return json.loads(resp.read())


def load_connection(args: argparse.Namespace) -> tuple[str, int, str | None]:
    """Resolve the server connection settings.

    Args:
        args: Parsed CLI args; --host/--port/--api-key win when given.

    Returns:
        (host, port, api_key) from CLI flags, else ~/.omlx/settings.json,
        else the built-in defaults (127.0.0.1, 8000, None).
    """
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


def load_context_limit(model_id: str) -> int | None:
    """Look up a model's context window in the installed model settings.

    Args:
        model_id: Server-form model id, e.g. GLM-5.3-Flash-oQ4-mtp.

    Returns:
        max_context_window for the model, or None when the file, entry,
        or field is missing.
    """
    settings_path = Path.home() / ".omlx" / "model_settings.json"
    if not settings_path.exists():
        return None
    try:
        entry = json.loads(settings_path.read_text()).get("models", {}).get(model_id, {})
        return entry.get("max_context_window")
    except (json.JSONDecodeError, OSError):
        return None


def model_exists(base: str, api_key: str, model_id: str) -> tuple[bool | None, list[str] | None]:
    """Pre-flight a model id against the server's model list.

    Args:
        base: Admin API base URL.
        api_key: Bearer token.
        model_id: The model id to look for.

    Returns:
        (True, None) when present; (False, available-ids) when absent;
        (None, None) when the check itself fails — the real bench call
        should decide then.
    """
    try:
        data = api("GET", f"{base}/models", api_key)
    except Exception:
        return None, None
    items = data.get("models", data.get("data", []))
    ids = [m.get("id") for m in items if isinstance(m, dict) and m.get("id")]
    if model_id in ids:
        return True, None
    return False, ids


def loaded_model_ids(base: str, api_key: str) -> list[str] | None:
    """Snapshot the ids of currently loaded models.

    Args:
        base: Admin API base URL.
        api_key: Bearer token.

    Returns:
        Loaded model ids, or None when the snapshot fails — the caller
        then skips restore instead of acting on partial knowledge.
    """
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


def restore_loaded_models(
    base: str, api_key: str, model_ids: list[str], timeout: float
) -> None:
    """Re-load models the benchmark unloaded.

    The server's benchmark unloads every loaded model and only unloads the
    bench model at the end — nothing restores prior state. Best effort:
    failures are reported but never mask the bench results.

    Args:
        base: Admin API base URL.
        api_key: Bearer token.
        model_ids: Model ids to re-load.
        timeout: Per-request timeout in seconds.
    """
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


def run_one(
    base: str,
    api_key: str,
    body: dict[str, Any],
    timeout: float,
    poll_interval: int = 5,
) -> dict[str, Any]:
    """Start one bench and poll it to a terminal status.

    Args:
        base: Admin API base URL.
        api_key: Bearer token.
        body: /bench/start payload (model, pp, batch, gen, profile).
        timeout: Overall deadline for the poll loop, in seconds.
        poll_interval: Seconds between result polls.

    Returns:
        The final results dict (status completed, cancelled, or error).

    Raises:
        SystemExit: When the bench cannot start, a poll fails, or the
            deadline passes (the bench is cancelled first).
    """
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
    # Best effort: a failed cancel still leaves the bench to expire server-side.
    try:
        api("POST", f"{base}/bench/{bench_id}/cancel", api_key, {})
    except Exception:
        pass
    sys.exit(1)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments.

    Args:
        argv: Argument list; defaults to sys.argv[1:].

    Returns:
        The parsed namespace (separated from main for testability).
    """
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
    return p.parse_args(argv)


def validate_test_args(args: argparse.Namespace) -> None:
    """Reject pp/batch values outside the server's supported sets.

    Args:
        args: Parsed CLI args; --pp and --batch are checked here.

    Raises:
        SystemExit: With the invalid and valid values, when a test point is
            unsupported or both lists are empty.
    """
    bad_pp = [x for x in args.pp if x not in VALID_PP]
    bad_batch = [x for x in args.batch if x not in VALID_BATCH]
    if bad_pp or bad_batch or (not args.pp and not args.batch):
        sys.exit(f"Invalid: pp={bad_pp} (valid {VALID_PP}), batch={bad_batch} (valid {VALID_BATCH})")


def apply_context_limit(args: argparse.Namespace) -> None:
    """Fit the requested test points to the model's context window.

    Args:
        args: Parsed CLI args; --pp may be trimmed in place.

    Raises:
        SystemExit: When every pp value exceeds the window, or batch runs
            are requested although pp1024 does not fit.
    """
    limit = load_context_limit(args.model)
    if limit is None:
        return
    too_big = [x for x in args.pp if x > limit]
    if too_big:
        args.pp = [x for x in args.pp if x <= limit]
        print(f"Dropping pp {too_big} — exceeds {args.model} max_context_window ({limit})")
        if not args.pp:
            sys.exit(f"No pp values left after dropping those above the {limit}-token context window")
    if args.batch and 1024 > limit:
        sys.exit(f"Batch tests always run at pp1024, which exceeds the {limit}-token context window")


def resolve_connection(args: argparse.Namespace) -> tuple[str, str]:
    """Resolve the connection and require an api key.

    Args:
        args: Parsed CLI args.

    Returns:
        (base URL, api_key) for the admin API.

    Raises:
        SystemExit: When no api_key is available from --api-key or
            ~/.omlx/settings.json.
    """
    host, port, api_key = load_connection(args)
    if not api_key:
        sys.exit("No api_key found in ~/.omlx/settings.json and none passed via --api-key")
    return f"http://{host}:{port}/admin/api", api_key


def preflight_model(base: str, api_key: str, model_id: str) -> None:
    """Fail fast when the model id is not on the server.

    Args:
        base: Admin API base URL.
        api_key: Bearer token.
        model_id: The model id to verify.

    Raises:
        SystemExit: With the available ids when the model is absent.
    """
    ok, ids = model_exists(base, api_key, model_id)
    if ok is False:
        sys.exit(
            f"Model not found on server: {model_id}\n"
            f"Available: {', '.join(ids)}\n"
            "(Model ids must use the exact server form, e.g. GLM-5.3-Flash-oQ4-mtp)"
        )


def snapshot_loaded_models(base: str, api_key: str) -> list[str]:
    """Record which models are loaded so the bench can restore them.

    The server-side benchmark unloads everything without restoring anything,
    so this snapshot is taken before any bench starts.

    Args:
        base: Admin API base URL.
        api_key: Bearer token.

    Returns:
        The loaded model ids (empty when none are loaded or the snapshot
        fails — restore is then skipped).
    """
    ids = loaded_model_ids(base, api_key) or []
    if ids:
        print("Loaded models (restored after bench): " + ", ".join(ids))
    return ids


def run_warmups(base: str, api_key: str, args: argparse.Namespace) -> None:
    """Run the requested number of throwaway warm-up benches.

    Warm-ups run pp1024 only, no batches, gen 128, so JIT/shader caches are
    hot before recording.

    Args:
        base: Admin API base URL.
        api_key: Bearer token.
        args: Parsed CLI args; --warmup and --profile are used here.

    Raises:
        SystemExit: When a warm-up bench fails.
    """
    warm_body: dict[str, Any] = {
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


def out_path_for(args: argparse.Namespace, run_i: int, label: str) -> Path:
    """Compute the raw-JSON output path for one run.

    Args:
        args: Parsed CLI args; --out overrides the default location.
        run_i: 1-based run number.
        label: Shared file id for this invocation.

    Returns:
        --out unchanged for a single run, a -runK sibling for multiple,
        or <repo-root>/benchmarks/<label>[-runK].json by default.
    """
    if args.out:
        p = Path(args.out)
        if args.runs > 1:
            return p.with_name(f"{p.stem}-run{run_i}{p.suffix}")
        return p
    name = f"{label}.json" if args.runs == 1 else f"{label}-run{run_i}.json"
    out_dir = project_output_dir()
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir / name


def run_recorded_benches(
    base: str, api_key: str, args: argparse.Namespace
) -> list[dict[str, Any]]:
    """Run the recorded benches and persist each run's raw JSON.

    Args:
        base: Admin API base URL.
        api_key: Bearer token.
        args: Parsed CLI args; --runs, --label, --out, and the bench body
            fields are used here.

    Returns:
        The result dicts of all completed runs, in run order.

    Raises:
        SystemExit: When a bench ends with an error or a non-completed
            status.
    """
    body: dict[str, Any] = {
        "model_id": args.model,
        "prompt_lengths": args.pp,
        "batch_sizes": args.batch,
        "generation_length": args.gen,
        "context_profile": args.profile,
    }
    label = args.label or f"{args.model.replace('/', '_')}-{time.strftime('%Y%m%d-%H%M%S')}"
    all_runs: list[dict[str, Any]] = []
    for run_i in range(1, args.runs + 1):
        if run_i > 1:
            print(f"\n=== Run {run_i}/{args.runs} ===")
        results = run_one(base, api_key, body, args.timeout)

        out = out_path_for(args, run_i, label)
        out.write_text(json.dumps(results, indent=2))
        print(f"Raw results: {out}\nStatus: {results.get('status')}")
        if results.get("error"):
            sys.exit(f"Bench error: {results['error']}")
        if results.get("status") != "completed":
            sys.exit(f"Bench ended with status: {results.get('status')}")
        all_runs.append(results)
    return all_runs


def print_stats(all_runs: list[dict[str, Any]]) -> None:
    """Print the aggregate table over all recorded runs.

    Args:
        all_runs: Result dicts from every recorded run.
    """
    print(f"\n### Aggregate over {len(all_runs)} runs (mean ± stddev (CV%) [min–max])")
    print("\n| pp | Prefill tok/s | Decode tok/s | TTFT ms |")
    print("|---|---|---|---|")
    pps = sorted({r.get("pp", 0) for res in all_runs for r in res["results"] if r.get("test_type") == "single"})
    for pp in pps:
        print(
            f"| {pp} | {fmt_stats(collect(all_runs, 'single', 'processing_tps', pp=pp))} "
            f"| {fmt_stats(collect(all_runs, 'single', 'gen_tps', pp=pp))} "
            f"| {fmt_stats(collect(all_runs, 'single', 'ttft_ms', pp=pp))} |"
        )
    batch_sizes = sorted({r.get("batch_size", 0) for res in all_runs for r in res["results"] if r.get("test_type") == "batch"})
    if batch_sizes:
        print("\n| Batch | Aggregate decode tok/s |")
        print("|---|---|")
        for b in batch_sizes:
            print(f"| {b}x | {fmt_stats(collect(all_runs, 'batch', 'tg_tps', batch_size=b))} |")


def print_batch_rows(singles: list[dict[str, Any]], batches: list[dict[str, Any]]) -> None:
    """Print the batch table rows, relative to the pp1024 single rate.

    Args:
        singles: Single-test rows of the last recorded run.
        batches: Batch-test rows of the last recorded run.
    """
    if not batches:
        return
    baseline = next(
        (
            r.get("gen_tps")
            for r in singles
            if r.get("pp") == 1024 or r.get("requested_pp") == 1024
        ),
        None,
    )
    print("\n| Batch | pp | Aggregate decode tok/s | vs 1x |")
    print("|---|---|---|---|")
    if baseline:
        print(f"| 1x (single) | 1024 | {baseline} | 1.00 |")
    for r in sorted(batches, key=lambda r: r.get("batch_size", 0)):
        speedup = f"{r['tg_tps'] / baseline:.2f}" if baseline else "-"
        print(f"| {r.get('batch_size')}x | {r.get('pp')} | {r.get('tg_tps')} | {speedup} |")


def print_tables(all_runs: list[dict[str, Any]]) -> None:
    """Print the per-run tables for the last recorded run.

    Args:
        all_runs: Result dicts from every recorded run; only the last run
            is tabulated, and its pp1024 decode rate is the speedup baseline.
    """
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
    print_batch_rows(singles, batches)


def main() -> None:
    """Orchestrate the benchmark: validate, preflight, warm up, record,
    report, then restore the previously loaded models."""
    args = parse_args()
    validate_test_args(args)
    apply_context_limit(args)
    base, api_key = resolve_connection(args)
    preflight_model(base, api_key, args.model)

    previously_loaded = snapshot_loaded_models(base, api_key)
    try:
        if args.warmup > 0:
            run_warmups(base, api_key, args)
        all_runs = run_recorded_benches(base, api_key, args)
        print_tables(all_runs)
        if args.runs > 1:
            print_stats(all_runs)
    finally:
        if previously_loaded:
            print("\nRestoring previously loaded models...")
            restore_loaded_models(base, api_key, previously_loaded, args.timeout)


if __name__ == "__main__":
    main()