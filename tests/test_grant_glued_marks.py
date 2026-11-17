# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""A mark glued to the end of an "or later" grant gets no answer (item 54).

``resolve()`` refuses ``GPL-2.0 or later-``, ``?``, ``!`` and ``*/`` (the
author's doubt, a footnote, a comment closer). ``looseid.disambiguate_whole``,
which reads a bare deprecated ID and its prose in the raw text, answered them
as ``GPL-2.0-or-later``, exact, in the argument and in a field. It refuses a
mark glued to the grant now; one ``.``, ``,``, ``;`` or ``:`` and a closing
bracket still pass. A tag runs on into prose and is not judged here.
"""
# pylint: disable=missing-function-docstring

import pytest
from conftest import GivenWarnings
from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import
from grant_channels import answers, refused

from licenseid import LicenseDatabase
from licenseid.detector import LicenseDetector
from licenseid.dropguard import glued_marks

#: ``value: reason`` of ``resolve()``; the argument and a field get no answer.
REFUSED = {
    "GPL-2.0 or later-": "character dropped: U+002D",
    "LGPL-2.1 or later-": "character dropped: U+002D",
    "GPL-2.0 or later--": "character dropped: U+002D",
    "GPL-2.0 or later?": "character dropped: U+003F",
    "GPL-2.0 or later!": "character dropped: U+0021",
    "GPL-2.0 or later*/": "character dropped: U+002A U+002F",
    "GPL-2.0 or later version-": "character dropped: U+002D",
    "GPL-2.0 or any later version-": "character dropped: U+002D",
    "GPL-2.0 or later–": "character dropped: U+2013",
    "GPL-2.0 or later_": "character dropped: U+005F",
    "MIT or later-": "character dropped: U+002D",
    "GPL-2.0 or later}": "parse failed: Missing matching '('",
}

#: Any other mark ``resolve()`` drops (``dropguard.dropped``): no answer either.
OTHER_MARKS = [
    ">",
    "~",
    "&",
    "#",
    "|",
    "<",
    "=",
    "@",
    "\\",
    "\u2026",
    "\u2122",
    ".>",
]

#: Read as before: one ending, a closing bracket, or a mark after white space.
KEPT = {
    "GPL-2.0 or later.": "GPL-2.0-or-later",
    "GPL-2.0 or later,": "GPL-2.0-or-later",
    "GPL-2.0 or later;": "GPL-2.0-or-later",
    "GPL-2.0 or later:": "GPL-2.0-or-later",
    "GPL-2.0 or later.)": "GPL-2.0-or-later",
    "GPL-2.0 or later)": "GPL-2.0-or-later",
    "GPL-2.0 or later]": "GPL-2.0-or-later",
    "GPL-2.0 or later": "GPL-2.0-or-later",
    "GPL-2.0 or later version.": "GPL-2.0-or-later",
}


@pytest.mark.parametrize("value", sorted(REFUSED), ids=lambda v: repr(v)[:34])
def test_a_mark_glued_to_a_grant_gets_no_answer(
    corpus_db: LicenseDatabase, value: str
) -> None:
    assert refused(corpus_db, value) == REFUSED[value]
    got = answers(corpus_db, value)
    assert got["argument"] is None
    assert got["field"] is None


@pytest.mark.parametrize("mark", OTHER_MARKS, ids=repr)
def test_any_mark_resolve_drops_glued_to_a_grant_gets_no_answer(
    corpus_db: LicenseDatabase, mark: str
) -> None:
    value = f"GPL-2.0 or later{mark}"
    reason = refused(corpus_db, value)
    assert reason is not None
    assert reason.startswith("character dropped: U+")
    got = answers(corpus_db, value)
    assert got["argument"] is None
    assert got["field"] is None


@pytest.mark.parametrize("value", ["GPL-2.0 or later?", "GPL-2.0 or later-"])
def test_the_refusal_says_why_as_for_a_cut_value(
    corpus_db: LicenseDatabase, given: GivenWarnings, value: str
) -> None:
    """The reason of ``resolve()`` is the detail of the usual warning (the
    same value with another ID, ``MIT or later?``, gives it too)."""
    assert LicenseDetector(corpus_db.location).detect(text=value) == []
    assert given.conditions() == {"too few words for text"}


@pytest.mark.parametrize("value", sorted(KEPT), ids=lambda v: repr(v)[:34])
def test_an_ending_after_a_grant_is_read(
    corpus_db: LicenseDatabase, value: str
) -> None:
    got = answers(corpus_db, value)
    assert got["argument"] == (KEPT[value], True)
    assert got["field"] == (KEPT[value], True)


@pytest.mark.parametrize(
    ("text", "end", "expected"),
    [
        ("x or later-", 10, "-"),
        ("x or later--", 10, "-"),
        ("x or later?!", 10, "?!"),
        ("x or later*/", 10, "*/"),
        ("x or later_", 10, "_"),
        ("x or later..", 10, "."),  # two end marks
        ("x or later.", 10, ""),
        ("x or later)", 10, ""),  # a closing bracket or a quote mark passes
        ("x or later]", 10, ""),
        ('x or later"', 10, ""),
        ("x or later;", 10, ""),  # one ending, trimmed by the reader
        ("x or later;;", 10, ";"),
        ("x or later}", 10, "}"),
        ("x or later.)", 10, ""),
        ("x or later ?", 10, ""),  # white space ends the run
        ("x or later", 10, ""),
    ],
)
def test_glued_marks_reads_the_run_at_the_end_of_a_grant(
    text: str, end: int, expected: str
) -> None:
    assert glued_marks(text, end) == expected
