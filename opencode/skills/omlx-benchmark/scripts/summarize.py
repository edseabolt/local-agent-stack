#!/usr/bin/env python3
"""Aggregate raw oMLX benchmark JSONs into a markdown report.

Takes one or more raw JSON files written by run_bench.py and writes a
markdown report containing per-run tables, aggregate stats (mean ± stddev,
CV%, min–max), the batching table with a scheduler-concurrency note, and the
methodology line.

The report filename defaults to the files' shared label (filename stem with
any `-runK` suffix stripped); override with --out.

Usage:
  summarize.py <results1.json> [results2.json ...] [--out report.md]
"""

import argparse
import json
import re
import statistics
import sys
from pathlib import Path


def project_output_dir():
    """Default output dir: <git-repo-root>/benchmarks, else ./benchmarks."""
    d = Path.cwd()
    for p in (d, *d.parents):
        if (p / ".git").exists():
            return p / "benchmarks"
    return d / "benchmarks"


def load_runs(paths):
    runs = []
    for p in paths:
        data = json.loads(Path(p).read_text())
        if data.get("status") != "completed" or not data.get("results"):
            sys.exit(f"{p}: status={data.get('status')!r}, no results — not a completed bench")
        data["_path"] = p
        runs.append(data)
    return runs


def shared_label(paths):
    stems = []
    for p in paths:
        stem = Path(p).stem
        stem = re.sub(r"-run\d+$", "", stem)
        stems.append(stem)
    if len(set(stems)) == 1:
        return stems[0]
    # Fall back to the longest common prefix ending at a `-` boundary.
    prefix = stems[0]
    for s in stems[1:]:
        while not s.startswith(prefix):
            prefix = prefix[:-1]
        prefix = prefix.rstrip("-0123456789")
    return prefix or stems[0]


def fmt(vals):
    m = statistics.mean(vals)
    s = statistics.stdev(vals) if len(vals) > 1 else 0.0
    line = f"{m:.1f} ± {s:.1f} (CV {100 * s / m:.1f}%)"
    if len(vals) > 1:
        line += f" [{min(vals):.1f}–{max(vals):.1f}]"
    return line


def collect(runs, test_type, key, pp=None, batch_size=None):
    return [
        r[key]
        for res in runs
        for r in res["results"]
        if r.get("test_type") == test_type
        and (pp is None or r.get("pp") == pp)
        and (batch_size is None or r.get("batch_size") == batch_size)
    ]


def scheduler_note(runs):
    max_conc = None
    settings = Path.home() / ".omlx" / "settings.json"
    if settings.exists():
        try:
            sched = json.loads(settings.read_text()).get("scheduler", {})
            max_conc = sched.get("max_concurrent_requests")
        except (json.JSONDecodeError, OSError):
            pass
    batch_sizes = sorted({r.get("batch_size", 0) for res in runs for r in res["results"] if r.get("test_type") == "batch"})
    if max_conc and batch_sizes and max(batch_sizes) > max_conc:
        top = max(batch_sizes)
        return (
            f"Note: `scheduler.max_concurrent_requests` is {max_conc} — the {top}× run sends "
            f"{top} requests but the scheduler admits {max_conc} and queues the rest, so "
            f"\"{top}×\" is {top} requests through a {max_conc}-wide pipe (multiple waves), "
            "not true parallelism. \"vs 1x\" is aggregate speedup; per-request latency spans "
            "the waves."
        )
    return None


def report(runs, model_id=None):
    first = runs[0]
    n = len(runs)
    gen = sorted({r.get("tg") for res in runs for r in res["results"] if r.get("test_type") == "single"})
    profile = first.get("context_profile", "unknown")
    model_id = model_id or first.get("model_id") or "(model not recorded in raw JSON)"

    lines = []
    lines.append(f"# {model_id} — oMLX throughput benchmark")
    lines.append("")
    lines.append(f"{n} recorded run(s) aggregated. Profile: `{profile}`, gen: "
                 f"{', '.join(str(g) for g in gen)}.")
    lines.append("")
    lines.append("Raw results:")
    for res in runs:
        bench_id = res.get("bench_id", "unknown")
        lines.append(f"- `{Path(res['_path']).name}` (bench `{bench_id}`)")
    lines.append("")

    # Aggregate single-request stats
    pps = sorted({r.get("pp", 0) for res in runs for r in res["results"] if r.get("test_type") == "single"})
    lines.append(f"## Single request — mean ± stddev (CV%) [min–max], n={n}")
    lines.append("")
    lines.append("| pp | tg | Prefill tok/s | Decode tok/s | TTFT ms |")
    lines.append("|---|---|---|---|---|")
    for pp in pps:
        tg = next(
            (r.get("tg") for res in runs for r in res["results"] if r.get("test_type") == "single" and r.get("pp") == pp),
            "",
        )
        lines.append(
            f"| {pp} | {tg} | {fmt(collect(runs, 'single', 'processing_tps', pp=pp))} "
            f"| {fmt(collect(runs, 'single', 'gen_tps', pp=pp))} "
            f"| {fmt(collect(runs, 'single', 'ttft_ms', pp=pp))} |"
        )
    lines.append("")

    # Batch stats + note
    batch_sizes = sorted({r.get("batch_size", 0) for res in runs for r in res["results"] if r.get("test_type") == "batch"})
    if batch_sizes:
        lines.append(f"## Batching (pp1024) — mean ± stddev, n={n}")
        lines.append("")
        note = scheduler_note(runs)
        if note:
            lines.append(note)
            lines.append("")
        baseline = statistics.mean(collect(runs, "single", "gen_tps", pp=1024)) if 1024 in pps else None
        lines.append("| Batch | pp | Aggregate decode tok/s | vs 1x |")
        lines.append("|---|---|---|---|")
        if baseline:
            lines.append(f"| 1x (single) | 1024 | {fmt([baseline])} | 1.00 |")
        for b in batch_sizes:
            speedup = f"{statistics.mean(collect(runs, 'batch', 'tg_tps', batch_size=b)) / baseline:.2f}" if baseline else "-"
            lines.append(f"| {b}x | 1024 | {fmt(collect(runs, 'batch', 'tg_tps', batch_size=b))} | {speedup} |")
        lines.append("")

    # Per-run tables for traceability
    lines.append(f"## Per-run tables (n={n})")
    for res in runs:
        bench_id = res.get("bench_id", "unknown")
        lines.append("")
        lines.append(f"### {Path(res['_path']).name} (`{bench_id}`)")
        lines.append("")
        lines.append("| pp | tg | Prefill tok/s | Decode tok/s | TTFT ms |")
        lines.append("|---|---|---|---|---|")
        singles = sorted((r for r in res["results"] if r.get("test_type") == "single"), key=lambda r: r.get("pp", 0))
        for r in singles:
            lines.append(
                f"| {r.get('pp')} | {r.get('tg')} | {r.get('processing_tps')} "
                f"| {r.get('gen_tps')} | {r.get('ttft_ms')} |"
            )
    lines.append("")

    lines.append(
        f"> oMLX throughput benchmark via the admin API, MTP enabled, server defaults, "
        f"{profile} prompts, {gen[0] if len(gen) == 1 else 'varied'} generated tokens, "
        f"decode = single-request gen_tps, batch = aggregate tg_tps at pp1024. n={n} run(s), "
        "reported as mean ± stddev (CV%) [min–max]."
    )
    lines.append("")
    return "\n".join(lines)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("json_files", nargs="+")
    p.add_argument("--out", default=None, help="output markdown path (default: <repo-root>/benchmarks/<shared-label>.md)")
    p.add_argument("--model", default=None, help="model id if not recorded in the raw JSON")
    args = p.parse_args()

    runs = load_runs(args.json_files)
    model_id = args.model
    if not model_id and not runs[0].get("model_id"):
        # Raw bench JSON predates model_id recording; the shared label embeds
        # the model id ("<model>-<YYYYmmdd-HHMMSS>-runN"), so recover it there.
        label = shared_label(args.json_files)
        model_id = re.sub(r"-\d{8}-\d{6}(-run\d+)?$", "", label) or None
    md = report(runs, model_id=model_id)

    out = Path(args.out) if args.out else project_output_dir() / (shared_label(args.json_files) + ".md")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(md)
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()