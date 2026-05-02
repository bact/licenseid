#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Art
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Compare two licenseid branches on recall, precision, speed, memory.

Orchestrates the benchmark by explicitly checking out `main` into a
temporary worktree, running `bench_single.py` across both `main` and
the current branch (`license-marker`), and producing a Markdown report.

Usage:
    python bench_compare.py
"""

import datetime
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

SCRIPT = Path(__file__).parent / "bench_single.py"
CURRENT_REPO = Path(__file__).parent.parent
RATES = ["00", "02", "05"]
BENCHMARK_NAME = "perf_eval"


def run_branch(src_path: str, label: str, timestamp: str) -> dict[str, Any]:
    print(f"\nRunning: {label} …", flush=True)
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), src_path, label, BENCHMARK_NAME, timestamp],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        print(f"  ERROR (exit {proc.returncode}):", file=sys.stderr)
        print(proc.stderr[-2000:], file=sys.stderr)
        sys.exit(1)

    # Progress lines go to stderr; JSON result is the last stdout line
    for line in proc.stderr.splitlines():
        print(f"  {line}", flush=True)
    result: dict[str, Any] = json.loads(proc.stdout.strip().splitlines()[-1])
    return result


def fmt_pct(v: float) -> str:
    return f"{v:6.2f}%"


def generate_markdown_report(
    a: dict[str, Any], b: dict[str, Any], timestamp: str
) -> str:
    lines = []
    lines.append(f"# Benchmark Comparison: `{a['label']}` vs `{b['label']}`")
    lines.append(f"**Date:** {timestamp}")
    lines.append("")
    lines.append("## Metrics")
    lines.append("")
    lines.append("| Metric | main | license-marker | Δ |")
    lines.append("| :--- | ---: | ---: | ---: |")

    for rate in RATES:
        lbl = "Verbatim" if rate == "00" else f"{rate}% noise"
        for k, col in [
            ("top1", "Recall@1"),
            ("top3", "Recall@3"),
            ("top5", "Recall@5"),
        ]:
            ta, tb = a["stats"][rate], b["stats"][rate]
            if ta["total"] == 0 or tb["total"] == 0:
                continue
            va = ta[k] / ta["total"] * 100
            vb = tb[k] / tb["total"] * 100
            mark = " 🟢" if vb > va + 0.005 else (" 🔴" if vb < va - 0.005 else " ")
            name = f"{lbl} {col}"
            lines.append(f"| {name} | {va:.2f}% | {vb:.2f}% | {vb - va:+.2f}%{mark} |")

    ap = a["correct_returned"] / a["total_returned"] * 100 if a["total_returned"] else 0
    bp = b["correct_returned"] / b["total_returned"] * 100 if b["total_returned"] else 0
    lines.append(f"| Precision | {ap:.2f}% | {bp:.2f}% | {bp - ap:+.2f}% |")

    at, bt = a["wall_time"], b["wall_time"]
    lines.append(f"| Wall time (s) | {at:.1f} | {bt:.1f} | {bt - at:+.1f}s |")

    aq = a["total_q"] / at if at > 0 else 0
    bq = b["total_q"] / bt if bt > 0 else 0
    lines.append(f"| Throughput (q/s) | {aq:.1f} | {bq:.1f} | {bq - aq:+.1f} |")

    am, bm = a["peak_mem_mb"], b["peak_mem_mb"]
    lines.append(f"| Peak memory (MB) | {am:.1f} | {bm:.1f} | {bm - am:+.1f} |")

    avg_a, avg_b = a.get("avg_mem_mb", 0), b.get("avg_mem_mb", 0)
    lines.append(
        f"| End memory (MB) | {avg_a:.1f} | {avg_b:.1f} | {avg_b - avg_a:+.1f} |"
    )

    return "\n".join(lines)


def main() -> None:
    """Main orchestration loop."""
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

    print("Orchestrating benchmark...")

    results = []

    # 1. Benchmark current branch (license-marker)
    current_src = str(CURRENT_REPO / "src" / "licenseid")
    res_marker = run_branch(current_src, "license-marker", timestamp)

    # 2. Benchmark main branch via temporary clone
    print("\nCreating temporary clone for `main` branch...", flush=True)
    with tempfile.TemporaryDirectory() as tmpdir:
        # Clone using current repo as reference to speed it up
        subprocess.run(
            [
                "git",
                "clone",
                "--shared",
                "--branch",
                "main",
                "file://" + str(CURRENT_REPO),
                tmpdir,
            ],
            check=True,
            capture_output=True,
        )
        main_src = str(Path(tmpdir) / "src" / "licenseid")
        res_main = run_branch(main_src, "main", timestamp)

    # Ensure 'main' is results[0] and 'license-marker' is results[1] for consistent diffing
    results = [res_main, res_marker]

    # Generate and print the markdown report
    md_report = generate_markdown_report(results[0], results[1], timestamp)
    print("\n" + md_report)

    # Save the markdown report
    report_file = Path(__file__).parent / f"{BENCHMARK_NAME}_report_{timestamp}.md"
    with open(report_file, "w", encoding="utf-8") as f:
        f.write(md_report)

    print(f"\nMarkdown report saved to: {report_file}")


if __name__ == "__main__":
    main()
