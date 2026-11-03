# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Task ``fixr``, review round 3: the loose "or later" grant of item 4 is
withdrawn (it read values past the drop guard), and a misplaced mark no
longer hides mismatched brackets. Every value here gives the answer of
``main`` before the task, but the mixed quote marks of item 3.

Each test was first a pin of what the branch did (``# BUG:``).
"""
# pylint: disable=missing-function-docstring

import pytest

from licenseid import LicenseDatabase, match


def _answer(db: LicenseDatabase, value: str) -> tuple[str | None, str, str | None]:
    got = match(value, db)
    return got["expression"], got["category"], got["reason"]


@pytest.mark.parametrize(
    "value",
    [
        "GPL-2.0 (or later)!",
        "AGPL-3.0 (or later) / ",
        "GPL-3.0 (or-later)…",
        "AGPL-3.0\n(or-later)!",
        "GPL-2.0 or_later)?",
        "GPL-2.0 )or_later(",
        "GPL-2.0 or)_later",
        "GPL-2.0 (or)(later)",
        "GPL-2.0 or}{later",
        "GPL-2.0 (or_later).",
        "GPL-2.0 ((or_later))",
    ],
    ids=ascii,
)
def test_a_loose_grant_past_the_drop_guard(
    corpus_db: LicenseDatabase, value: str
) -> None:
    # BUG: read as a grant, a mark or a bracket dropped in silence
    assert _answer(corpus_db, value)[1:] == ("stated_qualifier", None)


@pytest.mark.parametrize(
    "value", ["GPL-2.0 or_later or later", "GPL-2.0 or_later+", "GPL-2.0 or-later+"]
)
def test_a_qualifier_stated_twice_after_a_loose_grant(
    corpus_db: LicenseDatabase, value: str
) -> None:
    # BUG: not found, not malformed
    assert _answer(corpus_db, value) == (None, "unresolved", f"not found: {value}")


@pytest.mark.parametrize(
    ("value", "reason"),
    [
        ("(MIT]+ OR ISC", "plus after a bracket: (MIT]+"),
        ("(MIT OR ISC]+ OR Zlib", "plus after a bracket: (MIT OR ISC]+"),
    ],
)
def test_a_plus_after_mismatched_brackets(
    corpus_db: LicenseDatabase, value: str, reason: str
) -> None:
    # BUG: a "(" paired with a "]"
    assert _answer(corpus_db, value) == (None, "malformed", reason)


def test_quotes_around_mismatched_brackets(corpus_db: LicenseDatabase) -> None:
    # BUG: a "(" paired with a "]"
    assert _answer(corpus_db, '"(MIT]" OR Zlib') == (
        None,
        "unresolved",
        "character dropped: U+0022",
    )
