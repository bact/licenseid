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
bracket still pass. A tag refuses ``?`` and ``!`` too; it runs on into prose
and a comment closer (``*/``), which stay read: also after end marks
(``.*/``, ``.-->``) and as ``?>`` and ``%>``, and end marks alone (``...``,
``.,``), which ``resolve()`` reads.
"""
# pylint: disable=missing-function-docstring

import pytest
from conftest import GivenWarnings
from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import
from grant_channels import answers, refused

from licenseid import LicenseDatabase
from licenseid.detector import LicenseDetector
from licenseid.dropguard import glued_marks, glued_tag_marks

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


@pytest.mark.parametrize("mark", ["?", "!", "-"])
@pytest.mark.parametrize("licence", ["GPL-2.0", "LGPL-2.1", "MIT"])
def test_a_mark_glued_to_a_grant_gets_no_answer_in_a_tag(
    corpus_db: LicenseDatabase, licence: str, mark: str
) -> None:
    value = f"{licence} or later{mark}"
    assert answers(corpus_db, value)["tag"] is None
    assert refused(corpus_db, value) is not None  # as resolve() does


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("GPL-2.0 or later.", "GPL-2.0-or-later"),
        ("GPL-2.0 or later version.", "GPL-2.0-or-later"),
        ("GPL-2.0 or later */", "GPL-2.0-or-later"),
        ("GPL-2.0 or later -->", "GPL-2.0-or-later"),
        ("GPL-2.0 or later*/", "GPL-2.0-or-later"),  # a closer glued to it
        ("GPL-2.0 or later-->", "GPL-2.0-or-later"),
        ("GPL-2.0 or later#}", "GPL-2.0-or-later"),
        ("GPL-2.0 or later}", "GPL-2.0-or-later"),
        ("GPL-2.0 or later]]", "GPL-2.0-or-later"),
    ],
)
def test_an_ending_after_a_grant_is_read_in_a_tag(
    corpus_db: LicenseDatabase, value: str, expected: str
) -> None:
    assert answers(corpus_db, value)["tag"] == (expected, True)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("x or later?", "?"),
        ("x or later!", "!"),
        ("x or later?*/", "?*/"),
        ("x or later*/", ""),  # a tag reader knows no closers: left to it
        ("x or later#}", ""),
        ("x or later}", ""),
        ("x or later>", ""),
        ("x or later.", ""),
        ("x or later", ""),
    ],
)
def test_glued_tag_marks_leaves_a_comment_closer_to_the_tag_reader(
    text: str, expected: str
) -> None:
    assert glued_tag_marks(text, 10) == expected


@pytest.mark.parametrize(
    "text",
    [
        "x or later.*/",
        "x or later.-->",
        "x or later?>",
        "x or later%>",
        "x or later.#}",
        "x or later.>",
        "x or later.]]",
        "x or later;.-->",
        "x or later_-->",
        "x or later--*/",
        "x or later...",
        "x or later.,",
        "x or later;;",
        "x or later.; ",
        "x or later..",
    ],
)
def test_glued_tag_marks_leaves_end_marks_and_a_closer_to_the_tag_reader(
    text: str,
) -> None:
    assert glued_tag_marks(text, 10) == ""


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("x or later.?", "?"),
        ("x or later.!*/", "!*/"),
        ("x or later.-", "-"),
        ("x or later-", "-"),
        ("x or later_", "_"),
        ("x or later?", "?"),
        ("x or later%", "%"),
        ("x or later.\u2026", "\u2026."),  # not an end mark
    ],
)
def test_glued_tag_marks_still_names_a_mark_that_is_no_ending_or_closer(
    text: str, expected: str
) -> None:
    assert glued_tag_marks(text, 10) == expected


#: Tags whose end after the grant is end marks or a comment closer, which the
#: tag reader knows (a C, PHP, ERB, HTML or Jinja comment): read, exact.
CLOSED = {
    "GPL-2.0 or later.*/": "GPL-2.0-or-later",
    "GPL-2.0 or later.-->": "GPL-2.0-or-later",
    "GPL-2.0 or later?>": "GPL-2.0-or-later",
    "GPL-2.0 or later%>": "GPL-2.0-or-later",
    "GPL-2.0 or later.#}": "GPL-2.0-or-later",
    "GPL-2.0 or any later version-->": "GPL-2.0-or-later",
    "GPL-2.0 or later version.*/": "GPL-2.0-or-later",
    "MIT or later.*/": "MIT+",
    "GPL-2.0 or later...": "GPL-2.0-or-later",
    "GPL-2.0 or later.,": "GPL-2.0-or-later",
    "GPL-2.0 or later;;": "GPL-2.0-or-later",
    "GPL-2.0 or later.>": "GPL-2.0-or-later",
}


@pytest.mark.parametrize("value", CLOSED, ids=lambda v: v[:34])
def test_end_marks_and_a_closer_after_a_grant_are_read_in_a_tag(
    corpus_db: LicenseDatabase, value: str
) -> None:
    assert answers(corpus_db, value)["tag"] == (CLOSED[value], True)


@pytest.mark.parametrize(
    "mark", ["?*/", ".?", ".!*/", ".-", "!", "?!", "_", ".\u2026"], ids=repr
)
def test_a_mark_that_is_no_ending_or_closer_still_refuses_a_tag(
    corpus_db: LicenseDatabase, mark: str
) -> None:
    assert answers(corpus_db, f"GPL-2.0 or later{mark}")["tag"] is None


#: Tags whose grant ends in end marks and then lists another licence: no
#: answer (the end marks hid the listing from the tag reader), as for the same
#: text without the end marks.
LISTED_AFTER_MARKS = [
    "GPL-2.0 or later.; Apache-2.0",
    "GPL-2.0 or later., ISC",
    "GPL-2.0 or later.., MIT",
    "GPL-2.0 or later..., MIT",
    "GPL-2.0 or later.,, ISC",
    "GPL-2.0 or later.: , MIT",
    "GPL-3.0 or later., LGPL-3.0",
    "MIT or later.; Apache-2.0",
    "GPL-2.0 or later.) , ISC",
    "GPL-2.0 (or later)., ISC",
]


@pytest.mark.parametrize("value", LISTED_AFTER_MARKS, ids=lambda v: v[:34])
def test_end_marks_after_a_grant_do_not_hide_a_listed_licence_in_a_tag(
    corpus_db: LicenseDatabase, value: str
) -> None:
    assert answers(corpus_db, value)["tag"] is None


#: ``value: expression`` of tags whose grant ends in end marks and then an
#: operator: read as ``resolve()`` reads them, as without the end marks.
OPERATOR_AFTER_MARKS = {
    "GPL-2.0 or later., AND MIT": "GPL-2.0-or-later AND MIT",
    "GPL-2.0 or later.; OR ISC": "GPL-2.0-or-later OR ISC",
    "GPL-2.0 or later.:, AND MIT": "GPL-2.0-or-later AND MIT",
    "GPL-2.0 or later. AND MIT": "GPL-2.0-or-later AND MIT",
}


@pytest.mark.parametrize("value", sorted(OPERATOR_AFTER_MARKS), ids=lambda v: v[:34])
def test_end_marks_then_an_operator_after_a_grant_read_as_resolve_does(
    corpus_db: LicenseDatabase, value: str
) -> None:
    got = answers(corpus_db, value)
    assert got["tag"] == (OPERATOR_AFTER_MARKS[value], True)
    assert got["argument"] == got["tag"]
    assert got["field"] == got["tag"]


@pytest.mark.parametrize(
    "value",
    ["GPL-2.0 or later.; Apache-2.0", "GPL-2.0 or later., ISC", "MIT or later., ISC"],
)
def test_the_other_channels_refuse_what_a_tag_refuses_after_end_marks(
    corpus_db: LicenseDatabase, value: str
) -> None:
    got = answers(corpus_db, value)
    assert got["argument"] is None
    assert got["field"] is None
    assert refused(corpus_db, value) is not None


#: Read after end marks: prose, a bare mark, or a comment closer follows.
KEPT_AFTER_MARKS = {
    "GPL-2.0 or later.": "GPL-2.0-or-later",
    "GPL-2.0 or later...": "GPL-2.0-or-later",
    "GPL-2.0 or later.,": "GPL-2.0-or-later",
    "GPL-2.0 or later. See COPYING": "GPL-2.0-or-later",
    "GPL-2.0 or later.*/": "GPL-2.0-or-later",
    "GPL-2.0 or later.-->": "GPL-2.0-or-later",
    "GPL-2.0 or later., see COPYING": "GPL-2.0-or-later",
    "GPL-2.0 or later, and see COPYING": "GPL-2.0-or-later",  # no end mark
    "MIT OR GPL-2.0 or later. See COPYING": "GPL-2.0-or-later OR MIT",
}


@pytest.mark.parametrize("value", sorted(KEPT_AFTER_MARKS), ids=lambda v: v[:34])
def test_end_marks_after_a_grant_keep_the_reading_of_a_tag(
    corpus_db: LicenseDatabase, value: str
) -> None:
    assert answers(corpus_db, value)["tag"] == (KEPT_AFTER_MARKS[value], True)


#: A bracketed grant glued to a comment closer: read, exact (a tag reader knows
#: the closers; ``glued_tag_marks`` skipped the bracket as a mark).
BRACKET_THEN_CLOSER = {
    "GPL-2.0 (or later)*/": "GPL-2.0-or-later",
    "MIT OR (GPL-2.0 or later)*/": "GPL-2.0-or-later OR MIT",
    "MIT OR GPL-2.0 (or later)*/": "GPL-2.0-or-later OR MIT",
    "MIT AND (GPL-2.0 or later)*/": "GPL-2.0-or-later AND MIT",
    "GPL-2.0 (or later).*/": "GPL-2.0-or-later",
    "LGPL-2.1 (or later)-->": "LGPL-2.1-or-later",
    "MIT (or later)#}": "MIT+",
    "GPL-2.0 (or later)?>": "GPL-2.0-or-later",
    "GPL-2.0 (or any later version)%>": "GPL-2.0-or-later",
    "GPL-2.0 [or later]*/": "GPL-2.0-or-later",
    "GPL-2.0 (or later) */": "GPL-2.0-or-later",
}


@pytest.mark.parametrize("value", sorted(BRACKET_THEN_CLOSER), ids=lambda v: v[:34])
def test_a_bracketed_grant_glued_to_a_closer_is_read_in_a_tag(
    corpus_db: LicenseDatabase, value: str
) -> None:
    assert answers(corpus_db, value)["tag"] == (BRACKET_THEN_CLOSER[value], True)


@pytest.mark.parametrize(
    "value",
    [
        "GPL-2.0 (or later)?*/",
        "GPL-2.0 (or later)?",
        "GPL-2.0 (or later)!",
        "GPL-2.0 [or later]?",
    ],
)
def test_a_mark_after_a_bracketed_grant_still_refuses_a_tag(
    corpus_db: LicenseDatabase, value: str
) -> None:
    assert answers(corpus_db, value)["tag"] is None


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("x (or later)*/", ""),
        ("x (or later).*/", ""),
        ("x (or later)-->", ""),
        ("x [or later]#}", ""),
        ("x (or later)?>", ""),
        ("x (or later)", ""),
        ("x (or later)?", "?"),
        ("x (or later)?*/", "?*/"),
        ("x (or later))?", "?"),
    ],
)
def test_glued_tag_marks_skips_closing_brackets_before_a_closer(
    text: str, expected: str
) -> None:
    assert glued_tag_marks(text, text.index("later") + 5) == expected
