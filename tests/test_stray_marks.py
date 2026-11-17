# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""A lone bracket or slash at an end of a declared value stays refused
(roadmap item 51, decided).

``(MIT`` is the head of a cut ``(MIT OR Apache-2.0)``, ``MIT/`` of a cut
``MIT/Apache-2.0``, ``MIT)`` the tail of one: a bracket or a slash is a piece
of a structure, so a value with one of them alone is refused, as is a stray
``,``, ``*``, ``!``, ``?``, ``<>`` or ``「``. A lone quote mark is read (a
weaker answer): a quote is no piece of a structure. None of these shapes is
in the corpus of real values (10,000 PyPI projects, 172 registry values), so
nothing was lost by keeping the refusal. The rows pin ``main`` before and
after the marks work of the same release (``tests/test_hidden_in_quotes.py``).
A tag ends at the first token no operator bridges, so some of these are read
in a tag (``MIT)``: the Markdown comment idiom ``[//]: # (SPDX-...: EPL-2.0)``).
"""
# pylint: disable=missing-function-docstring

import json

import pytest
from conftest import GivenWarnings
from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import

from licenseid import LicenseDatabase, resolve
from licenseid.detector import LicenseDetector

TAG = "SPDX-License-Identifier: "

#: ``value: reason`` of ``resolve()``, refused on every channel (argument,
#: ``license`` field), whichever mark stands alone.
REFUSED = {
    "/MIT": "character dropped: U+002F",
    "MIT/": "character dropped: U+002F",
    "/MIT/": "character dropped: U+002F",
    "(MIT": "parse failed: Unexpected '('",
    "[MIT": "parse failed: Unexpected '('",
    "(GPL-2.0+": "parse failed: Unexpected '('",
    "MIT)": "parse failed: Missing matching '('",
    "MIT]": "parse failed: Missing matching '('",
    "Apache-2.0)": "parse failed: Missing matching '('",
    "GPL-2.0+)": "parse failed: Missing matching '('",
    ",MIT": "character dropped: U+002C",
    "*MIT": "character dropped: U+002A",
    "MIT*": "character dropped: U+002A",
    "MIT!": "character dropped: U+0021",
    "MIT?": "character dropped: U+003F",
    "<MIT>": "character dropped: U+003C U+003E",
    "「MIT": "character dropped: U+300C",
    "(MIT OR Apache-2.0": "parse failed: Unexpected '('",
    "MIT OR (Apache-2.0": "parse failed: Unexpected 'OR'",
}

#: Read, as a weaker answer: a lone quote mark, one ending mark.
READ = ['"MIT', 'MIT"', "'MIT", "MIT,", "MIT.", "MIT;", "MIT:"]

#: Read as written: a bracket or a quote around the whole, a slash list.
WHOLE = {
    "(MIT)": "MIT",
    "((MIT))": "MIT",
    "[MIT]": "MIT",
    "{MIT}": "MIT",
    '"MIT"': "MIT",
    "'MIT'": "MIT",
    "「MIT」": "MIT",
    "MIT/Apache-2.0": "Apache-2.0 OR MIT",
}

#: ``line: expression``: a tag ends at the first token no operator bridges,
#: so a stray closing bracket after it is read, as before.
TAGS = {
    TAG + "MIT)": "MIT",
    TAG + "Apache-2.0)": "Apache-2.0",
    TAG + "GPL-2.0+)": "GPL-2.0-or-later",
    "[//]: # (" + TAG + "EPL-2.0)": "EPL-2.0",
}


def _field(value: str) -> str:
    return json.dumps({"name": "x", "license": value})


def _top(db: LicenseDatabase, text: str) -> str | None:
    found = LicenseDetector(db.location).detect(text=text)
    return found[0]["expression"] if found else None


@pytest.mark.parametrize("value", sorted(REFUSED), ids=lambda v: ascii(v)[:30])
def test_a_lone_mark_is_refused_with_its_reason(
    corpus_db: LicenseDatabase, given: GivenWarnings, value: str
) -> None:
    got = resolve(value, corpus_db)
    assert (got["expression"], got["reason"]) == (None, REFUSED[value])
    assert _top(corpus_db, value) is None
    assert _top(corpus_db, _field(value)) is None
    assert given.conditions() <= {"too few words for text"}


@pytest.mark.parametrize("value", READ, ids=ascii)
def test_a_lone_quote_or_ending_is_read(corpus_db: LicenseDatabase, value: str) -> None:
    got = resolve(value, corpus_db)
    assert (got["expression"], got["category"]) == ("MIT", "separator")
    assert _top(corpus_db, value) == "MIT"
    assert _top(corpus_db, _field(value)) == "MIT"


@pytest.mark.parametrize("value", sorted(WHOLE), ids=lambda v: ascii(v)[:30])
def test_marks_around_the_whole_are_read(
    corpus_db: LicenseDatabase, value: str
) -> None:
    assert resolve(value, corpus_db)["expression"] == WHOLE[value]
    assert _top(corpus_db, value) == WHOLE[value]
    assert _top(corpus_db, _field(value)) == WHOLE[value]


@pytest.mark.parametrize("line", sorted(TAGS), ids=lambda v: ascii(v)[-24:])
def test_a_tag_reads_a_closing_bracket_after_its_value(
    corpus_db: LicenseDatabase, line: str
) -> None:
    found = LicenseDetector(corpus_db.location).detect(text=line)
    assert [(d["expression"], d["exact"]) for d in found[:1]] == [(TAGS[line], True)]
