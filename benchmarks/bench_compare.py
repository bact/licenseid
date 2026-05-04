#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Art
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Compare two licenseid branches on recall, precision, speed, memory.

Usage:
    python bench_compare.py [--verify]
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
BENCHMARK_NAME = "perf_eval"


def run_branch(
    src_path: str, label: str, timestamp: str, verify: bool
) -> dict[str, Any]:
    print(f"\nRunning: {label} …", flush=True)
    cmd = [sys.executable, str(SCRIPT), src_path, label, BENCHMARK_NAME, timestamp]
    if verify:
        cmd.append("--verify")

    # Use Popen to stream stderr in real-time while capturing stdout for the final result
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )

    stdout_lines = []

    # We need a way to read both pipes. Stderr is for progress, Stdout is for the JSON result.
    # Since progress is more important for real-time, we'll focus on that.
    import threading

    def stream_stderr(pipe):
        for line in pipe:
            print(f"  {line.strip()}", flush=True)

    stderr_thread = threading.Thread(target=stream_stderr, args=(proc.stderr,))
    stderr_thread.start()

    # Read stdout in the main thread (it will block until the process finishes or buffers)
    for line in proc.stdout:
        stdout_lines.append(line)

    proc.wait()
    stderr_thread.join()

    if proc.returncode != 0:
        print(f"  ERROR (exit {proc.returncode}):", file=sys.stderr)
        # We don't have the full stderr captured anymore, but it was streamed to terminal.
        sys.exit(1)

    if not stdout_lines:
        print(f"  ERROR: No JSON output from {label}", file=sys.stderr)
        sys.exit(1)

    result: dict[str, Any] = json.loads(stdout_lines[-1].strip())
    return result


def generate_markdown_report(
    a: dict[str, Any], b: dict[str, Any], timestamp: str
) -> str:
    lines = []
    lines.append(f"# Benchmark Comparison: `{a['label']}` vs `{b['label']}`")
    lines.append(f"**Date:** {timestamp}")
    lines.append("")
    lines.append("## Metrics")
    lines.append("")

    for t_idx in range(1, 6):
        t_key = f"type_{t_idx}"
        lines.append(f"### Input Type {t_idx}")
        lines.append("| Category | main | license-marker | Δ |")
        lines.append("| :--- | ---: | ---: | ---: |")

        all_subcats = sorted(
            list(
                set(a["stats"].get(t_key, {}).keys())
                | set(b["stats"].get(t_key, {}).keys())
            )
        )

        for subcat in all_subcats:
            for k, col in [
                ("top1", "Recall@1"),
                ("top3", "Recall@3"),
                ("top5", "Recall@5"),
            ]:
                ta = (
                    a["stats"]
                    .get(t_key, {})
                    .get(subcat, {"total": 0, "top1": 0, "top3": 0, "top5": 0})
                )
                tb = (
                    b["stats"]
                    .get(t_key, {})
                    .get(subcat, {"total": 0, "top1": 0, "top3": 0, "top5": 0})
                )

                if ta["total"] == 0 or tb["total"] == 0:
                    continue
                va = ta[k] / ta["total"] * 100
                vb = tb[k] / tb["total"] * 100
                mark = " 🟢" if vb > va + 0.005 else (" 🔴" if vb < va - 0.005 else " ")
                lines.append(
                    f"| {subcat} {col} | {va:.2f}% | {vb:.2f}% | {vb - va:+.2f}%{mark} |"
                )
        lines.append("")

    lines.append("### Global Summary")
    lines.append("| Metric | main | license-marker | Δ |")
    lines.append("| :--- | ---: | ---: | ---: |")

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

    lines.append("")
    return "\n".join(lines)


def main() -> None:
    is_verify = "--verify" in sys.argv
    timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    with tempfile.TemporaryDirectory(prefix="licenseid-bench-") as tmpdir:
        tmp_path = Path(tmpdir)
        print(f"Creating pristine checkout of main in {tmp_path} ...", flush=True)

        subprocess.run(
            ["git", "worktree", "add", "--detach", str(tmp_path), "main"],
            cwd=CURRENT_REPO,
            check=True,
            capture_output=True,
        )

        try:
            print("Starting evaluation of branch 'main'...", flush=True)
            res_main = run_branch(
                src_path=str(tmp_path / "src"),
                label="main",
                timestamp=timestamp,
                verify=is_verify,
            )
            print("Finished evaluation of branch 'main'.", flush=True)

            print("Starting evaluation of branch 'license-marker'...", flush=True)
            res_marker = run_branch(
                src_path=str(CURRENT_REPO / "src"),
                label="license-marker",
                timestamp=timestamp,
                verify=is_verify,
            )
            print("Finished evaluation of branch 'license-marker'.", flush=True)

            print("Generating Markdown report...", flush=True)
            report = generate_markdown_report(res_main, res_marker, timestamp)
            out_file = CURRENT_REPO / "benchmarks" / "summary.md"
            with open(out_file, "w", encoding="utf-8") as f:
                f.write(report)

            print(f"\nReport written to {out_file}")

        finally:
            print(f"Cleaning up worktree {tmp_path} ...", flush=True)
            subprocess.run(
                ["git", "worktree", "remove", "--force", str(tmp_path)],
                cwd=CURRENT_REPO,
                check=False,
                capture_output=True,
            )
            print("Cleanup complete.", flush=True)


if __name__ == "__main__":
    main()
