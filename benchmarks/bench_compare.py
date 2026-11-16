#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Art
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Compare two licenseid branches on recall, precision, speed, memory.

Usage:
    python bench_compare.py [--verify] [--subset N]
"""

import datetime
import json
import subprocess
import sys
import tempfile
import threading
from pathlib import Path
from typing import Any

from bench_report import generate_markdown_report

SCRIPT = Path(__file__).parent / "bench_single.py"
CURRENT_REPO = Path(__file__).parent.parent
BENCHMARK_NAME = "perf_eval"


def _stream_stderr(pipe: Any) -> None:
    """Echo the child's progress lines as they arrive."""
    for line in pipe:
        print(f"  {line.strip()}", flush=True)


def run_branch(
    src_path: str, label: str, timestamp: str, options: list[str]
) -> dict[str, Any]:
    """Run ``bench_single.py`` on one source tree and return its JSON result."""
    print(f"\nRunning: {label} \u2026", flush=True)
    cmd = [sys.executable, str(SCRIPT), src_path, label, BENCHMARK_NAME, timestamp]
    cmd.extend(options)

    # Stream stderr in real time while capturing stdout for the final result.
    with subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    ) as proc:
        stderr_thread = threading.Thread(target=_stream_stderr, args=(proc.stderr,))
        stderr_thread.start()

        # Read stdout in the main thread
        if proc.stdout is None:
            print("  ERROR: No stdout pipe", file=sys.stderr)
            sys.exit(1)
        stdout_lines = list(proc.stdout)

        proc.wait()
        stderr_thread.join()

    if proc.returncode != 0:
        print(f"  ERROR (exit {proc.returncode}):", file=sys.stderr)
        # The full stderr is not captured; it was streamed to the terminal.
        sys.exit(1)

    if not stdout_lines:
        print(f"  ERROR: No JSON output from {label}", file=sys.stderr)
        sys.exit(1)

    result: dict[str, Any] = json.loads(stdout_lines[-1].strip())
    return result


def _current_branch() -> str:
    """Return the name of the current git branch."""
    result = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        cwd=CURRENT_REPO,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _options() -> list[str]:
    """Return the ``bench_single.py`` flags given on this command line."""
    options: list[str] = []
    if "--verify" in sys.argv:
        options.append("--verify")
    subset_idx = next((i for i, a in enumerate(sys.argv) if a == "--subset"), None)
    if subset_idx is not None:
        options.extend(["--subset", str(int(sys.argv[subset_idx + 1]))])
    if "--fast" in sys.argv:
        options.append("--fast")
    return options


def _evaluate(
    src_path: Path, label: str, timestamp: str, options: list[str]
) -> dict[str, Any]:
    """Run one branch, announcing its start and end."""
    print(f"Starting evaluation of branch '{label}'...", flush=True)
    result = run_branch(str(src_path), label, timestamp, options)
    print(f"Finished evaluation of branch '{label}'.", flush=True)
    return result


def _compare(
    tmp_path: Path, labels: tuple[str, str], timestamp: str, options: list[str]
) -> None:
    """Evaluate the baseline and the current branch, then write the report."""
    baseline_label, current_label = labels
    res_main = _evaluate(tmp_path / "src", baseline_label, timestamp, options)
    res_marker = _evaluate(CURRENT_REPO / "src", current_label, timestamp, options)

    print("Generating Markdown report...", flush=True)
    report = generate_markdown_report(res_main, res_marker, timestamp)
    out_file = CURRENT_REPO / "benchmarks" / "summary.md"
    with open(out_file, "w", encoding="utf-8") as f:
        f.write(report)

    print(f"\nReport written to {out_file}")


def main() -> None:
    """Compare the current branch with ``main`` and write ``summary.md``."""
    options = _options()
    timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    current_label = _current_branch()
    baseline_label = "main"

    with tempfile.TemporaryDirectory(prefix="licenseid-bench-") as tmpdir:
        tmp_path = Path(tmpdir)
        print(
            f"Creating pristine checkout of '{baseline_label}' in {tmp_path} ...",
            flush=True,
        )

        subprocess.run(
            ["git", "worktree", "add", "--detach", str(tmp_path), baseline_label],
            cwd=CURRENT_REPO,
            check=True,
            capture_output=True,
        )

        try:
            _compare(tmp_path, (baseline_label, current_label), timestamp, options)
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
