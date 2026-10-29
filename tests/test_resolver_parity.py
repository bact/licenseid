# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The parity corpus pins what ``resolve()`` 0.6.0 answers (the 0.7.0 plan,
finding F9, task T0): ``tests/fixtures/resolver_parity.tsv`` holds real and
synthetic declared values with their 0.6.0 answers, the answer of Pitloom
0.21.1 and the answer the plan expects of 0.7.0.

A later rule pull request changes an answer on purpose: it lists the value in
``resolver_corpus.EXPECTED_CHANGES``, and this file skips that row. A
``# BUG:`` pin asserts an answer that is wrong today; the pull request that
fixes it flips it.
"""

import hashlib
import re

import pytest
from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import
from resolver_corpus import (
    EXPECTED_CHANGES,
    PARITY_FILE,
    UNRESOLVED,
    parity_rows,
    pinned,
    read_comments,
    read_rows,
)

from licenseid import LicenseDatabase, resolve
from tools.pypi_licence_sample.answer import (
    answer_of,
    escape_field,
    unescape_field,
)

ROWS = parity_rows()


def _id(index: int, row: dict[str, str]) -> str:
    """A short, ASCII test id: the row number and the start of the value."""
    return f"{index:03}-" + re.sub(r"[^A-Za-z0-9.+-]+", "_", row["value"])[:28]


@pytest.mark.parametrize(
    "row", ROWS, ids=[_id(index, row) for index, row in enumerate(ROWS)]
)
def test_a_row_keeps_its_0_6_0_answer(
    corpus_db: LicenseDatabase, row: dict[str, str]
) -> None:
    """The whole pinned answer: expression, category, candidates, step and
    expansion kinds, trust and whether ``input`` is the value. A value in
    ``EXPECTED_CHANGES`` must give the answer listed there instead."""
    value = unescape_field(row["value"])
    expected = EXPECTED_CHANGES[value][0] if value in EXPECTED_CHANGES else pinned(row)
    assert answer_of(value, resolve(value, corpus_db)) == expected


def test_the_corpus_is_well_formed() -> None:
    """Distinct, escaped values; every row says what 0.7.0 should do and why."""
    values = [unescape_field(row["value"]) for row in ROWS]
    assert len(values) == len(set(values)), "a value is listed twice"
    assert all(escape_field(value) == row["value"] for value, row in zip(values, ROWS))
    assert len(ROWS) >= 100
    assert len(PARITY_FILE.read_text(encoding="utf-8").splitlines()) < 800
    for row in ROWS:
        assert row["expected_0_7_0"], row["value"]
        assert row["why"], row["value"]
        assert row["pitloom_0_21_1"].split(":")[0] in {
            "expression",
            "text",
            "noassertion",
            "none",
        }


def test_the_header_records_the_row_count_and_hash() -> None:
    """A row cannot be dropped, added or edited without the header saying so."""
    comment = next(c for c in read_comments(PARITY_FILE) if c.startswith("# rows:"))
    found = re.fullmatch(r"# rows: (\d+); sha256 .*: (\w+)", comment)
    assert found, comment
    count, digest = found.groups()
    lines = PARITY_FILE.read_text(encoding="utf-8").split("\n")
    header_row = next(i for i, line in enumerate(lines) if line.startswith("value\t"))
    body = "\n".join(lines[header_row + 1 :])
    assert int(count) == len(ROWS)
    assert hashlib.sha256(body.encode()).hexdigest() == digest


def test_a_value_may_start_with_a_hash() -> None:
    """Only the lines above the header row are comments."""
    row = next(r for r in ROWS if unescape_field(r["value"]) == "#MIT")
    assert row["value"] == "#MIT"
    assert read_rows(PARITY_FILE).count(row) == 1


def test_the_corpus_has_the_shapes_the_plan_names() -> None:
    """The gaps of the design and the evidence doc are all present."""
    values = {unescape_field(row["value"]) for row in ROWS}
    assert {
        "MIT OR ISC OR MIT OR ISC",
        "GPL-3.0 OR MIT",
        "StandardML-NJ",
        "StandardML-NJ OR MIT",
        "Apache2 OR MIT",
        "GPLv3+ OR MIT",
        "MIT OR Foo",
        "MIT AND",
        "(MIT",
        "MIT/Apache-2.0",
        "Apache License, Version 2.0",
        "Apache License 2.0 OR MIT",
        "MIT License (MIT)",
        "ISC License (ISCL)",
        "Apache Software License",
        "Python Software Foundation License",
        "Expat license",
        "OSI Approved",
        "apache-2.0",
        "BSD-3-clause",
        "UNLICENSE",
        "(MIT OR ISC) AND GPL-2.0-only WITH Classpath-exception-2.0",
    } <= values
    kinds = {row["source"].split(":")[0] for row in ROWS}
    assert {"real"} <= kinds
    assert len(kinds) >= 2


# F6, fixed by T6 (dropguard): the dropped character is the author's doubt or
# a corruption, and 0.6.0 turned it into a claim (category `separator`).
# 0.7.0 answers `unresolved`, with the reading it stopped. (A lone surrogate
# was a sixth; G1, T4b, refuses it early: tests/test_resolver_surrogate.py.)
@pytest.mark.parametrize(
    ("value", "stopped", "lost"),
    [
        ("Apache 2.0?", "Apache-2.0", "?"),
        ("Apache 2.0!", "Apache-2.0", "!"),
        ("MIT" + chr(0xFFFD), "MIT", chr(0xFFFD)),  # a decoding error
        ("MIT*", "MIT", "*"),
        ("#MIT", "MIT", "#"),
    ],
    ids=[
        "question-mark",
        "exclamation",
        "u-fffd",
        "asterisk",
        "hash",
    ],
)
def test_a_dropped_character_is_no_longer_read_as_a_licence(
    corpus_db: LicenseDatabase, value: str, stopped: str, lost: str
) -> None:
    """Fixed by T6: unresolved, a ``drop`` step that did not apply, a reason."""
    got = resolve(value, corpus_db)
    assert (got["expression"], got["category"]) == (None, "unresolved")
    assert got["reason"] == "character dropped: " + " ".join(
        f"U+{ord(c):04X}" for c in lost
    )
    assert [(s["kind"], s["applied"], s["to"]) for s in got["steps"]] == [
        ("drop", False, stopped)
    ]


# Controls: what the drop guard of T6 must keep (the plan allows white space,
# "-", "_", ".", a Unicode dash and one trailing ","), so a fix that refuses
# too much fails here.
@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("Apache–2.0", "Apache-2.0"),  # an en dash is a dash (Pd)
        ("Apache‐2.0", "Apache-2.0"),
        ("MIT.", "MIT"),
        ("MIT,", "MIT"),
        ("Apache 2.0", "Apache-2.0"),
    ],
    ids=["en-dash", "hyphen-u2010", "full-stop", "comma", "space"],
)
def test_control_what_the_drop_guard_keeps(
    corpus_db: LicenseDatabase, value: str, expected: str
) -> None:
    """A character the guard allows is still dropped silently."""
    got = resolve(value, corpus_db)
    assert (got["expression"], got["category"]) == (expected, "separator")


def test_a_row_without_an_expression_pins_none() -> None:
    """A ``-`` expression is pinned as ``None``, not as the text ``-``."""
    row = next(
        r for r in ROWS if unescape_field(r["value"]) == "Apache Software License"
    )
    assert pinned(row) == UNRESOLVED
