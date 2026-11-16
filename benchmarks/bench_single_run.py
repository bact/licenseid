# SPDX-FileCopyrightText: 2026 Art
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The run of ``bench_single.py``: build the database, query, write results.

Import only after the source tree under test is on ``sys.path``.
"""

import json
import sys
import time
import tracemalloc
from pathlib import Path
from typing import Any

from bench_single_board import Scoreboard
from bench_single_db import build_rows, find_tarball, load_db, new_db_path
from bench_single_fixtures import FixtureRunner, RunOptions
from bench_single_matcher import InstrumentedMatcher

BENCH_DIR = Path(__file__).parent


def _log(message: str) -> None:
    """Write a progress line to standard error."""
    print(message, file=sys.stderr, flush=True)


def run(
    label: str,
    benchmark_name: str,
    timestamp: str,
    tarball: Path | None,
    options: RunOptions,
) -> None:
    """Run the benchmark, write the JSON result file and print it."""
    tar_path = tarball if tarball is not None else find_tarball()
    _log(f"[{label}] Building DB from {tar_path.name} …")
    licenses, index, safe_to_canon = build_rows(tar_path)
    db_path = new_db_path(label)
    keepalive = load_db(db_path, licenses, index)
    _log(f"[{label}] DB ready ({len(licenses)} licences). Running queries …")

    matcher = InstrumentedMatcher(db_path)
    matcher.detect("MIT License")  # warm up

    tracemalloc.start()
    tracemalloc.clear_traces()
    t_start: float = time.perf_counter()

    board = Scoreboard(matcher)
    base_dir = BENCH_DIR.parent / "tests" / "fixtures"
    FixtureRunner(board, base_dir, options, safe_to_canon).run_all()

    wall_time: float = time.perf_counter() - t_start
    current_mem, peak_mem = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    _log(f"[{label}] Done in {wall_time:.1f}s")

    result: dict[str, Any] = {
        "label": label,
        "stats": board.stats,
        "tier_stats": board.tier_stats,
        "total_q": board.total_queries(),
        "total_returned": board.global_counts["total_returned"],
        "correct_returned": board.global_counts["correct_returned"],
        "wall_time": wall_time,
        "peak_mem_mb": peak_mem / 1024 / 1024,
        "avg_mem_mb": current_mem / 1024 / 1024,
        "failures_sample": board.failures[:10],
    }
    _write_result(result, benchmark_name, label, timestamp)
    keepalive.close()


def _write_result(
    result: dict[str, Any], benchmark_name: str, label: str, timestamp: str
) -> None:
    """Write *result* to benchmarks/outputs/ and print it to standard output."""
    output_dir = BENCH_DIR / "outputs"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / f"{benchmark_name}_{label}_{timestamp}.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    print(json.dumps(result))
