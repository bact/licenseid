# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""``licenseid.dropguard.dropped``: which characters a loose reading may not
drop (task T6)."""

# pylint: disable=missing-function-docstring

import time

import pytest

from licenseid.dropguard import dropped


@pytest.mark.parametrize(
    "text",
    [
        "",
        "MIT",
        "Apache 2.0",
        "Apache_2.0",
        "Apache-2.0",
        "Apache–2.0",  # en dash (Pd)
        "Apache—2.0",  # em dash (Pd)
        "Apache‐2.0",  # hyphen U+2010 (Pd)
        "Apache−2.0",  # minus sign U+2212 is Sm, not Pd: see below
    ][:-1],
)
def test_nothing_is_dropped(text: str) -> None:
    assert dropped(text) == ""


def test_a_minus_sign_is_not_a_dash() -> None:
    """U+2212 is a math symbol (Sm), not a dash (Pd): it is refused."""
    assert dropped("Apache−2.0") == "−"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("MIT.", ""),
        ("MIT..", ""),
        ("MIT,", ""),
        ("MIT, ", ""),  # one comma at the end, white space after it
        ("MIT,,", ","),
        ("MIT,.", ","),  # the comma is no longer the last character
        ("MIT, X", ","),
        ("A,B", ","),
        (",", ""),
    ],
)
def test_one_comma_at_the_end_is_allowed(text: str, expected: str) -> None:
    assert dropped(text) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Apache 2.0?", "?"),
        ("Apache 2.0!", "!"),
        ("MIT*", "*"),
        ("#MIT", "#"),
        ('"MIT"', '"'),
        ("'MIT'", "'"),
        ("MIT�", "�"),
        ("a?b!c?", "?!"),  # each once, in order of first appearance
        ("MIT/Apache", "/"),
        ("MIT©", "©"),
        ("MIT\u200b", "\u200b"),  # also refused earlier, by the resolver
        ("MIT" + chr(0xDCFF), chr(0xDCFF)),  # a lone surrogate
        ("MIT (c)", "()"),
    ],
)
def test_other_characters_are_named(text: str, expected: str) -> None:
    assert dropped(text) == expected


@pytest.mark.parametrize("char", ["\t", "\n", " ", " ", "　"])
def test_white_space_of_any_kind_is_allowed(char: str) -> None:
    assert dropped(f"Apache{char}2.0") == ""


def test_non_ascii_letters_and_digits_are_not_dropped() -> None:
    assert dropped("Lizenzä٣") == ""  # an a-umlaut and an Arabic digit


@pytest.mark.parametrize("text", ["x" + " " * 200_000, "?" * 200_000, "," * 200_000])
def test_it_is_linear(text: str) -> None:
    start = time.monotonic()
    result = dropped(text)
    assert time.monotonic() - start < 2
    assert len(result) <= 1
