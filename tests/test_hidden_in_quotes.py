# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""A plain format character inside the quote marks of a value is left off.

``MIT\\u200b`` was read as ``MIT`` (the character stands at the end, nothing
beyond it to reorder); ``"MIT\\u200b"`` was refused, though the closing mark
stands beyond it no further than the end did. Now both read, with a ``trim``
step after ``unquote``; a zero-width character there is white space, as
outside the marks. A bidi control, a control character (``Cc``), a NUL, a
character inside a word and a value of nothing else stay refused.
"""
# pylint: disable=missing-function-docstring

import json

import pytest
from conftest import GivenWarnings
from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import

from licenseid import LicenseDatabase, resolve
from licenseid.detector import LicenseDetector
from licenseid.hiddenchars import strip_plain_format

ZWSP, ZWJ, BOM = "\u200b", "\u200d", "\ufeff"
RLO, LRM, NUL, BEL = "\u202e", "\u200e", "\x00", "\x07"
TAG_A = "\U000e0041"  # a Unicode tag character: invisible ASCII

#: ``(value, reading)``: read as ``MIT``, steps ``unquote`` then ``trim``.
READ = [
    f'"MIT{ZWSP}"',
    f'"{ZWSP}MIT"',
    f"'MIT{ZWSP}'",
    f"「MIT{ZWSP}」",
    f"«MIT{ZWSP}»",
    f'"MIT{BOM}"',
    f'"MIT{ZWJ}"',
    f'"{ZWSP}MIT{ZWSP}"',
    f'("MIT{ZWSP}")',
    f'"MIT{ZWSP}".',  # an end mark: a cut
    f'  "MIT{ZWSP}"  ',
    f'"MIT{TAG_A}"',  # no zero-width character: a cut
]

#: Still refused, with the first character it names.
REFUSED = {
    f'"MIT{RLO}"': "U+202E",
    f'"{RLO}MIT"': "U+202E",
    f'"MIT{LRM}"': "U+200E",
    f'"MIT{NUL}"': "U+0000",
    f'"MIT{BEL}"': "U+0007",
    f'"M{ZWSP}IT"': "U+200B",
    f'"{ZWSP}"': "U+200B",
    f'"MIT{ZWSP}{RLO}"': "U+200B",
    f'"{BEL}{ZWSP}MIT"': "U+0007",
    f'"MIT{ZWSP}" OR ISC': "U+200B",  # an operand's quotes are not the value's
    f"(MIT{ZWSP})": "U+200B",  # brackets are no quote marks
    f"({ZWSP}MIT)": "U+200B",
    # two marks, one after the quotes and one inside them: refused as without it
    f'"MIT.{ZWSP}".': "U+200B",
    f'"(MIT;){ZWSP}".': "U+200B",
    f'"MIT;{ZWSP}";': "U+200B",
    f"'Apache-2.0,{ZWSP}'.": "U+200B",
    # the first character it names stays the one of the whole value
    f'"{ZWSP}MIT{BEL}{ZWSP}"': "U+200B",
    f'"{ZWSP}MIT{RLO}{ZWSP}"': "U+200B",
}


def _steps(value: str, db: LicenseDatabase) -> list[str]:
    return [s["kind"] for s in resolve(value, db)["steps"]]


def _top(db: LicenseDatabase, text: str) -> tuple[str, bool] | None:
    found = LicenseDetector(db.location).detect(text=text)
    return (found[0]["expression"], found[0]["exact"]) if found else None


@pytest.mark.parametrize("value", READ, ids=lambda v: ascii(v)[:24])
def test_a_plain_format_character_inside_quotes_is_left_off(
    corpus_db: LicenseDatabase, value: str
) -> None:
    got = resolve(value, corpus_db)
    cut = value.endswith(".") or TAG_A in value
    assert (got["expression"], got["category"]) == (
        "MIT",
        "separator" if cut else "lexical",
    )
    assert _steps(value, corpus_db)[-2:] == ["unquote", "trim"]
    # `separator` is a rule's reading, not exact, in every channel
    assert _top(corpus_db, value) == ("MIT", not cut)
    assert _top(corpus_db, json.dumps({"name": "x", "license": value})) == (
        "MIT",
        not cut,
    )


def test_the_trim_step_says_what_it_left_off(corpus_db: LicenseDatabase) -> None:
    steps = resolve(f'"MIT{ZWSP}"', corpus_db)["steps"]
    assert [(s["kind"], s["from"], s["to"], s["detail"]) for s in steps] == [
        ("unquote", f'"MIT{ZWSP}"', f"MIT{ZWSP}", "balanced"),
        ("trim", f"MIT{ZWSP}", "MIT", "zero-width characters"),
    ]
    steps = resolve(f'"MIT{TAG_A}"', corpus_db)["steps"]
    assert steps[-1]["detail"] == "invisible characters"


@pytest.mark.parametrize("value", sorted(REFUSED), ids=lambda v: ascii(v)[:24])
def test_other_characters_inside_quotes_stay_refused(
    corpus_db: LicenseDatabase, given: GivenWarnings, value: str
) -> None:
    got = resolve(value, corpus_db)
    assert got["expression"] is None
    assert got["reason"] == f"control or format character: {REFUSED[value]}"
    assert _top(corpus_db, value) is None
    assert given.conditions() <= {"too few words for text"}


def test_an_operand_with_a_hidden_character_in_quotes_is_refused(
    corpus_db: LicenseDatabase, given: GivenWarnings
) -> None:
    value = f'"MIT{ZWSP}" OR ISC'
    assert resolve(value, corpus_db)["expression"] is None
    assert _top(corpus_db, value) is None
    assert given.conditions() <= {"too few words for text"}


@pytest.mark.parametrize("value", [f"MIT{ZWSP}", f"{ZWSP}MIT", "MIT\u00ad", '"MIT"'])
def test_a_value_read_before_reads_as_before(
    corpus_db: LicenseDatabase, value: str
) -> None:
    got = resolve(value, corpus_db)
    assert got["expression"] == "MIT"
    assert "trim" not in _steps(value, corpus_db)[1:]  # at most its own end trim


@pytest.mark.parametrize(
    ("text", "template", "exact"),
    [
        # a zero-width character is white space, quoted or not
        (f"MIT{ZWSP}", '[metadata]\nname = x\nlicense = "{}"\n', True),
        (f"MIT{ZWSP}", "[metadata]\nname = x\nlicense = {}\n", True),
        ("MIT", '[metadata]\nname = x\nlicense = "{}"\n', True),
        # any other hidden character is a cut, quoted or not
        (f"MIT{TAG_A}", '[metadata]\nname = x\nlicense = "{}"\n', False),
        (f"MIT{TAG_A}", "[metadata]\nname = x\nlicense = {}\n", False),
    ],
)
def test_an_ini_field_reads_a_quoted_hidden_character(
    corpus_db: LicenseDatabase, text: str, template: str, exact: bool
) -> None:
    assert _top(corpus_db, template.format(text)) == ("MIT", exact)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (f"{ZWSP}MIT{BEL}{ZWSP}", (f"{ZWSP}MIT{BEL}{ZWSP}", 0)),  # beyond the end
        (f"{ZWSP}MIT{RLO}{ZWSP}", (f"{ZWSP}MIT{RLO}{ZWSP}", 0)),
        (f"MIT{ZWSP}", ("MIT", 0)),
        (f"{ZWSP}MIT", ("MIT", 1)),
        (f"{ZWSP}{ZWSP}MIT{BOM}", ("MIT", 2)),
        (f" {ZWSP}MIT {ZWJ}", ("MIT", 2)),
        ("MIT", ("MIT", 0)),  # nothing to leave off
        (" MIT ", (" MIT ", 0)),  # white space alone is not this function's
        (ZWSP, (ZWSP, 0)),  # nothing else is left
        (f"MIT{RLO}", (f"MIT{RLO}", 0)),
        (f"MIT{ZWSP}{RLO}", (f"MIT{ZWSP}{RLO}", 0)),  # a bidi control is no format
        (f"{BEL}MIT{ZWSP}", (f"{BEL}MIT{ZWSP}", 0)),
        (f"MIT{ZWSP}{BEL}", (f"MIT{ZWSP}{BEL}", 0)),
        (f"M{ZWSP}IT", (f"M{ZWSP}IT", 0)),  # inside a word
        ("", ("", 0)),
    ],
    ids=lambda v: ascii(v)[:20],
)
def test_strip_plain_format(text: str, expected: tuple[str, int]) -> None:
    assert strip_plain_format(text) == expected


@pytest.mark.parametrize(
    ("value", "span"),
    [
        (f'"{ZWSP}MIT"', (2, 5)),
        (f'{ZWSP}"{ZWSP}MIT"', (3, 6)),
        (f'"MIT{ZWSP}"', (1, 4)),
        (f'("{ZWSP}MIT")', (3, 6)),
        (f"'{ZWSP}MIT{ZWSP}'", (2, 5)),
        (f'  "{ZWSP}MIT"  ', (4, 7)),
        (f'"{ZWSP}MIT".', (2, 5)),
    ],
    ids=lambda v: ascii(v)[:24],
)
def test_the_span_of_the_operand_indexes_the_raw_value(
    corpus_db: LicenseDatabase, value: str, span: tuple[int, int]
) -> None:
    operand = resolve(value, corpus_db)["operands"][0]
    assert tuple(operand["span"]) == span
    assert value[span[0] : span[1]] == "MIT"
