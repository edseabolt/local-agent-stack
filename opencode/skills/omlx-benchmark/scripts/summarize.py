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

from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
from pathlib import Path
from typing import Any

from bench_common import collect, fmt_stats, project_output_dir


def load_runs(paths: list[str]) -> list[dict[str, Any]]:
    """Load raw bench JSONs and validate each is a completed bench.

    Args:
        paths: Paths to raw JSON files written by run_bench.py.

    Returns:
        The parsed result dicts, each tagged with "_path" (its source file)
        for provenance lines in the report.

    Raises:
        SystemExit: When a file's status is not "completed" or it carries
            no results.
    """
    runs: list[dict[str, Any]] = []
    for p in paths:
        data = json.loads(Path(p).read_text())
        if data.get("status") != "completed" or not data.get("results"):
            sys.exit(f"{p}: status={data.get('status')!r}, no results — not a completed bench")
        data["_path"] = p
        runs.append(data)
    return runs


def shared_label(paths: list[str]) -> str:
    """Derive the files' shared label for the default report filename.

    Args:
        paths: Paths to raw JSON files.

    Returns:
        The common filename stem with -runK suffixes stripped, or the
        longest common prefix ending at a `-` boundary when the stems
        differ beyond that.
    """
    stems = [re.sub(r"-run\d+$", "", Path(p).stem) for p in paths]
    if len(set(stems)) == 1:
        return stems[0]
    # Fall back to the longest common prefix ending at a `-` boundary.
    prefix = stems[0]
    for s in stems[1:]:
        while not s.startswith(prefix):
            prefix = prefix[:-1]
        prefix = prefix.rstrip("-0123456789")
    return prefix or stems[0]


def bench_profile(runs: list[dict[str, Any]]) -> str:
    """Read the context profile shared by all runs.

    Args:
        runs: Raw bench result dicts.

    Returns:
        The context_profile of the first run, or "unknown" when it was
        not recorded.
    """
    return runs[0].get("context_profile", "unknown")


def single_tg_values(runs: list[dict[str, Any]]) -> list[int]:
    """Collect the generation lengths used by the runs' single tests.

    Args:
        runs: Raw bench result dicts.

    Returns:
        Sorted distinct "tg" values across all single-test rows.
    """
    return sorted({r.get("tg") for res in runs for r in res["results"] if r.get("test_type") == "single"})


def scheduler_note(runs: list[dict[str, Any]]) -> str | None:
    """Build the scheduler-concurrency note for the batching section.

    Args:
        runs: Raw bench result dicts.

    Returns:
        An explanatory note when a batch size exceeds
        scheduler.max_concurrent_requests (the queued waves are not true
        parallelism), otherwise None.
    """
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


def report_header(runs: list[dict[str, Any]], model_id: str) -> list[str]:
    """Build the report's title block.

    Args:
        runs: Raw bench result dicts.
        model_id: The model id to name the report after.

    Returns:
        Markdown lines: title, run count with profile and generation
        lengths, and the raw-result provenance list.
    """
    profile = bench_profile(runs)
    gen = single_tg_values(runs)
    lines = [f"# {model_id} — oMLX throughput benchmark", ""]
    lines.append(
        f"{len(runs)} recorded run(s) aggregated. Profile: `{profile}`, gen: "
        f"{', '.join(str(g) for g in gen)}."
    )
    lines += ["", "Raw results:"]
    for res in runs:
        bench_id = res.get("bench_id", "unknown")
        lines.append(f"- `{Path(res['_path']).name}` (bench `{bench_id}`)")
    lines.append("")
    return lines


def single_stats_section(runs: list[dict[str, Any]], n: int) -> list[str]:
    """Build the aggregate single-request table.

    Args:
        runs: Raw bench result dicts.
        n: Number of recorded runs, for the section heading.

    Returns:
        Markdown lines: one row per prompt length with mean ± stddev per
        metric.
    """
    pps = sorted({r.get("pp", 0) for res in runs for r in res["results"] if r.get("test_type") == "single"})
    lines = [f"## Single request — mean ± stddev (CV%) [min–max], n={n}", ""]
    lines += ["| pp | tg | Prefill tok/s | Decode tok/s | TTFT ms |", "|---|---|---|---|---|"]
    for pp in pps:
        tg = next(
            (r.get("tg") for res in runs for r in res["results"] if r.get("test_type") == "single" and r.get("pp") == pp),
            "",
        )
        lines.append(
            f"| {pp} | {tg} | {fmt_stats(collect(runs, 'single', 'processing_tps', pp=pp))} "
            f"| {fmt_stats(collect(runs, 'single', 'gen_tps', pp=pp))} "
            f"| {fmt_stats(collect(runs, 'single', 'ttft_ms', pp=pp))} |"
        )
    lines.append("")
    return lines


def batch_section(runs: list[dict[str, Any]], n: int) -> list[str]:
    """Build the aggregate batching table at pp1024.

    Args:
        runs: Raw bench result dicts.
        n: Number of recorded runs, for the section heading.

    Returns:
        Markdown lines: the batching table with the pp1024 single decode
        rate as baseline, preceded by the scheduler note when a batch size
        exceeds the scheduler's concurrency. Empty when there are no batch
        tests.
    """
    batch_sizes = sorted({r.get("batch_size", 0) for res in runs for r in res["results"] if r.get("test_type") == "batch"})
    if not batch_sizes:
        return []
    lines = [f"## Batching (pp1024) — mean ± stddev, n={n}", ""]
    note = scheduler_note(runs)
    if note:
        lines += [note, ""]
    pps = {r.get("pp", 0) for res in runs for r in res["results"] if r.get("test_type") == "single"}
    baseline = statistics.mean(collect(runs, "single", "gen_tps", pp=1024)) if 1024 in pps else None
    lines += ["| Batch | pp | Aggregate decode tok/s | vs 1x |", "|---|---|---|---|"]
    if baseline:
        lines.append(f"| 1x (single) | 1024 | {fmt_stats([baseline])} | 1.00 |")
    for b in batch_sizes:
        mean_tg = statistics.mean(collect(runs, "batch", "tg_tps", batch_size=b))
        speedup = f"{mean_tg / baseline:.2f}" if baseline else "-"
        lines.append(f"| {b}x | 1024 | {fmt_stats(collect(runs, 'batch', 'tg_tps', batch_size=b))} | {speedup} |")
    lines.append("")
    return lines


def per_run_section(runs: list[dict[str, Any]]) -> list[str]:
    """Build the per-run tables for traceability back to the raw JSON.

    Args:
        runs: Raw bench result dicts.

    Returns:
        Markdown lines: one single-request table per run, keyed by source
        filename and bench id.
    """
    lines = [f"## Per-run tables (n={len(runs)})"]
    for res in runs:
        bench_id = res.get("bench_id", "unknown")
        lines += ["", f"### {Path(res['_path']).name} (`{bench_id}`)", ""]
        lines += ["| pp | tg | Prefill tok/s | Decode tok/s | TTFT ms |", "|---|---|---|---|---|"]
        singles = sorted((r for r in res["results"] if r.get("test_type") == "single"), key=lambda r: r.get("pp", 0))
        for r in singles:
            lines.append(
                f"| {r.get('pp')} | {r.get('tg')} | {r.get('processing_tps')} "
                f"| {r.get('gen_tps')} | {r.get('ttft_ms')} |"
            )
    lines.append("")
    return lines


def methodology_line(runs: list[dict[str, Any]]) -> str:
    """Build the one-line methodology note that closes the report.

    Args:
        runs: Raw bench result dicts.

    Returns:
        A blockquote line stating the bench conditions (profile, generation
        length, metric definitions) and the aggregation format.
    """
    profile = bench_profile(runs)
    gen = single_tg_values(runs)
    return (
        f"> oMLX throughput benchmark via the admin API, MTP enabled, server defaults, "
        f"{profile} prompts, {gen[0] if len(gen) == 1 else 'varied'} generated tokens, "
        f"decode = single-request gen_tps, batch = aggregate tg_tps at pp1024. n={len(runs)} run(s), "
        "reported as mean ± stddev (CV%) [min–max]."
    )


def report(runs: list[dict[str, Any]], model_id: str | None = None) -> str:
    """Assemble the full markdown report from the per-section helpers.

    Args:
        runs: Raw bench result dicts (as returned by load_runs).
        model_id: Model id to name the report after; falls back to the one
            recorded in the raw JSON.

    Returns:
        The complete markdown report.
    """
    first = runs[0]
    model_id = model_id or first.get("model_id") or "(model not recorded in raw JSON)"
    n = len(runs)
    lines = report_header(runs, model_id)
    lines += single_stats_section(runs, n)
    lines += batch_section(runs, n)
    lines += per_run_section(runs)
    lines.append(methodology_line(runs))
    lines.append("")
    return "\n".join(lines)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments.

    Args:
        argv: Argument list; defaults to sys.argv[1:].

    Returns:
        The parsed namespace (separated from main for testability).
    """
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("json_files", nargs="+")
    p.add_argument("--out", default=None, help="output markdown path (default: <repo-root>/benchmarks/<shared-label>.md)")
    p.add_argument("--model", default=None, help="model id if not recorded in the raw JSON")
    return p.parse_args(argv)


def recover_model_id(args: argparse.Namespace, runs: list[dict[str, Any]]) -> str | None:
    """Determine the model id for the report title.

    Args:
        args: Parsed CLI args; --model wins when given.
        runs: Raw bench result dicts.

    Returns:
        The model id, or None to let report() fall back to the raw JSON's
        model_id — recovery from the shared label only happens for raw JSON
        that predates model_id recording.
    """
    if args.model:
        return args.model
    if runs[0].get("model_id"):
        return None
    label = shared_label(args.json_files)
    return re.sub(r"-\d{8}-\d{6}(-run\d+)?$", "", label) or None


def main() -> None:
    """Orchestrate the report: load runs, recover the model id, write the
    markdown file."""
    args = parse_args()
    runs = load_runs(args.json_files)
    model_id = recover_model_id(args, runs)

    out = Path(args.out) if args.out else project_output_dir() / (shared_label(args.json_files) + ".md")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(report(runs, model_id=model_id))
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()