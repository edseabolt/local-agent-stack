#!/usr/bin/env python3
"""Generate benchmarks/benchmarks.svg comparing the 2026-10-21/22 (oMLX
v0.7.2) and 2026-11-15 (oMLX v0.7.3) benchmark reports. Stdlib only.

The script reads the aggregated .md reports in benchmarks/ (one per model
per run date), renders a self-contained SVG with decode and prefill panels
at pp1024, and can print table cells (mean ± sd / median / min–max) with
--table for use in the benchmark documentation.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from statistics import median

REPO_ROOT = Path(__file__).resolve().parent.parent
BENCH_DIR = REPO_ROOT / "benchmarks"

# Display name -> filename prefix of the report .md files.
MODELS: list[tuple[str, str]] = [
    ("GLM-5.3-Flash", "GLM-5.3-Flash"),
    ("Ornith-1.5-35B-A3B", "Ornith-1.5-35B-A3B"),
    ("Qwen3.8-27B", "Qwen3.8-27B"),
    ("Qwen3.8-Flash-Next", "Qwen3.8-Flash-Next"),
]

# Legend label -> substring that picks the report files for that run date.
DATE_DIRS: dict[str, str] = {
    "oMLX v0.7.2 (2026-10-21/22)": "-2026102",
    "oMLX v0.7.3 (2026-11-15)": "-20261115",
}

PP_LEVELS: list[str] = ["1024", "4096", "32768", "131072"]
METRICS: list[str] = ["prefill", "decode", "ttft"]

# One cell of the aggregated table: "486.0 ± 1.9 (CV 0.4%) [483.8–487.2]".
CELL_RE = re.compile(r"([\d.]+) ± ([\d.]+)(?:.*?\[([\d.]+)–([\d.]+)\])?")
ROW_RE = re.compile(r"^\|\s*(\d+)\s*\|")
BATCH_ROW_RE = re.compile(r"^\|\s*(\d+)x\b")
RUN_HEADER_RE = re.compile(r"^### .+-run\d+\.json")


def _cell(row: str, index: int) -> tuple[float, float, float, float] | None:
    """Parse one table cell into (mean, sd, min, max); min/max default to mean.

    Args:
        row: Pipe-delimited markdown table row.
        index: Zero-based cell index after the leading pipe.

    Returns:
        The parsed numbers, or None when the cell is missing or unparsable.
    """
    cells = [c.strip() for c in row.split("|")]
    if index + 1 >= len(cells):
        return None
    text = cells[index + 1]
    match = CELL_RE.match(text)
    if match:
        mean, sd = float(match.group(1)), float(match.group(2))
        lo = float(match.group(3)) if match.group(3) else mean
        hi = float(match.group(4)) if match.group(4) else mean
        return mean, sd, lo, hi
    try:
        value = float(text)
    except ValueError:
        return None
    return value, 0.0, value, value


def parse_report(path: Path) -> dict[str, float]:
    """Parse one aggregated benchmark report.

    Args:
        path: Path to a report .md produced by the benchmark skill.

    Returns:
        Keys "pp:metric" (mean), "pp:metric:sd", "pp:metric:min",
        "pp:metric:max" for prefill/decode/ttft, and "batchN" plus
        "batchN:sd" for the batching table.

    Raises:
        FileNotFoundError: If the report file does not exist.
        ValueError: If the single-request or batching table is missing.
    """
    if not path.exists():
        raise FileNotFoundError(f"report not found: {path}")
    data: dict[str, float] = {}
    in_per_run = False
    for row in path.read_text(encoding="utf-8").splitlines():
        if row.startswith("## Per-run"):
            in_per_run = True
        if in_per_run:
            continue
        if ROW_RE.match(row) and not BATCH_ROW_RE.match(row):
            for offset, metric in enumerate(METRICS):
                cell = _cell(row, offset + 2)
                if cell:
                    _store(data, row.split("|")[1].strip(), metric, cell)
        elif BATCH_ROW_RE.match(row):
            width = BATCH_ROW_RE.match(row).group(1)  # type: ignore[union-attr]
            cell = _cell(row, 2)
            if cell:
                data[f"batch{width}"] = cell[0]
                data[f"batch{width}:sd"] = cell[1]
                data[f"batch{width}:min"] = cell[2]
                data[f"batch{width}:max"] = cell[3]
    if "1024:prefill" not in data or "batch1" not in data:
        raise ValueError(f"unparsable report: {path}")
    return data


def _store(data: dict[str, float], pp: str, metric: str,
           cell: tuple[float, float, float, float]) -> None:
    """Store one parsed cell under its pp:metric keys.

    Args:
        data: Accumulating parse results.
        pp: Prompt-length row label.
        metric: One of prefill/decode/ttft.
        cell: (mean, sd, min, max) tuple.
    """
    data[f"{pp}:{metric}"] = cell[0]
    data[f"{pp}:{metric}:sd"] = cell[1]
    data[f"{pp}:{metric}:min"] = cell[2]
    data[f"{pp}:{metric}:max"] = cell[3]


def parse_median(path: Path, pp: str, metric: str) -> float:
    """Middle of the three per-run values for one pp/metric cell.

    Args:
        path: Report .md containing "## Per-run tables (n=3)".
        pp: Prompt-length row label, e.g. "1024".
        metric: Column name: prefill, decode, or ttft.

    Returns:
        The median (middle of 3) per-run value.

    Raises:
        ValueError: If fewer than three per-run values are found.
    """
    column = METRICS.index(metric) + 2
    per_pp = _per_pp_values(path, pp, column)
    if len(per_pp) < 3:
        raise ValueError(f"fewer than 3 per-run values in {path}")
    return float(median(per_pp))


def _per_pp_values(path: Path, pp: str, column: int) -> list[float]:
    """Collect one column's values at one pp across all per-run tables.

    Args:
        path: Report .md with per-run tables.
        pp: Prompt-length row label.
        column: Zero-based cell index of the metric column.

    Returns:
        Up to three values, one per run.
    """
    values: list[float] = []
    in_run = False
    for row in path.read_text(encoding="utf-8").splitlines():
        if RUN_HEADER_RE.match(row):
            in_run = True
        elif row.startswith("## "):
            in_run = False
        elif in_run and row.startswith(f"| {pp} "):
            cell = _cell(row, column)
            if cell:
                values.append(cell[0])
    return values


def find_report(label: str, prefix: str) -> Path:
    """Locate the report .md for one model on one run date.

    Args:
        label: Legend label key into DATE_DIRS.
        prefix: Model filename prefix.

    Returns:
        Path to the matching report.

    Raises:
        FileNotFoundError: If no report matches the date substring.
    """
    substring = DATE_DIRS[label]
    matches = sorted(BENCH_DIR.glob(f"{prefix}*{substring}*.md"))
    if not matches:
        raise FileNotFoundError(f"no report for {prefix} on {label} in {BENCH_DIR}")
    return matches[0]


def collect() -> dict[tuple[str, str], dict[str, float]]:
    """Parse every report for every model and run date.

    Returns:
        Mapping of (legend label, model display name) to parsed data.
    """
    parsed: dict[tuple[str, str], dict[str, float]] = {}
    for label in DATE_DIRS:
        for _, prefix in MODELS:
            parsed[(label, prefix)] = parse_report(find_report(label, prefix))
    return parsed


def _bar(svg: list[str], y: float, value: float, max_value: float,
         color: str, x_label: int) -> None:
    """Append one bar and its value label to the SVG fragment list.

    Args:
        svg: Accumulating SVG lines.
        y: Top of the bar.
        value: Data value; bar width scales against max_value.
        max_value: Panel maximum used for scaling.
        color: Bar fill color.
        x_label: X position where the model label starts.
    """
    width = value / (max_value * 1.15) * 560
    svg.append(
        f'  <rect x="{x_label}" y="{y:.1f}" width="{width:.1f}" '
        f'height="18" fill="{color}"/>'
    )
    svg.append(
        f'  <text x="{x_label + width + 6:.1f}" y="{y + 13:.1f}" '
        f'font-size="11" fill="#1f2328">{value:.1f}</text>'
    )


def _panel(svg: list[str], title: str, metric: str,
           data: dict[tuple[str, str], dict[str, float]], y0: float) -> float:
    """Render one panel of grouped bars and return its bottom y.

    Args:
        svg: Accumulating SVG lines.
        title: Panel heading.
        metric: Metric key to chart ("decode" or "prefill").
        data: Parsed reports keyed by (label, model prefix).
        y0: Top y of the panel.

    Returns:
        The y coordinate just below the panel.
    """
    max_value = max(d[f"1024:{metric}"] for d in data.values())
    svg.append(
        f'  <text x="20" y="{y0 + 14}" font-size="13" font-weight="bold" '
        f'fill="#1f2328">{title}</text>'
    )
    y = y0 + 26
    for name, prefix in MODELS:
        svg.append(
            f'  <text x="150" y="{y + 13:.1f}" font-size="11" '
            f'fill="#1f2328" text-anchor="end">{name}</text>'
        )
        for row, (label, color) in enumerate(
            [(lab, "#8a8f98" if i == 0 else "#2563eb")
             for i, lab in enumerate(DATE_DIRS)]
        ):
            _bar(svg, y + row * 20, data[(label, prefix)][f"1024:{metric}"],
                 max_value, color, 156)
        y += 44
    return y + 8


def render_svg(data: dict[tuple[str, str], dict[str, float]]) -> str:
    """Build the complete self-contained SVG document.

    Args:
        data: Parsed reports keyed by (legend label, model prefix).

    Returns:
        The SVG markup as a string.
    """
    svg: list[str] = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="880" height="560" '
        'viewBox="0 0 880 560" role="img" font-family="sans-serif">',
        '  <title>Benchmark comparison: decode and prefill per model, '
        'oMLX v0.7.2 vs v0.7.3</title>',
        '  <rect width="880" height="560" fill="#ffffff"/>',
    ]
    for i, label in enumerate(DATE_DIRS):
        color = "#8a8f98" if i == 0 else "#2563eb"
        svg.append(
            f'  <rect x="{420 + i * 190}" y="14" width="14" height="14" '
            f'fill="{color}"/>'
        )
        svg.append(
            f'  <text x="{438 + i * 190}" y="25" font-size="11" '
            f'fill="#1f2328">{label}</text>'
        )
    y = _panel(svg, "Decode tok/s at pp1024", "decode", data, 50)
    y = _panel(svg, "Prefill tok/s at pp1024", "prefill", data, y + 10)
    svg.append(
        f'  <text x="20" y="{min(y + 14, 552)}" font-size="10" '
        'fill="#1f2328">Generated by scripts/generate_chart.py from the '
        '.md reports in benchmarks/.</text>'
    )
    svg.append("</svg>")
    return "\n".join(svg) + "\n"


def print_table(data: dict[tuple[str, str], dict[str, float]]) -> None:
    """Print mean ± sd / median / min–max cells for every report.

    Args:
        data: Parsed reports keyed by (legend label, model prefix).
    """
    for (label, prefix), d in sorted(data.items()):
        path = find_report(label, prefix)
        print(f"## {prefix} — {label}")
        for pp in PP_LEVELS:
            cells = []
            for metric in METRICS:
                med = parse_median(path, pp, metric)
                cells.append(
                    f"{d[f'{pp}:{metric}']} ± {d[f'{pp}:{metric}:sd']} / "
                    f"{med} / {d[f'{pp}:{metric}:min']}–{d[f'{pp}:{metric}:max']}"
                )
            print(f"pp{pp}: prefill {cells[0]} | decode {cells[1]} | ttft {cells[2]}")
        for b in (1, 2, 4, 8):
            key = f"batch{b}"
            print(
                f"batch{b}x: {d[key]} ± {d[f'{key}:sd']} / "
                f"{d[f'{key}:min']}–{d[f'{key}:max']}"
            )
        print()


def main() -> None:
    """Parse args, parse reports, and either print tables or write the SVG."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--table", action="store_true",
        help="print mean ± sd / median / min–max cells instead of writing the SVG",
    )
    args = parser.parse_args()
    data = collect()
    if args.table:
        print_table(data)
        return
    out = BENCH_DIR / "benchmarks.svg"
    out.write_text(render_svg(data), encoding="utf-8")
    print(f"wrote {out}")


if __name__ == "__main__":
    try:
        main()
    except (FileNotFoundError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(1)
