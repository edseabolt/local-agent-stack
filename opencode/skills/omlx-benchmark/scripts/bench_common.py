#!/usr/bin/env python3
"""Shared helpers for the oMLX benchmark scripts.

Holds the pieces both scripts need — output-dir resolution, result-row
filtering, and stats formatting — so the logic lives in exactly one place.
Stdlib only; imported by run_bench.py and summarize.py.
"""

from __future__ import annotations

import statistics
from pathlib import Path
from typing import Any


def project_output_dir() -> Path:
    """Resolve the default output dir for benchmark artifacts.

    Returns:
        <git-repo-root>/benchmarks when the cwd is inside a git repo,
        otherwise ./benchmarks.
    """
    d = Path.cwd()
    for p in (d, *d.parents):
        if (p / ".git").exists():
            return p / "benchmarks"
    return d / "benchmarks"


def collect(
    runs: list[dict[str, Any]],
    test_type: str,
    key: str,
    pp: int | None = None,
    batch_size: int | None = None,
) -> list[float]:
    """Pull one metric out of completed bench runs.

    Args:
        runs: Raw bench result dicts, each carrying a "results" list of
            per-test rows.
        test_type: Row type to keep ("single" or "batch").
        key: Metric field to extract from each kept row.
        pp: When given, keep only rows with this prompt length.
        batch_size: When given, keep only rows with this batch size.

    Returns:
        The extracted metric values, in run order.
    """
    return [
        r[key]
        for res in runs
        for r in res["results"]
        if r.get("test_type") == test_type
        and (pp is None or r.get("pp") == pp)
        and (batch_size is None or r.get("batch_size") == batch_size)
    ]


def fmt_stats(vals: list[float]) -> str:
    """Format a metric sample as mean ± stddev with coefficient of variation.

    Args:
        vals: The sampled metric values (at least one).

    Returns:
        "mean ± stddev (CV%)", plus a "[min–max]" range when the sample
        has more than one value.
    """
    m = statistics.mean(vals)
    s = statistics.stdev(vals) if len(vals) > 1 else 0.0
    line = f"{m:.1f} ± {s:.1f} (CV {100 * s / m:.1f}%)"
    if len(vals) > 1:
        line += f" [{min(vals):.1f}–{max(vals):.1f}]"
    return line