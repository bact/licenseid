# SPDX-FileCopyrightText: 2026 Art
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Fixture sets of ``bench_single.py``: one runner method per input type.

Import only after the source tree under test is on ``sys.path``.
"""

import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from bench_single_board import Scoreboard

T1_FIELDS: tuple[str, ...] = (
    "id_verbatim",
    "id_deprecated",
    "id_space",
    "id_casing",
    "id_punct",
    "id_distorted",
)
# "name_distored" is the key as the fixture file spells it.
T2_FIELDS: tuple[str, ...] = (
    "name_verbatim",
    "name_space",
    "name_casing",
    "name_punct",
    "name_distored",
)


@dataclass(frozen=True)
class RunOptions:
    """The flags of one run (see the usage of ``bench_single.py``)."""

    verify: bool = False
    fast: bool = False
    subset: int | None = None


def _log(message: str) -> None:
    """Write a progress line to standard error."""
    print(message, file=sys.stderr, flush=True)


def _load_json(path: Path) -> Any:
    """Read a JSON fixture."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def select_benchmark_subset(files: list[Path], n: int = 70) -> list[Path]:
    """Return a deterministic stratified subset of *n* fixture files.

    Strategy:

    1. Sort files by (family_prefix, file_size).  This groups members of
       the same licence family together and orders within each family by
       approximate text length, ensuring both dimensions are covered.
    2. Apply a systematic stride: pick every k-th file where
       ``k = len(files) // n``.  Files whose index is a multiple of *k*
       are selected; any remainder slots are filled from the start of the
       sorted list to reach exactly *n* files.
    3. If ``len(files) <= n`` return all files unchanged.

    The family prefix is the leading ASCII-letter characters of the
    filename stem (e.g. ``CC`` from ``CC-BY-4.0.json``, ``GPL`` from
    ``GPL-2.0-only.json``).  File size is used as an inexpensive proxy
    for text length (no JSON parsing needed).
    """
    if len(files) <= n:
        return list(files)

    def _sort_key(p: Path) -> tuple[str, int]:
        m = re.match(r"^([A-Za-z]+)", p.stem)
        family = m.group(1).upper() if m else ""
        return (family, p.stat().st_size)

    sorted_files = sorted(files, key=_sort_key)
    stride = len(sorted_files) // n
    return [sorted_files[i * stride] for i in range(n)]


class FixtureRunner:
    """Run the fixture sets of each input type against one scoreboard."""

    def __init__(
        self,
        board: Scoreboard,
        base_dir: Path,
        options: RunOptions,
        safe_to_canon: dict[str, str],
    ) -> None:
        self.board = board
        self.base_dir = base_dir
        self.options = options
        self.safe_to_canon = safe_to_canon

    def run_all(self) -> None:
        """Run every input type, in order."""
        self.run_fields("Type 1", "type_1", "license-id/license_ids.json", T1_FIELDS)
        self.run_fields(
            "Type 2", "type_2", "license-name/license_names.json", T2_FIELDS
        )
        self.run_type3()
        self.run_type4()
        self.run_mixed("Type 5", "type_5", "mixed-content", ordered=False)
        # Type 5.1: same logic as Type 5 but uses curated hand-crafted fixtures
        # from tests/fixtures/mixed-content-curated/ instead of generated ones.
        self.run_mixed("Type 5.1", "type_51", "mixed-content-curated", ordered=True)

    def _finish(self, label: str, category: str) -> None:
        """Log the number of queries run for *category*."""
        total = self.board.category_total(category)
        _log(f"Finished {label} ({total} queries)")

    def _fixture_files(self, directory: Path, label: str) -> list[Path]:
        """Return the JSON fixtures of *directory*, cut by --verify/--subset."""
        files = sorted(directory.glob("*.json"))
        if self.options.verify:
            return files[:2]
        if self.options.subset is not None:
            files = select_benchmark_subset(files, n=self.options.subset)
            _log(f"  [subset] {label}: {len(files)} fixtures")
        return files

    def run_fields(
        self, label: str, category: str, relpath: str, fields: tuple[str, ...]
    ) -> None:
        """Types 1 and 2: one list of items, each with a text per field."""
        _log(f"Running {label}...")
        path = self.base_dir / relpath
        if not path.exists():
            return
        data = _load_json(path)
        if self.options.verify:
            data = data[:2]
        for fld in fields:
            self.board.ensure(category, fld)
        for item in data:
            for fld in fields:
                text = item.get(fld)
                if text:
                    self.board.check(item["license_id"], text, category, fld)
        self._finish(label, category)

    def run_type3(self) -> None:
        """Type 3: head-only slices.

        Heads of 300 to 800 characters (the full head×tail matrix is not
        needed for iteration). --fast reduces to head_800 only.
        """
        _log("Running Type 3...")
        directory = self.base_dir / "license-text-short"
        if not directory.exists():
            return
        head_sizes = [800] if self.options.fast else [300, 500, 800]
        for fp in self._fixture_files(directory, "Type 3"):
            data = _load_json(fp)
            for sz in head_sizes:
                text = data.get(f"license_text_short_head_{sz}", "")
                if text:
                    self.board.ensure("type_3", f"head_{sz}")
                    self.board.check(data["license_id"], text, "type_3", f"head_{sz}")
        self._finish("Type 3", "type_3")

    def run_type4(self) -> None:
        """Type 4: the long texts, verbatim and distorted."""
        _log("Running Type 4...")
        directory = self.base_dir / "license-text-long"
        if not directory.exists():
            return
        rates = ["02"] if self.options.fast else ["01", "02", "05", "10", "20"]
        for fp in self._fixture_files(directory, "Type 4"):
            data = _load_json(fp)
            true_id = data["license_id"]
            self.board.ensure("type_4", "verbatim")
            self.board.check(true_id, data["license_text"], "type_4", "verbatim")
            for rate in rates:
                text = data.get(f"license_text_long_distorted_{rate}")
                if text:
                    self.board.ensure("type_4", rate)
                    self.board.check(true_id, text, "type_4", rate)
        self._finish("Type 4", "type_4")

    def run_mixed(
        self, label: str, category: str, dirname: str, *, ordered: bool
    ) -> None:
        """Types 5 and 5.1: one directory of files per licence."""
        _log(f"Running {label}...")
        directory = self.base_dir / dirname
        if not directory.exists():
            return
        subdirs = sorted(d for d in directory.iterdir() if d.is_dir())
        if self.options.verify:
            subdirs = subdirs[:2]
        self.board.ensure(category, "mixed")
        for d in subdirs:
            _log(f"  {label}: processing dir {d.name}")
            true_id = self.safe_to_canon.get(d.name)
            if true_id:
                self._run_dir(d, category, true_id, ordered=ordered)
        self._finish(label, category)

    def _run_dir(self, d: Path, category: str, true_id: str, *, ordered: bool) -> None:
        """Match the files of one licence directory."""
        count = 0
        for fp in sorted(d.iterdir()) if ordered else d.iterdir():
            if not fp.is_file():
                continue
            if self.options.verify and count >= 2:
                break
            with open(fp, "r", encoding="utf-8") as inner_f:
                text = inner_f.read()
            self.board.check(true_id, text, category, "mixed")
            count += 1
