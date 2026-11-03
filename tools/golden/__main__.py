# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Show or regenerate the golden snapshots (``tests/fixtures/golden/``)."""

import argparse
import hashlib
import sys
import tempfile
from pathlib import Path

# isort: off
# pylint: disable=wrong-import-order
from tools.golden import paths  # first: it puts tests/ on sys.path

import harness_changes
import harness_cli
import harness_golden as hg
from harness_db import harness_detector

# isort: on

TESTS = paths.TESTS

CLI_FILE = hg.GOLDEN / "cli.jsonl"
COMMENT = (
    "Golden snapshot of detect(): the top result of each case, on the database",
    "of the long-text fixtures (tests/harness_db.py). Regenerate with",
    "python -m tools.golden --write {kind}; never edit by hand.",
)


def identity(line: str) -> str:
    """A value as it is."""
    return line


def digest(line: str) -> str:
    """The twelve-character digest a CLI golden record is listed by."""
    return hashlib.sha256(line.encode("utf-8")).hexdigest()[:12]


def cli_snapshot() -> dict[str, str]:
    """``{case#mode: line}`` of every CLI case, now."""
    current = {}
    with tempfile.TemporaryDirectory() as base, harness_cli.cli_env(Path(base)) as env:
        for case in harness_cli.CASES:
            for record in env.run(case):
                current[f"{record.case}#{record.mode}"] = harness_cli.record_line(
                    record
                )
    return current


def read_cli_golden() -> dict[str, str]:
    """``{case#mode: line}`` of ``cli.jsonl``."""
    lines = CLI_FILE.read_text(encoding="utf-8").splitlines()
    return {
        f"{r.case}#{r.mode}": line
        for line in lines
        for r in [harness_cli.read_record(line)]
    }


def main(argv: list[str] | None = None) -> int:
    """Print the differences, or with ``--write`` rewrite the files."""
    parser = argparse.ArgumentParser(prog="python -m tools.golden", description=__doc__)
    parser.add_argument("--write", action="store_true", help="rewrite the files")
    parser.add_argument(
        "what",
        nargs="*",
        choices=[*hg.KINDS, "cli"],
        help="a detect kind or cli (default: all)",
    )
    args = parser.parse_args(argv)
    what = args.what or [*hg.KINDS, "cli"]
    status = 0
    for name in what:
        if name == "cli":
            current, path = cli_snapshot(), CLI_FILE
            if args.write:
                lines = [current[key] for key in sorted(current)]
                path.write_text("\n".join(lines) + "\n", encoding="utf-8")
                print(f"{path.name}: {len(lines)} records")
                continue
            old = read_cli_golden()
            view = digest
        else:
            current = hg.snapshot(harness_detector(), name)
            path = hg.GOLDEN / hg.FILES[name]
            if args.write:
                comment = [line.format(kind=name) for line in COMMENT]
                hg.write_golden(path, hg.DETECT_HEADER, comment, current)
                print(f"{path.name}: {len(current)} rows")
                continue
            old, view = hg.read_golden(path), identity
        expected = (
            harness_changes.CLI_CHANGES
            if name == "cli"
            else {
                case: entry
                for case, entry in harness_changes.DETECT_CHANGES.items()
                if case.startswith(f"{name}/")
            }
        )
        report = hg.diff_report(old, current, expected, view=view, complete=True)
        print(report or f"{name}: as the golden")
        status = status or (1 if report else 0)
    return status


if __name__ == "__main__":
    sys.exit(main())
