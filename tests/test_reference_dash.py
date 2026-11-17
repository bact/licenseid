# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""A reference keeps the dashes and dots at its end in a tag or a field.

``LicenseRef-a-`` is a reference of its own (an idstring takes ``.`` and ``-``
at its end), and ``resolve()`` keeps it. A tag or a ``license`` field
holding ``MIT OR LicenseRef-a-`` answered ``MIT OR LicenseRef-a``, another
reference, because ``identifiers._normalize_expression`` cut every ID at
its last letter or digit. It reads each ID as ``exprtokens.expression_tokens``
does now. A reference cut inside a word (``LicenseRef-a-ä``) and an underscore
(``LicenseRef-a_``) are refused as before, and so is a tag whose last
reference has dashes glued to a comment closer (``LicenseRef-a-->``, ``MIT OR
LicenseRef-a-->``).
"""
# pylint: disable=missing-function-docstring

import json

import pytest
from conftest import GivenWarnings
from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import

from licenseid import LicenseDatabase, resolve
from licenseid.detector import LicenseDetector
from licenseid.dropguard import cut_reference
from licenseid.exprtokens import RE_TOKEN, expression_tokens

TAG = "SPDX-License-Identifier: "

#: ``value: expression`` on every channel (a tag and a field answer in their
#: own order for a bracketed value: only the references are compared).
KEPT = {
    "MIT OR LicenseRef-a-": "MIT OR LicenseRef-a-",
    "LicenseRef-a. AND MIT": "MIT AND LicenseRef-a.",
    "LicenseRef-a- OR LicenseRef-b.": "LicenseRef-a- OR LicenseRef-b.",
    "MIT OR LicenseRef-a.-": "MIT OR LicenseRef-a.-",
    "MIT OR DocumentRef-x:LicenseRef-a-": "MIT OR DocumentRef-x:LicenseRef-a-",
    "MIT OR LicenseRef-a": "MIT OR LicenseRef-a",
}


def _top(db: LicenseDatabase, text: str) -> str | None:
    found = LicenseDetector(db.location).detect(text=text)
    return found[0]["expression"] if found else None


@pytest.mark.parametrize("value", sorted(KEPT), ids=lambda v: v[:30])
def test_a_reference_keeps_its_end_on_every_channel(
    corpus_db: LicenseDatabase, value: str
) -> None:
    expected = KEPT[value]
    assert resolve(value, corpus_db)["expression"] == expected
    assert _top(corpus_db, TAG + value + "\n") == expected
    assert _top(corpus_db, json.dumps({"name": "x", "license": value})) == expected


@pytest.mark.parametrize(
    "value", ["MIT OR (LicenseRef-a- AND ISC)", "(MIT AND LicenseRef-a-) OR ISC"]
)
def test_a_bracketed_reference_keeps_its_end(
    corpus_db: LicenseDatabase, value: str
) -> None:
    for text in (TAG + value, json.dumps({"name": "x", "license": value})):
        assert "LicenseRef-a-" in (_top(corpus_db, text) or "")
        assert not (_top(corpus_db, text) or "").endswith("LicenseRef-a")


@pytest.mark.parametrize(
    "value",
    [
        "MIT OR LicenseRef-a-ä",  # cut inside a word
        "MIT OR LicenseRef-a_",
        "MIT OR LicenseRef-a+",  # a reference takes no "+"
        "GPL-2.0-only+ OR LicenseRef-a-",
    ],
    ids=ascii,
)
def test_a_refused_value_stays_refused(
    corpus_db: LicenseDatabase, given: GivenWarnings, value: str
) -> None:
    assert resolve(value, corpus_db)["expression"] is None
    assert _top(corpus_db, json.dumps({"name": "x", "license": value})) is None
    assert given.conditions() <= {"too few words for text", "invalid"}


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("MIT OR LicenseRef-a-", ["MIT", "OR", "LicenseRef-a-"]),
        ("LicenseRef-a. AND MIT", ["LicenseRef-a.", "AND", "MIT"]),
        ("(LicenseRef-a-)", ["(", "LicenseRef-a-", ")"]),
        ("GPL-2.0+ WITH Classpath-exception-2.0", None),  # as RE_TOKEN reads it
        ("MIT-", None),  # no reference: the dash is no part of the token
        ("LicenseRef-a-ä", None),  # cut inside a word: as RE_TOKEN reads it
        ("DocumentRef-x:LicenseRef-a-", ["DocumentRef-x:LicenseRef-a-"]),
        ("", []),
    ],
    ids=lambda v: ascii(v)[:30],
)
def test_expression_tokens(text: str, expected: list[str] | None) -> None:
    if expected is None:
        expected = RE_TOKEN.findall(text)
    assert expression_tokens(text) == expected


#: A tag whose last operand is a reference (alone too) with dashes right before
#: a comment closer: no answer (the reference or the closer may own the dashes; either
#: reading is another reference than the author's). The same values as an
#: argument or a field are refused already (``character dropped``, a parse
#: failure).
CLOSER_REFUSED = [
    "MIT OR LicenseRef-a-->",
    "MIT OR LicenseRef-a--}",
    "MIT OR LicenseRef-a--]]",
    "MIT AND LicenseRef-a-#}",
    "MIT OR LicenseRef-a-*/",
    "MIT OR LicenseRef-a-}",
    "MIT OR LicenseRef-a-/",
    "MIT OR LicenseRef-a->",
    "MIT OR LicenseRef-a.-->",
    "MIT OR LicenseRef-a_-->",
    "MIT OR DocumentRef-x:LicenseRef-a-->",
    "MIT WITH AdditionRef-a-->",
    "LicenseRef-a- OR LicenseRef-b-->",
    "LicenseRef-a-->",  # alone: main read LicenseRef-a--; refused (owner, 2026-11-17)
    "LicenseRef-a--}",
    "LicenseRef-a-#}",
    "LicenseRef-a-*/",
    "LicenseRef-a--]]",
]

#: Read as before: a space or the end of the value after the dashes, a
#: dot-only end, a plain ID with a closer (``STAYS``).
CLOSER_KEPT = {
    "LicenseRef-a- -->": "LicenseRef-a-",
    "LicenseRef-a>": "LicenseRef-a",
    "MIT OR LicenseRef-a- -->": "MIT OR LicenseRef-a-",
    "MIT OR LicenseRef-a. -->": "MIT OR LicenseRef-a.",
    "MIT OR LicenseRef-a- ": "MIT OR LicenseRef-a-",
    "MIT OR LicenseRef-a-": "MIT OR LicenseRef-a-",
    "MIT OR LicenseRef-a. */": "MIT OR LicenseRef-a.",
    "MIT OR LicenseRef-a>": "MIT OR LicenseRef-a",  # no dash: nothing to lose
    "MIT OR LicenseRef-a*/": "MIT OR LicenseRef-a",
    "MIT OR LicenseRef-a}": "MIT OR LicenseRef-a",
    "MIT-->": "MIT",
    "MIT*/": "MIT",
    "MIT OR ISC-->": "ISC OR MIT",
    "MIT OR ISC*/": "ISC OR MIT",
    "(MIT OR LicenseRef-a-)": "MIT OR LicenseRef-a-",
}


@pytest.mark.parametrize("value", CLOSER_REFUSED, ids=lambda v: v[-26:])
def test_a_reference_dash_glued_to_a_closer_in_a_tag_is_refused(
    corpus_db: LicenseDatabase, given: GivenWarnings, value: str
) -> None:
    assert _top(corpus_db, TAG + value) is None
    assert _top(corpus_db, "<!-- " + TAG + value) is None
    assert _top(corpus_db, json.dumps({"name": "x", "license": value})) is None
    assert given.conditions() <= {"too few words for text", "invalid"}


@pytest.mark.parametrize("value", sorted(CLOSER_KEPT), ids=lambda v: v[-26:])
def test_a_closer_beside_an_other_ending_is_read_as_before(
    corpus_db: LicenseDatabase, value: str
) -> None:
    assert _top(corpus_db, TAG + value) == CLOSER_KEPT[value]


@pytest.mark.parametrize(
    ("text", "end", "expected"),
    [
        ("MIT OR LicenseRef-a-->", 20, True),
        ("MIT OR LicenseRef-a-}", 20, True),
        ("MIT OR LicenseRef-a_-->", 19, True),  # the run is apart from the token
        ("MIT OR LicenseRef-a->", 20, True),
        ("MIT OR LicenseRef-a- -->", 20, False),  # white space: the author's
        ("MIT OR LicenseRef-a-", 20, False),  # the end of the value
        ("MIT OR LicenseRef-a. */", 21, False),  # no dash: the dot is its own
        ("LicenseRef-a-->", 13, True),  # a lone reference is refused too
        ("LicenseRef-a-*/", 13, True),
        ("LicenseRef-a- -->", 13, False),
        ("MIT OR ISC-->", 10, False),  # no reference
        ("MIT OR LicenseRef-a-x", 20, False),  # a word follows: other reader
        ("", 0, False),
    ],
    ids=lambda v: ascii(v)[:26],
)
def test_cut_reference(text: str, end: int, expected: bool) -> None:
    assert cut_reference(text, end) is expected
