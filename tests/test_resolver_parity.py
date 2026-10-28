# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The parity corpus pins what ``resolve()`` 0.6.0 answers (the 0.7.0 plan,
finding F9, task T0): ``tests/fixtures/resolver_parity.tsv`` holds real and
synthetic declared values with their 0.6.0 answers, the answer of Pitloom
0.21.1 and the answer the plan expects of 0.7.0.

A later rule pull request changes an answer on purpose: it lists the value in
``resolver_corpus.EXPECTED_CHANGES``, and this file skips that row. The
``# BUG:`` pins at the end assert answers that are wrong today; the pull
request that fixes one flips it.
"""

import re

import pytest
from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import
from resolver_corpus import (
    EXPECTED_CHANGES,
    PARITY_FILE,
    Answer,
    answer_of,
    escape,
    load_list,
    parity_rows,
    pinned,
    unescape,
)

from licenseid import LicenseDatabase, resolve

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
    """Expression, category, candidates, step kinds and expansions."""
    value = unescape(row["value"])
    if value in EXPECTED_CHANGES:
        pytest.skip(EXPECTED_CHANGES[value])
    got = resolve(value, corpus_db)
    assert answer_of(got) == pinned(row)
    steps = [s["kind"] for s in got["steps"]]
    expansions = [s["kind"] + ("" if s["applied"] else "!") for s in got["expansions"]]
    assert steps == list(load_list(row["steps_0_6_0"]))
    assert expansions == list(load_list(row["expansions_0_6_0"]))


def test_the_corpus_is_well_formed() -> None:
    """Distinct, escaped values; every row says what 0.7.0 should do and why."""
    values = [unescape(row["value"]) for row in ROWS]
    assert len(values) == len(set(values)), "a value is listed twice"
    assert all(escape(value) == row["value"] for value, row in zip(values, ROWS))
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


def test_the_corpus_has_the_shapes_the_plan_names() -> None:
    """The gaps of the design and the evidence doc are all present."""
    values = {unescape(row["value"]) for row in ROWS}
    assert {
        "MIT OR ISC OR MIT OR ISC",
        "GPL-3.0 OR MIT",
        "StandardML-NJ",
        "Apache2 OR MIT",
        "GPLv3+ OR MIT",
        "MIT OR Foo",
        "MIT AND",
        "(MIT",
        "MIT/Apache-2.0",
        "Apache License, Version 2.0",
        "MIT License (MIT)",
        "ISC License (ISCL)",
        "Apache Software License",
        "Python Software Foundation License",
        "Expat license",
        "OSI Approved",
    } <= values
    kinds = {row["source"].split(":")[0] for row in ROWS}
    assert {"real"} <= kinds
    assert len(kinds) >= 2


# BUG: F6, fixed by T6 (dropguard): the dropped character is the author's
# doubt or a corruption, and 0.6.0 turns it into a claim. Each of these
# answers the licence with category `separator`; 0.7.0 must answer
# `unresolved`.
@pytest.mark.parametrize(
    ("value", "wrong"),
    [
        ("Apache 2.0?", "Apache-2.0"),
        ("Apache 2.0!", "Apache-2.0"),
        ("MIT" + chr(0xDCFF), "MIT"),  # a lone surrogate (not UTF-8 encodable)
        ("MIT" + chr(0xFFFD), "MIT"),  # U+FFFD, a decoding error left in a value
        ("MIT*", "MIT"),
    ],
    ids=["question-mark", "exclamation", "lone-surrogate", "u-fffd", "asterisk"],
)
def test_bug_a_dropped_character_is_read_as_a_licence(
    corpus_db: LicenseDatabase, value: str, wrong: str
) -> None:
    """Pins today's wrong answer; the fix flips it."""
    got = resolve(value, corpus_db)
    assert (got["expression"], got["category"]) == (wrong, "separator")
    assert [s["kind"] for s in got["steps"]] == ["separator"]


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
    row = next(r for r in ROWS if unescape(r["value"]) == "Apache Software License")
    assert pinned(row) == Answer(None, "unresolved", ())
