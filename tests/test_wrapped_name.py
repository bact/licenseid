# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""A List name wrapped in marks is refused, as ``*MIT License*`` already was
(roadmap item 50, W1).

``*Apache License 2.0*`` answered ``Apache-2.0`` exact in ``detect`` while
``resolve()`` said ``not found``: only a name a loose ID reads (``MIT
License``) met the guard against dropped marks, a name of the List-name table
did not. ``resolveleaf._refuse_wrapped_name`` closes the gap in the resolver,
so ``detect`` refuses through ``resolvereason.refuses_text_match``. What stays
read: a bracket or a quote mark round the name, one end mark, a "+", and a
name inside a sentence.
"""
# pylint: disable=missing-function-docstring

import json
import time
from unittest.mock import create_autospec

import pytest
from conftest import GivenWarnings
from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import
from timing import slack

from licenseid import LicenseDatabase, resolve
from licenseid.detector import LicenseDetector
from licenseid.dropguard import edge_marks
from licenseid.listlookup import ListLookup
from licenseid.quotes import CORNER_PAIRS
from licenseid.resolveleaf import _Dropped, _refuse_wrapped_name

#: ``value: reason`` of ``resolve()``, refused on every channel.
REFUSED = {
    "*Apache License 2.0*": "character dropped: U+002A",
    "*Apache License 2.0": "character dropped: U+002A",
    "~Apache License 2.0~": "character dropped: U+007E",
    "|Apache License 2.0|": "character dropped: U+007C",
    "@Apache License 2.0": "character dropped: U+0040",
    "# Apache License 2.0": "character dropped: U+0023",
    "- Apache License 2.0": "character dropped: U+002D",
    "-- Apache License 2.0": "character dropped: U+002D",
    "... Apache License 2.0": "character dropped: U+002E",
    "<Apache License 2.0>": "character dropped: U+003C U+003E",
    "©Apache License 2.0": "character dropped: U+00A9",
    "¡Apache License 2.0!": "character dropped: U+00A1 U+0021",
    "[*Apache License 2.0*]": "character dropped: U+002A",
    '"*Apache License 2.0*"': "character dropped: U+002A",
    "*Mozilla Public License 2.0*": "character dropped: U+002A",
    "*GNU General Public License v3.0 only*": "character dropped: U+002A",
    "*Apache License 2.0*,": "character dropped: U+002A U+002C",
    # The reason names the marks, not the brackets and the plus of the name.
    "*Sun PPP License (2000)*": "character dropped: U+002A",
    "*MIT +no-false-attribs License*": "character dropped: U+002A",
}

#: Names of 10 words or more (by the normaliser) in marks: no answer either,
#: not a text match that picks another licence (the ESA-PL name answered
#: ``ESA-PL-weak-copyleft-2.4``, 0.8722, with the marks).
LONG_NAMES = [
    "European Space Agency Public License (ESA-PL) - V2.4 - Strong Copyleft (Type 1)",
    "Creative Commons Attribution Share Alike 2.0 England and Wales",
    "SIL Open Font License 1.1 with Reserved Font Name",
]
LONG_WRAPS = ["*{}*", "# {}", "- {}", "<{}>", "{}*"]

#: ``value: expression``: read, as before. Brackets and quote marks round the
#: name, one end mark, a name in a sentence.
READ = {
    "(MIT License)": "MIT",
    "[MIT License]": "MIT",
    "`Apache License 2.0`": "Apache-2.0",
    '"Apache License 2.0"': "Apache-2.0",
    "Apache License 2.0.": "Apache-2.0",
    "Apache License 2.0,": "Apache-2.0",
    "Apache License 2.0;": "Apache-2.0",
    "Apache License 2.0:": "Apache-2.0",
    "Apache License 2.0 ;": "Apache-2.0",
    "MIT License,": "MIT",
    "MIT License:": "MIT",
    "MIT License ;": "MIT",
    "Apache License 2.0+": "Apache-2.0+",
    "Apache License (2.0)": "Apache-2.0",
    "GNU General Public License v3 (GPLv3)": "GPL-3.0",
}

#: Not a wrapped List name: the core is no name, or no mark was cut. The
#: ``resolve()`` answer is unchanged; ``detect`` reads the name, inexact.
SENTENCES = {
    "**License:** Apache License 2.0": "Apache-2.0",
    "License: *Apache License 2.0*": "Apache-2.0",
    "*Apache License 2.0* applies to all files here, see the LICENSE file at "
    "the top": "Apache-2.0",
    "MIT License (see LICENSE)": "MIT",
}

#: A name with quote marks inside, in quote marks of the other kind: the
#: quotes step does not unwrap it, the guard must not read the marks as cut.
#: ``detect`` answers by name, exact, as before.
INNER_QUOTES = [
    '`BSD 3-Clause "New" or "Revised" License`',
    '\'BSD 3-Clause "New" or "Revised" License\'',
    '\u300cBSD 3-Clause "New" or "Revised" License\u300d',
]

#: Marks a "+" reader refuses (a reason of its own, kept).
PLUS = {
    "MIT License++": "qualifier stated twice: MIT License++",
    "Apache License 2.0++": "qualifier stated twice: Apache License 2.0++",
    "The MIT License++": "qualifier stated twice: MIT License++",
}

#: Known gaps, left on purpose (the answer of today): a mark after an end mark,
#: a list number.
GAPS = ["*Apache License 2.0*.", "1. Apache License 2.0"]

#: ``text: (core, marks)`` of ``dropguard.edge_marks``; None for no cut worth a
#: refusal.
EDGE = {
    "*Apache License 2.0*": ("Apache License 2.0", "**"),
    "# Apache License 2.0": ("Apache License 2.0", "#"),
    "- Apache License 2.0": ("Apache License 2.0", "-"),
    "...  Apache License 2.0": ("Apache License 2.0", "..."),
    "<MIT>": ("MIT", "<>"),
    "  *Apache License 2.0* ": ("Apache License 2.0", "**"),
    "MIT;;": ("MIT", ";;"),
    "Apache License 2.0": None,
    "Apache License 2.0.": None,
    "Apache License 2.0,": None,
    "Apache License 2.0 ;": None,
    "Apache License 2.0+": None,
    "Apache License 2.0-": None,
    "(MIT License)": None,
    '"MIT License"': None,
    "`MIT License`": None,
    "'MIT'": None,
    "*Apache License 2.0*.": ("Apache License 2.0*.", "*"),  # no name: a gap
    "1. Apache License 2.0": None,
    "": None,
    "   ": None,
}


def _field(value: str) -> str:
    return json.dumps({"name": "x", "license": value})


def _top(db: LicenseDatabase, text: str) -> str | None:
    found = LicenseDetector(db.location).detect(text=text)
    return found[0]["expression"] if found else None


def _exact(db: LicenseDatabase, text: str) -> bool | None:
    found = LicenseDetector(db.location).detect(text=text)
    return found[0]["exact"] if found else None


@pytest.mark.parametrize("value", sorted(REFUSED), ids=lambda v: ascii(v)[:30])
def test_a_list_name_in_marks_is_refused(
    corpus_db: LicenseDatabase, given: GivenWarnings, value: str
) -> None:
    got = resolve(value, corpus_db)
    assert (got["expression"], got["reason"]) == (None, REFUSED[value])
    assert [s["kind"] for s in got["steps"]] == ["drop"]
    assert _top(corpus_db, value) is None
    assert _top(corpus_db, _field(value)) is None
    assert given.conditions() <= {"too few words for text"}


@pytest.mark.parametrize("name", LONG_NAMES, ids=lambda v: v[:12])
@pytest.mark.parametrize("wrap", LONG_WRAPS)
def test_a_long_list_name_in_marks_has_no_text_answer(
    corpus_db: LicenseDatabase, given: GivenWarnings, name: str, wrap: str
) -> None:
    value = wrap.format(name)
    got = resolve(value, corpus_db)
    assert got["expression"] is None
    assert str(got["reason"]).startswith("character dropped")
    detector = LicenseDetector(corpus_db.location)
    assert detector.detect(text=value) == []
    assert detector.detect(text=name)  # the name alone is read
    assert given.conditions() <= {"too few words for text"}


def test_a_short_wrapped_name_says_why_it_has_no_answer(
    corpus_db: LicenseDatabase, given: GivenWarnings
) -> None:
    assert _top(corpus_db, "*Apache License 2.0*") is None
    assert given.conditions() == {"too few words for text"}


def test_the_final_refusal_is_for_a_listed_name_only(
    corpus_db: LicenseDatabase,
) -> None:
    # A long value that is no listed name in marks goes on to the text tiers,
    # as before: its answer is weak, not a refusal.
    value = (
        "MIT OR Apache-2.0 OR ISC OR BSD-3-Clause OR 0BSD OR Zlib OR Unlicense "
        "OR Python-2.0 OR X11*"
    )
    assert resolve(value, corpus_db)["reason"] == "character dropped: U+002A"
    assert LicenseDetector(corpus_db.location).detect(text=value)


@pytest.mark.parametrize("value", sorted(READ), ids=lambda v: ascii(v)[:30])
def test_a_list_name_in_brackets_or_quotes_is_read(
    corpus_db: LicenseDatabase, value: str
) -> None:
    assert resolve(value, corpus_db)["expression"] == READ[value]
    assert _top(corpus_db, value) == READ[value]
    assert _top(corpus_db, _field(value)) == READ[value]


@pytest.mark.parametrize(
    "value", ["Apache License 2.0,", "Apache License 2.0;", "Apache License 2.0:"]
)
def test_end_marks_of_a_list_name_stay_read(
    corpus_db: LicenseDatabase, value: str
) -> None:
    assert resolve(value, corpus_db)["expression"] == "Apache-2.0"
    assert _top(corpus_db, value) == "Apache-2.0"
    assert _exact(corpus_db, value) is False  # `separator`: an end mark dropped


@pytest.mark.parametrize("value", INNER_QUOTES, ids=lambda v: ascii(v)[:12])
def test_a_name_with_inner_quotes_in_quote_marks_is_read(
    corpus_db: LicenseDatabase, value: str
) -> None:
    found = LicenseDetector(corpus_db.location).detect(text=value)
    assert [(d["expression"], d["method"], d["exact"]) for d in found[:1]] == [
        ("BSD-3-Clause", "name", True)
    ]


@pytest.mark.parametrize("value", sorted(PLUS), ids=lambda v: ascii(v)[:30])
def test_a_plus_refusal_keeps_its_reason(
    corpus_db: LicenseDatabase, given: GivenWarnings, value: str
) -> None:
    got = resolve(value, corpus_db)
    assert (got["expression"], got["reason"]) == (None, PLUS[value])
    assert _top(corpus_db, value) is None
    assert given.conditions() <= {"too few words for text"}


def test_a_trailing_dash_keeps_its_own_reason(corpus_db: LicenseDatabase) -> None:
    got = resolve("MIT License-", corpus_db)
    assert (got["expression"], got["reason"]) == (None, "character dropped: U+002D")


@pytest.mark.parametrize("value", sorted(SENTENCES), ids=lambda v: ascii(v)[:30])
def test_a_name_in_a_sentence_is_a_name_answer(
    corpus_db: LicenseDatabase, value: str
) -> None:
    assert resolve(value, corpus_db)["expression"] is None
    found = LicenseDetector(corpus_db.location).detect(text=value)
    assert [(d["expression"], d["method"], d["exact"]) for d in found[:1]] == [
        (SENTENCES[value], "name", False)
    ]


@pytest.mark.parametrize("value", GAPS, ids=ascii)
def test_the_known_gaps_stay_as_they_are(
    corpus_db: LicenseDatabase, value: str
) -> None:
    # Left open on purpose (roadmap item 50): move one and flip the row.
    assert resolve(value, corpus_db)["expression"] is None
    assert _top(corpus_db, value) == "Apache-2.0"


@pytest.mark.parametrize("value", ["MIT OR *Apache License 2.0*"])
def test_a_wrapped_operand_is_refused_with_the_mark(
    corpus_db: LicenseDatabase, given: GivenWarnings, value: str
) -> None:
    got = resolve(value, corpus_db)
    assert (got["expression"], got["reason"]) == (None, "character dropped: U+002A")
    assert _top(corpus_db, value) is None
    assert given.conditions() <= {"too few words for text"}


def test_a_wrapped_name_beside_a_semicolon_is_not_listed(
    corpus_db: LicenseDatabase, given: GivenWarnings
) -> None:
    got = resolve("*Apache License 2.0*; MIT", corpus_db)
    assert (got["expression"], got["reason"]) == (None, "operator not stated: ;")
    assert given.conditions() <= {"too few words for text"}


def test_a_name_of_two_ids_is_not_refused() -> None:
    # The List has no name of two active IDs today: a stub holds one.
    lookup = create_autospec(ListLookup, instance=True)
    lookup.get_active_ids_by_name.return_value = {
        "one name": ["One-1.0"],
        "shared name": ["Shared-1.0", "Shared-2.0"],
    }
    _refuse_wrapped_name(lookup, "*shared name*")
    _refuse_wrapped_name(lookup, "*unlisted name*")
    with pytest.raises(_Dropped) as refused:
        _refuse_wrapped_name(lookup, "*one name*")
    assert (refused.value.lost, refused.value.license_id) == ("*", "One-1.0")


@pytest.mark.parametrize("text", sorted(EDGE), ids=lambda v: ascii(v)[:30])
def test_edge_marks_table(text: str) -> None:
    assert edge_marks(text) == EDGE[text]


@pytest.mark.parametrize(
    "make",
    [
        lambda n: "*" + "x " * n + "*",
        lambda n: "*" * n + "Apache License 2.0",
        lambda n: "Apache License 2.0" + "*" * n,
        lambda n: " " * n + "*Apache License 2.0*",
        lambda n: "." * n + "Apache License 2.0",
    ],
    ids=["words", "lead-run", "trail-run", "spaces", "dots"],
)
def test_the_edge_strip_is_linear(make) -> None:  # type: ignore[no-untyped-def]
    payload = make(20000)
    start = time.monotonic()
    edge_marks(payload)
    assert time.monotonic() - start < slack(1.0)


@pytest.mark.benchmark
@pytest.mark.parametrize("size", [200000, 1000000])
def test_the_edge_strip_is_linear_at_a_large_size(size: int) -> None:
    start = time.monotonic()
    edge_marks("*" * size + "Apache License 2.0" + "*" * size)
    assert time.monotonic() - start < slack(2.0)


@pytest.mark.parametrize("mark", sorted(set(CORNER_PAIRS) | set(CORNER_PAIRS.values())))
def test_every_corner_bracket_of_the_quote_reader_is_no_edge_mark(mark: str) -> None:
    """``dropguard`` keeps the corner brackets by hand (``quotes`` imports it):
    a pair added to ``quotes.CORNER_PAIRS`` must be kept at the edge too, or a
    quoted name would be refused as a name in marks."""
    assert edge_marks(f"{mark}Apache License 2.0") is None
