# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Task ``fixr``, review round 3: the loose "or later" grant of item 4 is
withdrawn (it read values past the drop guard), and a misplaced mark no
longer hides mismatched brackets. Every value here gives the answer of
``main`` before the task, but the mixed quote marks of item 3.

Each test was first a pin of what the branch did (``# BUG:``); it now holds
the answer of ``main``.
"""
# pylint: disable=missing-function-docstring

import pytest

from licenseid import LicenseDatabase, resolve


def _answer(db: LicenseDatabase, value: str) -> tuple[str | None, str, str | None]:
    got = resolve(value, db)
    return got["expression"], got["category"], got["reason"]


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        # a mark or a bracket the drop guard refuses
        ("GPL-2.0 (or later)!", (None, "unresolved", "character dropped: U+0021")),
        ("AGPL-3.0 (or later) / ", (None, "unresolved", "character dropped: U+002F")),
        ("GPL-3.0 (or-later)\u2026", (None, "unresolved", "character dropped: U+2026")),
        # a line break before the grant is white space, as a space is (it
        # was "qualifier stated twice")
        ("AGPL-3.0\n(or-later)!", (None, "unresolved", "character dropped: U+0021")),
        # brackets inside the words: no grant, no ID
        ("GPL-2.0 or_later)?", (None, "unresolved", "not found: GPL-2.0 or_later)?")),
        ("GPL-2.0 )or_later(", (None, "unresolved", "not found: GPL-2.0 )or_later(")),
        ("GPL-2.0 or)_later", (None, "unresolved", "not found: GPL-2.0 or)_later")),
        (
            "GPL-2.0 (or)(later)",
            (None, "unresolved", "not found: GPL-2.0 (or)(later)"),
        ),
        ("GPL-2.0 or}{later", (None, "unresolved", "not found: GPL-2.0 or}{later")),
        (
            "GPL-2.0 (or_later).",
            (None, "unresolved", "not found: GPL-2.0 (or_later)."),
        ),
        (
            "GPL-2.0 ((or_later))",
            (None, "unresolved", "not found: GPL-2.0 ((or_later))"),
        ),
        # a qualifier stated twice
        (
            "GPL-2.0 or_later or later",
            (None, "malformed", "qualifier stated twice: GPL-2.0 or_later or later"),
        ),
        (
            "GPL-2.0 or_later+",
            (None, "malformed", "qualifier stated twice: GPL-2.0 or_later+"),
        ),
        (
            "GPL-2.0 or-later+",
            (None, "malformed", "qualifier stated twice: GPL-2.0 or-later+"),
        ),
        # the separator spellings, as on main
        ("GPL-2.0 or_later", ("GPL-2.0-or-later", "separator", None)),
        (
            "GFDL-1.3-invariants or later",
            ("GFDL-1.3-invariants-or-later", "separator", None),
        ),
    ],
    ids=ascii,
)
def test_an_or_later_reads_as_on_main(
    corpus_db: LicenseDatabase, value: str, expected: tuple[object, ...]
) -> None:
    assert _answer(corpus_db, value) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        # brackets of two kinds: no group, as on main
        ("(MIT]+ OR ISC", (None, "unresolved", "not found: (MIT]+ OR ISC")),
        (
            "(MIT OR ISC]+ OR Zlib",
            (None, "unresolved", "not found: (MIT OR ISC]+ OR Zlib"),
        ),
        ("(MIT] OR ISC", (None, "malformed", "mismatched brackets")),
        ('"(MIT]" OR Zlib', (None, "unresolved", 'not found: "(MIT]" OR Zlib')),
        ("(MIT]) OR (ISC)+", (None, "unresolved", "not found: (MIT]) OR (ISC)+")),
        # brackets of one kind, nested in another: a group
        ("([MIT])+ OR ISC", (None, "malformed", "plus after a bracket: ([MIT])+")),
        ('"[MIT]" AND Zlib', (None, "unresolved", "character dropped: U+0022")),
    ],
)
def test_a_misplaced_mark_beside_mismatched_brackets(
    corpus_db: LicenseDatabase, value: str, expected: tuple[object, ...]
) -> None:
    assert _answer(corpus_db, value) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        # two double quote marks pair, whichever they are (normalize.QUOTE_KIND)
        (
            '\u201c(MIT)" OR Zlib',
            (None, "unresolved", "character dropped: U+201C U+0022"),
        ),
        (
            '"(MIT)\u201d OR Zlib',
            (None, "unresolved", "character dropped: U+0022 U+201D"),
        ),
        # one mark more on one end: unbalanced, no quotes around a group
        ('""(MIT)" OR Zlib', (None, "unresolved", 'not found: ""(MIT)" OR Zlib')),
        # a double and a single mark do not: no quotes around a group
        ("\"(MIT)' OR Zlib", (None, "unresolved", "not found: \"(MIT)' OR Zlib")),
        ("'(MIT)\" OR Zlib", (None, "unresolved", "not found: '(MIT)\" OR Zlib")),
    ],
    ids=ascii,
)
def test_mixed_quote_marks_around_a_group(
    corpus_db: LicenseDatabase, value: str, expected: tuple[object, ...]
) -> None:
    assert _answer(corpus_db, value) == expected
