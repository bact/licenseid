#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Art
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Single-branch benchmark: recall, precision, speed, memory.

Usage:
    python bench_single.py <src_path> <label> <benchmark_name> <timestamp>
        [--tarball PATH] [--verify] [--subset N] [--fast]

Outputs JSON to stdout and to benchmarks/outputs/.
Runs completely standalone — no shared state.

Flags:
    --tarball PATH  SPDX data tarball (default: newest in the licenseid cache)
    --verify        1-2 items per input type, to check the script itself
    --subset N      stratified N-fixture subset of Type 3 and Type 4
    --fast          reduced matrix: Type 3 head_800 only; Type 4 verbatim and 02
"""

import argparse
import importlib
import sys
from pathlib import Path

USAGE = (
    "Usage: python bench_single.py <src_path> <label> <benchmark_name> <timestamp>"
    " [--tarball PATH] [--verify] [--subset N] [--fast]"
)


def _parse(argv: list[str]) -> argparse.Namespace:
    """Read the command line; print the usage and exit 1 if it is short."""
    if len(argv) < 4:
        print(USAGE)
        sys.exit(1)
    parser = argparse.ArgumentParser(usage=USAGE, add_help=False)
    parser.add_argument("src_path")
    parser.add_argument("label")
    parser.add_argument("benchmark_name")
    parser.add_argument("timestamp")
    parser.add_argument("--tarball", type=Path, default=None)
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--subset", type=int, default=None)
    parser.add_argument("--fast", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    """Run one branch's benchmark; see the module docstring."""
    args = _parse(sys.argv[1:] if argv is None else argv)
    # The tree under test must come first on sys.path before licenseid is
    # imported, which the modules below do at the top.
    sys.path.insert(0, args.src_path)
    fixtures = importlib.import_module("bench_single_fixtures")
    run = importlib.import_module("bench_single_run").run
    options = fixtures.RunOptions(
        verify=args.verify, fast=args.fast, subset=args.subset
    )
    run(args.label, args.benchmark_name, args.timestamp, args.tarball, options)


if __name__ == "__main__":
    main()
