#!/usr/bin/env python3
"""Unit tests for scripts/generate_chart.py (parser, median, renderer)."""

from __future__ import annotations

import contextlib
import importlib.util
import io
import tempfile
import unittest
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "generate_chart", Path(__file__).resolve().parent / "generate_chart.py"
)
gc = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(gc)  # type: ignore[union-attr]

FIXTURE_MD = """# Fixture model — oMLX throughput benchmark

## Single request — mean ± stddev (CV%) [min–max], n=3

| pp | tg | Prefill tok/s | Decode tok/s | TTFT ms |
|---|---|---|---|---|
| 1024 | 256 | 486.0 ± 1.9 (CV 0.4%) [483.8–487.2] | 41.4 ± 1.9 (CV 4.6%) [40.1–43.6] | 2106.9 ± 8.4 (CV 0.4%) [2101.7–2116.6] |
| 4096 | 256 | 560.1 ± 2.4 (CV 0.4%) [557.4–562.1] | 43.2 ± 1.9 (CV 4.3%) [41.0–44.3] | 7312.6 ± 32.3 (CV 0.4%) [7286.4–7348.6] |
| 32768 | 256 | 540.0 ± 1.0 (CV 0.2%) [539.0–541.0] | 60.0 ± 1.0 (CV 1.7%) [59.0–61.0] | 60000.0 ± 100.0 (CV 0.2%) [59900.0–60100.0] |
| 131072 | 256 | 500.0 ± 1.0 (CV 0.2%) [499.0–501.0] | 70.0 ± 1.0 (CV 1.4%) [69.0–71.0] | 200000.0 ± 100.0 (CV 0.1%) [199900.0–200100.0] |

## Batching (pp1024) — mean ± stddev, n=3

| Batch | pp | Aggregate decode tok/s | vs 1x |
|---|---|---|---|
| 1x (single) | 1024 | 41.4 ± 0.0 (CV 0.0%) | 1.00 |
| 2x | 1024 | 42.4 ± 1.5 (CV 3.6%) [40.7–43.7] | 1.02 |
| 4x | 1024 | 80.0 ± 2.0 (CV 2.5%) [78.0–82.0] | 1.93 |
| 8x | 1024 | 150.0 ± 3.0 (CV 2.0%) [147.0–153.0] | 3.62 |

## Per-run tables (n=3)

### fixture-run1.json (`bench-1`)

| pp | tg | Prefill tok/s | Decode tok/s | TTFT ms |
|---|---|---|---|---|
| 1024 | 256 | 487.2 | 43.6 | 2101.7 |
| 4096 | 256 | 562.1 | 44.3 | 7286.4 |
| 32768 | 256 | 541.0 | 61.0 | 59900.0 |
| 131072 | 256 | 501.0 | 71.0 | 199900.0 |

### fixture-run2.json (`bench-2`)

| pp | tg | Prefill tok/s | Decode tok/s | TTFT ms |
|---|---|---|---|---|
| 1024 | 256 | 483.8 | 40.1 | 2116.6 |
| 4096 | 256 | 557.4 | 41.0 | 7348.6 |
| 32768 | 256 | 539.0 | 59.0 | 60100.0 |
| 131072 | 256 | 499.0 | 69.0 | 200100.0 |

### fixture-run3.json (`bench-3`)

| pp | tg | Prefill tok/s | Decode tok/s | TTFT ms |
|---|---|---|---|---|
| 1024 | 256 | 487.0 | 40.5 | 2102.5 |
| 4096 | 256 | 561.0 | 42.0 | 7300.0 |
| 32768 | 256 | 540.0 | 60.0 | 60000.0 |
| 131072 | 256 | 500.0 | 70.0 | 200000.0 |
"""


class ParseReportTests(unittest.TestCase):
    """Tests for parse_report and parse_median against a fixture report."""

    def setUp(self) -> None:
        """Write the fixture report into a temporary directory."""
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "fixture.md"
        self.path.write_text(FIXTURE_MD, encoding="utf-8")

    def test_missing_report_raises(self) -> None:
        """A nonexistent report path raises FileNotFoundError."""
        with self.assertRaises(FileNotFoundError):
            gc.parse_report(Path(self.tmp.name) / "nope.md")

    def test_aggregated_mean_is_parsed(self) -> None:
        """The mean is the first number before the ± sign."""
        data = gc.parse_report(self.path)
        self.assertEqual(data["1024:prefill"], 486.0)
        self.assertEqual(data["1024:decode"], 41.4)

    def test_min_max_are_parsed(self) -> None:
        """Min and max come from the bracketed range."""
        data = gc.parse_report(self.path)
        self.assertEqual(data["1024:prefill:min"], 483.8)
        self.assertEqual(data["1024:prefill:max"], 487.2)

    def test_batch_row_is_parsed(self) -> None:
        """A 2x batching row lands under the batch2 key."""
        data = gc.parse_report(self.path)
        self.assertEqual(data["batch2"], 42.4)
        self.assertEqual(data["batch2:sd"], 1.5)

    def test_batch_1x_defaults_min_max_to_mean(self) -> None:
        """The 1x row has no range; min/max fall back to the mean."""
        data = gc.parse_report(self.path)
        self.assertEqual(data["batch1"], 41.4)

    def test_median_is_middle_of_three_runs(self) -> None:
        """Median of 40.1, 43.6, 40.5 is 40.5."""
        self.assertEqual(gc.parse_median(self.path, "1024", "decode"), 40.5)

    def test_median_prefill(self) -> None:
        """Median prefill of 487.2, 483.8, 487.0 is 487.0."""
        self.assertEqual(gc.parse_median(self.path, "1024", "prefill"), 487.0)

    def test_unparsable_report_raises(self) -> None:
        """A file without the expected tables raises ValueError."""
        bad = Path(self.tmp.name) / "bad.md"
        bad.write_text("# nothing useful\n", encoding="utf-8")
        with self.assertRaises(ValueError):
            gc.parse_report(bad)


class PrintTableTests(unittest.TestCase):
    """Tests for the --table output (print_table) against the fixture."""

    def setUp(self) -> None:
        """Point BENCH_DIR at a temp dir holding one fixture report."""
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.bench_dir = Path(self.tmp.name)
        label = next(iter(gc.DATE_DIRS))
        name = f"GLM-5.3-Flash-x{gc.DATE_DIRS[label]}.md"
        (self.bench_dir / name).write_text(FIXTURE_MD, encoding="utf-8")
        self.parsed = gc.parse_report(self.bench_dir / name)
        self.data = {(label, "GLM-5.3-Flash"): self.parsed}
        self._orig_bench_dir = gc.BENCH_DIR
        gc.BENCH_DIR = self.bench_dir
        self.addCleanup(setattr, gc, "BENCH_DIR", self._orig_bench_dir)

    def test_table_prints_median_and_cell_format(self) -> None:
        """Cells use 'mean ± sd / median / min–max' and the median appears."""
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            gc.print_table(self.data)
        output = buffer.getvalue()
        self.assertIn("487.0", output)  # median prefill at pp1024
        self.assertIn("486.0 ± 1.9 / 487.0 / 483.8–487.2", output)
        self.assertIn("## GLM-5.3-Flash —", output)

    def test_table_prints_batch_rows(self) -> None:
        """Batching rows appear with the same slash-separated format."""
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            gc.print_table(self.data)
        self.assertIn("batch8x: 150.0 ± 3.0 / 147.0–153.0", buffer.getvalue())


class RenderTests(unittest.TestCase):
    """Tests for the SVG renderer's structure and self-containment."""

    def setUp(self) -> None:
        """Build parsed data from the fixture for rendering."""
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        path = Path(self.tmp.name) / "fixture.md"
        path.write_text(FIXTURE_MD, encoding="utf-8")
        parsed = gc.parse_report(path)
        self.data = {
            (label, prefix): dict(parsed)
            for label in gc.DATE_DIRS
            for _, prefix in gc.MODELS
        }

    def test_output_starts_with_svg(self) -> None:
        """The document starts with an <svg element."""
        self.assertTrue(gc.render_svg(self.data).startswith("<svg"))

    def test_no_external_references(self) -> None:
        """No http/https references appear in the SVG."""
        svg = gc.render_svg(self.data)
        self.assertNotIn("http", svg.replace('xmlns="http://www.w3.org/2000/svg"', ""))

    def test_legend_labels_present(self) -> None:
        """Both legend labels appear in the output."""
        svg = gc.render_svg(self.data)
        self.assertIn("Decode tok/s at pp1024", svg)
        self.assertIn("Prefill tok/s at pp1024", svg)

    def test_bar_widths_scale_with_value(self) -> None:
        """A larger value produces a wider bar."""
        second = list(gc.DATE_DIRS)[1]
        self.data[(second, "GLM-5.3-Flash")]["1024:decode"] = 200.0
        self.data[(second, "Ornith-1.5-35B-A3B")]["1024:decode"] = 200.0
        self.data[(second, "Qwen3.8-27B")]["1024:decode"] = 200.0
        self.data[(second, "Qwen3.8-Flash-Next")]["1024:decode"] = 200.0
        svg = gc.render_svg(self.data)
        widths = [
            float(line.split('width="')[1].split('"')[0])
            for line in svg.splitlines()
            if "<rect" in line and 'fill="#' in line and 'width="880"' not in line
            and 'width="14"' not in line
        ]
        self.assertGreater(max(widths), min(widths))


if __name__ == "__main__":
    unittest.main()
