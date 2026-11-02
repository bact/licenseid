# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The VALUE of a ``KEY=VALUE`` field of a result line: as it is, but for
the four characters that would end a field or a line or start an escape,
and read back exactly (``result.text_field``, ``read_text_field``)."""
# pylint: disable=missing-function-docstring

import pytest

from licenseid.resolvertypes import Resolution, step
from licenseid.result import (
    fields_line,
    read_text_field,
    resolution_lines,
    text_field,
)

VALUES = [
    ("Apache License, Version 2.0", "Apache License, Version 2.0"),
    ("a=b", "a=b"),
    ("a\tb", "a\\tb"),
    ("\u201cMIT\u201d", "\u201cMIT\u201d"),
    ("caf\u00e9", "caf\u00e9"),
    ("\U0001f600", "\U0001f600"),
    ("back\\slash", "back\\\\slash"),
    ("\\x20", "\\\\x20"),  # an escape written in the value stays text
    ("\\u00e9", "\\\\u00e9"),
    ("line\nbreak\r", "line\\nbreak\\r"),
    ("\x00\x7f\u2028", "\x00\x7f\u2028"),  # only four are escaped
    (" ", " "),
    ("", ""),
    ("GPL-2.0-or-later OR MIT", "GPL-2.0-or-later OR MIT"),
]


@pytest.mark.parametrize(("value", "field"), VALUES, ids=range(len(VALUES)))
def test_a_value_holds_no_tab_or_line_break_and_reads_back(
    value: str, field: str
) -> None:
    assert text_field(value) == field
    assert not {"\t", "\r", "\n"} & set(field)
    assert read_text_field(field) == value


@pytest.mark.parametrize(
    ("written", "value"),
    [
        ("caf\\xe9", "caf\u00e9"),
        ("\\u201cMIT\\u201d", "\u201cMIT\u201d"),
        ("\\U0001f600", "\U0001f600"),
        ("\\\\xe9", "\\xe9"),  # an escaped backslash, then text
        ("\\q\\x4", "\\q\\x4"),  # no escape of the rule: left as it is
    ],
    ids=["latin", "bmp", "astral", "backslash", "other"],
)
def test_the_escapes_of_an_unencodable_character_read_back(
    written: str, value: str
) -> None:
    """What ``output.echo`` writes for a character the stream cannot encode."""
    assert read_text_field(written) == value


def test_a_line_is_fields_joined_by_one_tab() -> None:
    assert fields_line(A="x y", B=None, C="a\tb") == "A=x y\tB=\tC=a\\tb"


def test_none_is_empty() -> None:
    assert text_field(None) == ""


def test_every_field_of_every_line_reads_back() -> None:
    """A line splits on tabs into ``KEY=VALUE`` fields, each read back to
    the value, an ``=`` in it included."""
    awkward = "x = y\té \\"
    resolution: Resolution = {  # type: ignore[typeddict-item]
        "expression": "MIT OR X",
        "category": "lexical",
        "trust": "identity",
        "steps": [step("trim", True, awkward, "x"), step("drop", False, "no", "no")],
        "expansions": [step("stated_qualifier", True, "a b", awkward)],
        "reason": None,
    }
    lines = resolution_lines(resolution)
    fields = [dict(f.split("=", 1) for f in line.split("\t")) for line in lines]
    decoded = [{k: read_text_field(v) for k, v in f.items()} for f in fields]
    assert decoded == [
        {"EXPRESSION": "MIT OR X", "CATEGORY": "lexical", "TRUST": "identity"},
        {"STEP": "trim", "FROM": awkward, "TO": "x"},
        {"STEP": "stated_qualifier", "FROM": "a b", "TO": awkward},
    ]
