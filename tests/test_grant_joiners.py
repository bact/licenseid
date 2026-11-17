# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""A run of dashes or underscores glued before an "or later" grant gets no
answer (roadmap item 54).

``GPL-2.0-- or later`` and ``MIT__ or later`` were read as the licence with
its grant, the run dropped as a separator. One glued dash or underscore
stays a separator (the maintainer's 2026-11-04 rule: ``GPL-2.0- or later``,
``GPL-2.0_ or later``); two or more are dropped characters, as ``MIT--`` is.
The same in ``resolve()``, the argument, a tag and a field.
"""
# pylint: disable=missing-function-docstring

import pytest
from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import
from grant_channels import answers, refused

from licenseid import LicenseDatabase
from licenseid.classify import grant_follows, grant_head
from licenseid.dropguard import trailing_joiners

DASH, LOW = "character dropped: U+002D", "character dropped: U+005F"

#: ``value: reason`` of ``resolve()``; no channel answers any of them.
REFUSED = {
    "GPL-2.0-- or later": DASH,
    "GPL-2.0__ or later": LOW,
    "GPL-2.0-_ or later": "character dropped: U+002D U+005F",
    "MIT__ or later": LOW,
    "MIT-- or later": DASH,
    "MIT_-_ or later": "character dropped: U+005F U+002D",
    "Apache-2.0-- or later": DASH,
    "GPLv2-- or later": DASH,
    "LGPLv2-- or later": DASH,
    "GPL-2.0–– or later": "character dropped: U+2013",
    "GPL-2.0-- or any later version": DASH,
    "GPL-2.0-- or later version": DASH,
    "GPL-2.0-- (or later)": DASH,
    "(GPL-2.0-- or later)": DASH,
    "(GPL-2.0--) or later": DASH,
    "GPL-2.0--, or later": DASH,
    "GPL-2.0--or later": DASH,
    "MIT OR GPL-2.0-- or later": DASH,
    "MIT AND (GPL-2.0__ or later)": LOW,
    "GPL-2.0-only-- or later": DASH,
}

#: ``value: expression`` read in every channel: one glued joiner, a spaced
#: run (the author's dash between words), a run after a mark.
KEPT = {
    "GPL-2.0- or later": "GPL-2.0-or-later",
    "GPL-2.0_ or later": "GPL-2.0-or-later",
    "MIT_ or later": "MIT+",
    "GPL-2.0 - or later": "GPL-2.0-or-later",
    "GPL-2.0 -- or later": "GPL-2.0-or-later",
    "GPL-2.0 - or - later": "GPL-2.0-or-later",
    "GPL-2.0 __ or later": "GPL-2.0-or-later",
    "GPL-2.0.-- or later": "GPL-2.0-or-later",
    "GPL-2.0, or later": "GPL-2.0-or-later",
    "MIT OR GPL-2.0_ or later": "GPL-2.0-or-later OR MIT",
}


@pytest.mark.parametrize("value", sorted(REFUSED), ids=lambda v: repr(v)[:30])
def test_a_glued_run_before_a_grant_gets_no_answer(
    corpus_db: LicenseDatabase, value: str
) -> None:
    assert refused(corpus_db, value) == REFUSED[value]
    assert answers(corpus_db, value) == {"argument": None, "tag": None, "field": None}


@pytest.mark.parametrize("value", sorted(KEPT), ids=lambda v: repr(v)[:30])
def test_one_glued_joiner_or_a_spaced_run_is_a_separator(
    corpus_db: LicenseDatabase, value: str
) -> None:
    assert refused(corpus_db, value) is None
    got = answers(corpus_db, value)
    assert {a[0] for a in got.values() if a} == {KEPT[value]}
    assert got["argument"] and got["field"]


@pytest.mark.parametrize(
    ("text", "least", "expected"),
    [
        ("GPL-2.0-", 1, "-"),
        ("GPL-2.0-", 2, ""),
        ("GPL-2.0--", 2, "-"),
        ("GPL-2.0-_", 2, "-_"),
        ("GPL-2.0__", 2, "_"),
        ("GPL-2.0--.", 2, "-"),  # one "." after the run is an ending
        ("GPL-2.0 --", 2, ""),  # not glued to a letter or digit
        ("LicenseRef-a--", 2, ""),  # a reference keeps its characters
    ],
)
def test_trailing_joiners_counts_a_run(text: str, least: int, expected: str) -> None:
    assert trailing_joiners(text, least=least) == expected


@pytest.mark.parametrize(
    ("before", "head"),
    [
        ("GPL-2.0 ", "GPL-2.0"),
        ("GPL-2.0- ", "GPL-2.0"),
        ("GPL-2.0_ ", "GPL-2.0_"),  # the loose reading drops one "_"
        ("GPL-2.0 -- ", "GPL-2.0"),
        ("GPL-2.0-- ", "GPL-2.0--"),  # a glued run stays with the head
        ("GPL-2.0-_ (", "GPL-2.0-_"),
        ("GPL-2.0-", None),  # "GPL-2.0-or later": a dash inside a word
    ],
)
def test_the_head_of_a_grant_keeps_a_glued_run(before: str, head: str | None) -> None:
    assert grant_head(before) == head


@pytest.mark.parametrize(
    ("gap", "expected"),
    [(" ", True), ("- ", True), (" -- ", True), ("-- ", None), ("-_ ", None)],
)
def test_a_tag_gap_judges_a_glued_run(gap: str, expected: bool | None) -> None:
    """The tag reader sees the gap between the ID and the "or" apart from the
    ID: its first line is glued to the ID."""
    assert grant_follows("GPL-2.0", f"{gap}or later") is expected
