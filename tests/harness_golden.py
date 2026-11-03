# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The golden snapshots: their cases, their files and the diff that accepts
only listed changes (the pattern of ``resolver_corpus.EXPECTED_CHANGES``).

A golden file is a TSV (``tests/fixtures/golden/``): ``#`` comment lines,
a header row, one row per case, the case first. A case is ``kind/...``; its
value is the rest of the row, joined by tabs. Regenerate with
``python -m tools.golden --write`` (see ``tools/golden/README.md``)."""

import json
import warnings
from collections.abc import Callable, Iterable
from pathlib import Path

from licenseid.detector import LicenseDetector
from tools.pypi_licence_sample.answer import escape_field, unescape_field

FIXTURES = Path(__file__).parent / "fixtures"
GOLDEN = FIXTURES / "golden"
DETECT_HEADER = ("case", "expression", "method", "exact", "score")
NONE = "-"
#: Every n-th long text and the variant of each short text, see :func:`detect_cases`.
LONG_STRIDE = 3
#: The every-commit slice of each kind: every n-th case of its golden file.
SLICE_STRIDE = {"long": 90, "short": 80, "mixed": 8, "id": 2, "name": 2}
KINDS = tuple(SLICE_STRIDE)
FILES = {
    "long": "detect_long.tsv",
    "short": "detect_short.tsv",
    "mixed": "detect_mixed.tsv",
    "id": "detect_id.tsv",
    "name": "detect_name.tsv",
}


def _json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def detect_cases(kind: str) -> list[tuple[str, str]]:
    """``(case, text)`` of *kind*, in case order. ``long``: the verbatim text
    of every third licence; ``short``: one slice of each text, head or tail
    of 300 to 2,000 characters, by the licence's place in the list; ``mixed``:
    every file of ``mixed-content`` and ``mixed-content-curated``; ``id`` and
    ``name``: every spelling of the ID and name fixtures."""
    if kind in ("long", "short"):
        return _text_cases(kind)
    if kind == "mixed":
        return _mixed_cases()
    prefix = "id_" if kind == "id" else "name_"
    entries = _json(FIXTURES / f"license-{kind}" / f"license_{kind}s.json")
    assert isinstance(entries, list)
    return [
        (f"{kind}/{entry['license_id']}/{key}", value)
        for entry in entries
        for key, value in entry.items()
        if key.startswith(prefix)
    ]


def _text_cases(kind: str) -> list[tuple[str, str]]:
    cases = []
    folder = FIXTURES / f"license-text-{kind}"
    # By name: sorting Paths compares case-insensitively on Windows.
    files = sorted(folder.glob("*.json"), key=lambda path: path.name)
    for place, path in enumerate(files):
        data = _json(path)
        assert isinstance(data, dict)
        if kind == "long":
            if place % LONG_STRIDE == 0:
                cases.append((f"long/{path.stem}", data["license_text"]))
            continue
        keys = [key for key in data if key.startswith("license_text_short_")]
        key = keys[place % len(keys)]
        cases.append(
            (f"short/{path.stem}/{key[len('license_text_short_') :]}", data[key])
        )
    return cases


def _mixed_cases() -> list[tuple[str, str]]:
    cases = []
    for folder in ("mixed-content", "mixed-content-curated"):
        root = FIXTURES / folder
        relatives = sorted(
            p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()
        )
        for relative in relatives:
            path = root / relative
            text = path.read_text(encoding="utf-8", errors="replace")
            cases.append((f"mixed/{folder}/{relative}", text))
    return cases


def detect_row(detector: LicenseDetector, text: str) -> str:
    """The top result of ``detect(text)``, as a row value: expression,
    method, exact, score to four places; ``-`` for each when nothing is
    found."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        found = detector.detect(text)
    if not found:
        return "\t".join([NONE] * 4)
    top = found[0]
    return "\t".join(
        [
            escape_field(top["expression"]),
            top["method"],
            "yes" if top["exact"] else "no",
            f"{top['score']:.4f}",
        ]
    )


def take_slice(kind: str, cases: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """The every-commit slice of *cases*."""
    return cases[:: SLICE_STRIDE[kind]]


def snapshot(
    detector: LicenseDetector, kind: str, *, short: bool = False
) -> dict[str, str]:
    """``{case: value}`` of *kind* (its slice when *short*)."""
    cases = detect_cases(kind)
    if short:
        cases = take_slice(kind, cases)
    return {case: detect_row(detector, text) for case, text in cases}


def read_golden(path: Path) -> dict[str, str]:
    """``{case: value}`` of a golden TSV, comments and header dropped."""
    lines = [line for line in path.read_text(encoding="utf-8").split("\n") if line]
    rows = [line for line in lines if not line.startswith("#")][1:]
    result = {}
    for row in rows:
        case, _, value = row.partition("\t")
        result[unescape_field(case)] = value
    return result


def write_golden(
    path: Path, header: Iterable[str], comments: Iterable[str], rows: dict[str, str]
) -> None:
    """Write *rows* as a golden TSV: *comments*, *header*, one line a case."""
    out = [f"# {line}" for line in comments]
    out.append("\t".join(header))
    out += [f"{escape_field(case)}\t{value}" for case, value in sorted(rows.items())]
    path.write_text("\n".join(out) + "\n", encoding="utf-8")


def diff_report(
    golden: dict[str, str],
    current: dict[str, str],
    expected: dict[str, tuple[str, str]],
    *,
    view: Callable[[str], str] = str,
    complete: bool = False,
) -> str:
    """Why *current* is not the golden plus *expected*, one case a line; empty
    when every case of *current* that differs from *golden* is in *expected*
    with the value it now has, and every case of *expected* that *current*
    holds did change. *expected* is ``{case: (view of the new value,
    reason)}``; *view* shortens a value for the report and the listing (the
    CLI golden lists a digest). A case in *current* only is new, a change.
    With *complete* (*current* is the whole run, not a slice) a case of
    *golden* or *expected* that *current* lacks is reported too."""
    lines = []
    for case, value in current.items():
        old = golden.get(case)
        if case in expected:
            if view(value) != expected[case][0]:
                lines.append(
                    f"{case}: listed as {expected[case][0]!r}, got {view(value)!r}"
                )
            elif value == old:
                lines.append(f"{case}: listed ({expected[case][1]}), unchanged")
        elif value != old:
            was = None if old is None else view(old)
            lines.append(f"{case}: {was!r} -> {view(value)!r}, not in EXPECTED_CHANGES")
    if complete:
        lines += [
            f"{case}: in the golden, not run"
            for case in golden
            if case not in current and case not in expected
        ]
        lines += [
            f"{case}: listed, not run" for case in expected if case not in current
        ]
    return "\n".join(lines)


def select(
    table: dict[str, tuple[str, str]], keep: Callable[[str], bool]
) -> dict[str, tuple[str, str]]:
    """The entries of *table* whose case satisfies *keep*."""
    return {case: entry for case, entry in table.items() if keep(case)}
