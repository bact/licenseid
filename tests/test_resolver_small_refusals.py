# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Four small refusals of ``match()`` (0.8 list; decisions P120 to P123).
Characterisation first: today's answers, so that each fix shows as a flip of
the values marked ``MOVES``."""
# pylint: disable=missing-function-docstring

import time

import pytest
from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import
from packaged_list import fixture_bundle, masked
from release_fakes import ship

from licenseid import LicenseDatabase, match
from licenseid.dropguard import end_dashes
from licenseid.quotes import ended_quote
from licenseid.resolver import match_with
from licenseid.resolvertypes import Source

DASH = "character dropped: U+002D"

#: Item 1: a value that is no string.
NOT_TEXT: list[object] = [None, b"MIT", 1]

#: Answers that do not move: ``(expression, reason)``.
STAYS: dict[str, tuple[str | None, str | None]] = {
    "MIT -": (None, "character dropped: U+002D"),
    "MIT;": ("MIT", None),
    "MIT,": ("MIT", None),
    'MIT,"': ("MIT", None),
    'MIT."': ("MIT", None),
    "LicenseRef-a;": ("LicenseRef-a", None),
    "LicenseRef-a;;": (None, "character dropped: U+003B"),
    "LicenseRef-a?": (None, "character dropped: U+003F"),
    "MIT-": ("MIT", None),  # a loose ID reads a dash as a separator
    "MIT--": ("MIT", None),
    "Apache 2.0-": ("Apache-2.0", None),
    "GPL-2.0 or later-": ("GPL-2.0-or-later", None),
    "LicenseRef-a-": ("LicenseRef-a-", None),
    "MIT License.": ("MIT", None),
    "MIT License;;": (None, "character dropped: U+003B"),
    "Apache-2.0 License+": (None, None),
    "MIT License -": (None, DASH),
    "MIT+-?": (None, None),  # a gap: a dash and a mark after a plus
    "MIT+": ("MIT+", None),
    '"MIT"': ("MIT", None),
    '"MIT"..': (None, "character dropped: U+0022 U+002E"),
    '"MIT".,': (None, "character dropped: U+0022 U+002E U+002C"),
    '"MIT;"': ("MIT", None),
}

#: Item 2 (P121): a dash joined to the end of a reading no loose ID made is a
#: dropped character, as a lone dash is (``MIT -``).
DASHED: dict[str, tuple[str | None, str | None]] = {
    "MIT+-": (None, DASH),
    "MIT+--": (None, DASH),
    "MIT License--": (None, DASH),
    "MIT License-": (None, DASH),
    "The MIT License--": (None, DASH),
    "Apache License, Version 2.0--": (None, DASH),
    "Apache-2.0+\u2013": (None, "character dropped: U+2013"),
    "MIT+\u2013-": (None, "character dropped: U+2013 U+002D"),
    "MIT WITH Classpath-exception-2.0-": (None, DASH),
    "GPL-2.0+ -": (None, DASH),
}

#: Item 3 (P122): one end mark after a ``LicenseRef-*`` that ends in a dot is an
#: ending, as after any ID; the dot is a character of the ID (P80).
REF_ENDED: dict[str, str] = {
    "LicenseRef-a.;": "LicenseRef-a.",
    "LicenseRef-a.,": "LicenseRef-a.",
    "LicenseRef-a.:": "LicenseRef-a.",
    "LicenseRef-a. ;": "LicenseRef-a.",
    "LicenseRef-a..;": "LicenseRef-a..",
    "DocumentRef-x:LicenseRef-a.;": "DocumentRef-x:LicenseRef-a.",
    "MIT OR LicenseRef-a.;": "MIT OR LicenseRef-a.",
}
REF_REFUSED: dict[str, str] = {
    "LicenseRef-a.;;": "character dropped: U+002E U+003B",
    "LicenseRef-a.;.": "character dropped: U+002E U+003B",
    "LicenseRef-a.?": "character dropped: U+003F",
    "LicenseRef-a;;": "character dropped: U+003B",
    "LicenseRef-a;,": "character dropped: U+003B U+002C",
}

#: Item 4 (P123): quote marks, then one end mark, read as the end mark then the
#: marks come off (the order they stand in); both orders read the same.
QUOTED_ENDED: dict[str, str] = {
    '"MIT".': "MIT",
    '"MIT",': "MIT",
    '"MIT";': "MIT",
    '"MIT":': "MIT",
    '"MIT" .': "MIT",
    '"MIT" ; ': "MIT",
    "'MIT'.": "MIT",
    "\u201cMIT\u201d,": "MIT",
    "\u00abMIT\u00bb.": "MIT",
    '""MIT"".': "MIT",
    '"MIT+".': "MIT+",
    '"GPL-2.0 or later".': "GPL-2.0-or-later",
    '"MIT OR ISC".': "ISC OR MIT",
    'MIT".': "MIT",
    'MIT,"': "MIT",  # the other order, as before
    'MIT."': "MIT",
}
QUOTED_REFUSED: dict[str, str] = {
    '"MIT"..': "character dropped: U+0022 U+002E",
    '"MIT".,': "character dropped: U+0022 U+002E U+002C",
    '"MIT",,': "character dropped: U+0022 U+002C",
    '"MIT"...': "character dropped: U+0022 U+002E",
    '"MIT.".': "character dropped: U+0022",  # a mark inside and one outside
    '"MIT;".': "character dropped: U+0022 U+003B",
    "\"MIT'.": "character dropped: U+0022 U+0027",  # two kinds (P16)
    '"MIT"+': "character dropped: U+0022",
    '"MIT"."': "character dropped: U+0022",
}


@pytest.mark.parametrize("value", sorted(DASHED), ids=lambda v: v[:20])
def test_a_dash_after_a_plus_or_a_prose_form_is_a_dropped_character(
    corpus_db: LicenseDatabase, value: str
) -> None:
    got = match(value, corpus_db)
    assert (got["expression"], got["reason"]) == DASHED[value]
    assert got["category"] == "unresolved"
    assert [(s["kind"], s["applied"]) for s in got["steps"]] == [("drop", False)]
    assert got["steps"][0]["from"] in value


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("", ""),
        ("MIT", ""),
        ("MIT+-", "-"),
        ("MIT+--", "-"),
        ("MIT+-\u2013", "-\u2013"),
        ("MIT+- \t", "-"),
        ("-", "-"),
        ("MIT-.", ""),
        ("MIT+- x", ""),
    ],
)
def test_end_dashes(text: str, expected: str) -> None:
    assert end_dashes(text) == expected


@pytest.mark.parametrize("value", sorted(REF_ENDED), ids=lambda v: v[:20])
def test_one_end_mark_after_a_dotted_licenseref_is_an_ending(
    corpus_db: LicenseDatabase, value: str
) -> None:
    got = match(value, corpus_db)
    assert (got["expression"], got["reason"]) == (REF_ENDED[value], None)
    assert got["category"] == "separator"
    kinds = [(s["kind"], s["detail"]) for s in got["steps"]]
    assert ("separator", "end mark") in kinds


@pytest.mark.parametrize("value", sorted(REF_REFUSED), ids=lambda v: v[:20])
def test_two_marks_after_a_licenseref_are_refused(
    corpus_db: LicenseDatabase, value: str
) -> None:
    got = match(value, corpus_db)
    assert (got["expression"], got["reason"]) == (None, REF_REFUSED[value])
    assert [s["kind"] for s in got["steps"]] == ["drop"]


@pytest.mark.parametrize("value", sorted(STAYS), ids=lambda v: v[:20])
def test_an_answer_that_does_not_move(corpus_db: LicenseDatabase, value: str) -> None:
    got = match(value, corpus_db)
    assert (got["expression"], got["reason"]) == STAYS[value]


@pytest.mark.parametrize("value", sorted(QUOTED_ENDED), ids=lambda v: v[:20])
def test_one_end_mark_after_quote_marks_is_an_ending(
    corpus_db: LicenseDatabase, value: str
) -> None:
    got = match(value, corpus_db)
    assert (got["expression"], got["reason"]) == (QUOTED_ENDED[value], None)
    assert got["category"] == "separator"


@pytest.mark.parametrize("value", ['"MIT".', '"MIT" ;', "'MIT'."])
def test_the_steps_are_in_the_order_they_apply(
    corpus_db: LicenseDatabase, value: str
) -> None:
    """The end mark stands outside the marks, so it comes off first."""
    got = match(value, corpus_db)
    assert [(s["kind"], s["detail"]) for s in got["steps"]] == [
        ("separator", "end mark"),
        ("unquote", "balanced"),
    ]
    first, second = got["steps"]
    assert first["from"] == value.strip()
    assert first["to"] == second["from"]
    assert second["to"] == "MIT"


@pytest.mark.parametrize("value", sorted(QUOTED_REFUSED), ids=lambda v: v[:20])
def test_other_marks_after_quote_marks_are_refused_with_a_reason(
    corpus_db: LicenseDatabase, value: str
) -> None:
    got = match(value, corpus_db)
    assert (got["expression"], got["reason"]) == (None, QUOTED_REFUSED[value])
    assert [s["kind"] for s in got["steps"]] == ["drop"]


@pytest.mark.parametrize(
    "value", ['MIT,"', 'MIT."', '"MIT".', '"MIT",', '"MIT";', "'MIT'."]
)
def test_both_orders_give_one_answer(corpus_db: LicenseDatabase, value: str) -> None:
    got = match(value, corpus_db)
    assert (got["expression"], got["category"]) == ("MIT", "separator")


@pytest.mark.parametrize("value", NOT_TEXT, ids=lambda v: type(v).__name__)
def test_a_value_that_is_no_string_is_a_type_error(
    corpus_db: LicenseDatabase, value: object
) -> None:
    message = f"value must be str, not {type(value).__name__}"
    with pytest.raises(TypeError, match=message):
        match(value, corpus_db)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match=message):
        match_with(corpus_db, value)  # type: ignore[arg-type]


@pytest.mark.parametrize("source", ["auto", "database", "packaged"])
def test_the_type_is_judged_before_any_list_is_read(source: Source) -> None:
    """No database and no packaged list in this environment: reading the
    list would raise ``DatabaseNotReadyError``; the type comes first."""
    with pytest.raises(TypeError):
        match(None, source=source)  # type: ignore[arg-type]


def test_a_string_subclass_is_a_string(corpus_db: LicenseDatabase) -> None:
    class Text(str):
        """A caller's own string type."""

    assert match(Text("MIT"), corpus_db)["expression"] == "MIT"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ('"MIT".', '"MIT"'),
        ('"MIT" ; ', '"MIT"'),
        ("“MIT”:", "“MIT”"),
        ('MIT".', 'MIT"'),
        ('"MIT"', None),  # no end mark
        ('"MIT;"', None),  # the mark is inside: unquote reads it
        ('"MIT"..', None),
        ('"MIT".,', None),
        ('"MIT.".', None),
        ("MIT.", None),  # no quote mark before the end mark
        ("MIT;", None),
        ('"."', None),
        ('"".', None),  # nothing between the marks
        ("\"MIT'.", None),  # two kinds
    ],
)
def test_ended_quote(text: str, expected: str | None) -> None:
    assert ended_quote(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        '"MIT" ' + "-" * 100_000,
        '"' * 100_000 + "MIT" + '"' * 100_000 + ".",
        '"MIT"' + " " * 100_000 + ".",
        '"MIT"' + "." * 100_000,
        "MIT+" + "-" * 100_000,
        "MIT License" + "-" * 100_000,
    ],
    ids=["dashes", "layers", "spaces", "dots", "plus-dashes", "prose-dashes"],
)
def test_the_new_rules_are_linear(corpus_db: LicenseDatabase, text: str) -> None:
    """Ten times the size would take ten times as long; 2 s for 200,000
    characters leaves room for a slow runner and fails a quadratic path."""
    started = time.monotonic()
    match(text, corpus_db)
    assert time.monotonic() - started < 2


_MOVED = [
    *DASHED,
    *REF_ENDED,
    *REF_REFUSED,
    *QUOTED_ENDED,
    *QUOTED_REFUSED,
    *STAYS,
]


def test_packaged_and_database_answers_agree(
    monkeypatch: pytest.MonkeyPatch, bundle_db: LicenseDatabase
) -> None:
    ship(monkeypatch, fixture_bundle())
    differences = [
        value
        for value in _MOVED
        if masked(match(value, bundle_db)) != masked(match(value, source="packaged"))
    ]
    assert not differences, differences
