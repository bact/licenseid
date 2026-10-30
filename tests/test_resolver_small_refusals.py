# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Four small refusals of ``match()`` (0.8 list; decisions P130 to P133).
Characterisation first: today's answers, so that each fix shows as a flip of
the values marked ``MOVES``."""
# pylint: disable=missing-function-docstring

import time

import pytest
from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import
from packaged_list import fixture_bundle, masked
from release_fakes import ship
from resolver_helpers import no_reader_reason

from licenseid import LicenseDatabase, match
from licenseid.dropguard import ends_in_mark, ends_in_ref, joined_marks
from licenseid.quotes import ended_quote
from licenseid.resolver import match_with
from licenseid.resolvertypes import Resolution, Source

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
    "MIT+": ("MIT+", None),
    '"MIT"': ("MIT", None),
    '"MIT"..': (None, "character dropped: U+0022 U+002E"),
    '"MIT".,': (None, "character dropped: U+0022 U+002E U+002C"),
    '"MIT;"': ("MIT", None),
}

#: Item 2 (P131): a dash joined to the end of a reading no loose ID made is a
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

#: Item 3 (P132): one end mark after a ``LicenseRef-*`` that ends in a dot is an
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
    "LicenseRef-a.;;": "character dropped: U+003B",
    "LicenseRef-a.;.": "character dropped: U+003B U+002E",
    "LicenseRef-a.?": "character dropped: U+003F",
    "LicenseRef-a;;": "character dropped: U+003B",
    "LicenseRef-a;,": "character dropped: U+003B U+002C",
}

#: Item 4 (P133): quote marks, then one end mark, read as the end mark then the
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
        ("MIT-.", "-"),
        ("MIT+_", "_"),
        ("MIT+_-_", "_-"),
        ("MIT+;", ""),
    ],
)
def test_joined_marks(text: str, expected: str) -> None:
    assert joined_marks(text) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("LicenseRef-a.", True),
        ("MIT WITH AdditionRef-x-", True),
        ("DocumentRef-d:LicenseRef-a- ", True),
        ("LicenseRef-a;", False),
        ("MIT.", False),
        ("", False),
        ("MIT WITH LicenseRef", False),
    ],
)
def test_ends_in_ref(text: str, expected: bool) -> None:
    assert ends_in_ref(text) is expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("MIT;", True),
        ("MIT.", True),
        ("(MIT;)", True),
        ("[MIT,] ", True),
        ("{MIT:}", True),
        ("MIT\u2026", True),
        ("MIT", False),
        ("(MIT)", False),
        ("", False),
        (")", False),
        ("LicenseRef-a.", False),  # the dot is a character of the ID
        ("LicenseRef-a.;", True),
        ("(LicenseRef-a;)", True),
    ],
)
def test_ends_in_mark(text: str, expected: bool) -> None:
    assert ends_in_mark(text) is expected


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
    assert_answer(got, STAYS[value])


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
        ('"(MIT;)".', None),  # a mark behind a bracket, inside
        ('"[MIT,]";', None),
        ('"LicenseRef-a.;".', None),  # two marks inside
        ('"LicenseRef-a.".', '"LicenseRef-a."'),  # the dot belongs to the ID
        ('"LicenseRef-a.";', '"LicenseRef-a."'),
        ("MIT'.", "MIT'"),
        ('GPL-2.0".', 'GPL-2.0"'),
        ('"".', None),  # nothing between the marks
        ("\"MIT'.", None),  # two kinds
    ],
)
def test_ended_quote(text: str, expected: str | None) -> None:
    assert ended_quote(text) == expected


def _shapes(size: int) -> list[str]:
    """Inputs that give each new rule a long run to scan."""
    return [
        '"MIT" ' + "-" * size,
        '"' * size + "MIT" + '"' * size + ".",
        '"MIT"' + " " * size + ".",
        '"MIT"' + "." * size,
        "MIT+" + "-" * size,
        "MIT License" + "-" * size,
        "LicenseRef-a" + "." * size + ";",
        "(" * size + "MIT;" + ")" * size,
    ]


_SHAPE_IDS = ["dashes", "layers", "spaces", "dots", "plus", "prose", "ref", "brackets"]


def _seconds(db: LicenseDatabase, text: str) -> float:
    started = time.monotonic()
    match(text, db)
    return time.monotonic() - started


@pytest.mark.parametrize("text", _shapes(10_000), ids=_SHAPE_IDS)
def test_the_new_rules_are_cheap(corpus_db: LicenseDatabase, text: str) -> None:
    """10,000 characters: a quadratic path takes seconds; under coverage a
    linear one takes well under one (CI's Python 3.10 job runs under it)."""
    assert _seconds(corpus_db, text) < 2


@pytest.mark.benchmark
@pytest.mark.parametrize("index", range(len(_SHAPE_IDS)), ids=_SHAPE_IDS)
def test_the_new_rules_are_linear(corpus_db: LicenseDatabase, index: int) -> None:
    """Four times the size takes about four times as long (not sixteen)."""
    small = _seconds(corpus_db, _shapes(50_000)[index])
    large = _seconds(corpus_db, _shapes(200_000)[index])
    assert large < max(small, 0.05) * 8


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


#: Review fixes (P134 to P137): ``(expression, reason)``.
REVIEW_NOW: dict[str, tuple[str | None, str | None]] = {
    # a mark inside the quote marks, behind a bracket, is seen: two marks
    '"(MIT;)".': (None, None),
    '"(MIT.)".': (None, None),
    '"[MIT,]";': (None, None),
    # two marks, the first a dot of the ID
    '"LicenseRef-a.;".': (None, None),
    '"LicenseRef-a.,",': (None, None),
    '"LicenseRef-a.;";': (None, None),
    # the dot of the ID is a character of it, not an end mark
    '"LicenseRef-a.".': ("LicenseRef-a.", None),
    '"LicenseRef-a.";': ("LicenseRef-a.", None),
    # an ID character before the end mark is no mark
    "LicenseRef-a-;": ("LicenseRef-a-", None),
    "LicenseRef-a-:": ("LicenseRef-a-", None),
    "LicenseRef-a-,": ("LicenseRef-a-", None),
    "LicenseRef-a- ;": ("LicenseRef-a-", None),
    "LicenseRef-a-;;": (None, "character dropped: U+003B"),
    "LicenseRef-a-?": (None, "character dropped: U+003F"),
    "MIT WITH AdditionRef-x.;": ("MIT WITH AdditionRef-x.", None),
    "MIT WITH AdditionRef-x-,": ("MIT WITH AdditionRef-x-", None),
    "MIT WITH AdditionRef-x;;": (None, "character dropped: U+003B"),
    # a dash or underscore joined to the end, then another mark or none
    "MIT+-?": (None, "character dropped: U+002D U+003F"),
    "MIT+-!": (None, "character dropped: U+002D U+0021"),
    "MIT+ -;": (None, "character dropped: U+002D U+003B"),
    "MIT+?-": (None, "character dropped: U+003F U+002D"),
    "MIT+_": (None, "character dropped: U+005F"),
    "MIT License-.": (None, DASH),
    "MIT License_": (None, "character dropped: U+005F"),
    # unbalanced marks plus an end mark read (maintainer, P133)
    "MIT'.": ("MIT", None),
    "Apache-2.0'.": ("Apache-2.0", None),
    'GPL-2.0".': ("GPL-2.0", None),
    'MIT+".': ("MIT+", None),
    'MIT".': ("MIT", None),
    # no reason of a reader's own, so the default one (P5: "not found");
    # each needs a path of its own (0.8 follow-ups)
    "LicenseRef-a+-": (None, None),  # malformed: no expression to say
    "(MIT)-": (None, None),
    "(MIT+)-": (None, None),
    "License :: OSI Approved :: MIT License-": (None, None),
    "The MIT License (MIT)-": (None, None),
    "MIT License (MIT)-": (None, None),
    "MIT+ WITH X-": (None, "exception not found: X-"),
    # the guard sees the quote marks only: a single dot passes it
    '"MIT.".': (None, "character dropped: U+0022"),
    '"MIT OR ISC.".': (None, "character dropped: U+0022"),
    # marks that are no dash help no prose form, and it is no operand either
    "Apache License, Version 2.0+": (None, None),
    "Apache License, Version 2.0+ OR MIT": (
        None,
        "operand not resolved: Apache License, Version 2.0+",
    ),
    # a loose ID reads a dash or underscore as a separator: nothing refused
    "GPL-2.0-only-": ("GPL-2.0-only", None),
    "Apache-2.0--": ("Apache-2.0", None),
    "BSD-2-Clause-": ("BSD-2-Clause", None),
    "BSD 3-Clause-": ("BSD-3-Clause", None),
    "MIT_": ("MIT", None),
}


@pytest.mark.parametrize("value", sorted(REVIEW_NOW), ids=lambda v: v[:24])
def test_review_answers(corpus_db: LicenseDatabase, value: str) -> None:
    got = match(value, corpus_db)
    assert_answer(got, REVIEW_NOW[value])


def assert_answer(got: Resolution, expected: tuple[str | None, str | None]) -> None:
    """*got* has the expression and reason *expected*; a refusal listed with
    no reason has the one no reader gives (P5), never none."""
    expression, reason = expected
    assert got["expression"] == expression
    if expression is None and reason is None:
        assert no_reader_reason(got["reason"]), got["reason"]
    else:
        assert got["reason"] == reason
