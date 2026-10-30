# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The VALUE of a ``KEY=VALUE`` field of ``licenseid match``: one word of
ASCII whatever the value, and read back exactly (``result.text_field``)."""
# pylint: disable=missing-function-docstring

import pytest

from licenseid.cli import unescape_text
from licenseid.resolvertypes import Resolution, step
from licenseid.result import read_text_field, resolution_lines, text_field

VALUES = [
    ("Apache License, Version 2.0", "Apache\\x20License,\\x20Version\\x202.0"),
    ("a=b", "a=b"),
    ("a\tb", "a\\tb"),
    ("“MIT”", "\\u201cMIT\\u201d"),
    ("café", "caf\\xe9"),
    ("日本", "\\u65e5\\u672c"),
    ("\U0001f600", "\\U0001f600"),
    ("back\\slash", "back\\\\slash"),
    ("\\x20", "\\\\x20"),  # an escape written in the value stays text
    ("line\nbreak\r", "line\\nbreak\\r"),
    ("\x00\x7f", "\\x00\\x7f"),
    (" ", "\\x20"),
    ("", ""),
    ("\udcff", "\\udcff"),
    ("GPL-2.0-or-later OR MIT", "GPL-2.0-or-later\\x20OR\\x20MIT"),
]


@pytest.mark.parametrize(("value", "field"), VALUES, ids=range(len(VALUES)))
def test_a_value_is_one_ascii_word_and_reads_back(value: str, field: str) -> None:
    assert text_field(value) == field
    assert field.isascii()
    assert not any(char.isspace() for char in field)
    assert read_text_field(field) == value


@pytest.mark.parametrize(("value", "field"), VALUES, ids=range(len(VALUES)))
def test_the_escapes_are_those_text_decodes(value: str, field: str) -> None:
    """One escape grammar: ``detect --text`` decodes what a field writes."""
    assert unescape_text(field) == value


def test_none_is_empty() -> None:
    assert text_field(None) == ""


def test_every_field_of_every_line_reads_back() -> None:
    """A line splits on single spaces into ``KEY=VALUE`` fields, each read
    back to the value, an ``=`` in it included."""
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
    fields = [dict(f.split("=", 1) for f in line.split(" ")) for line in lines]
    decoded = [{k: read_text_field(v) for k, v in f.items()} for f in fields]
    assert decoded == [
        {"EXPRESSION": "MIT OR X", "CATEGORY": "lexical", "TRUST": "identity"},
        {"STEP": "trim", "FROM": awkward, "TO": "x"},
        {"STEP": "stated_qualifier", "FROM": "a b", "TO": awkward},
    ]
