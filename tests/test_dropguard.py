# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""``licenseid.dropguard.dropped``: which characters a loose reading may not
drop (task T6)."""

# pylint: disable=missing-function-docstring

import time

import pytest

from licenseid.dropguard import code_points, dropped


@pytest.mark.parametrize(
    "text",
    [
        "",
        "MIT",
        "Apache 2.0",
        "Apache_2.0",
        "Apache-2.0",
        "Apache\u20132.0",  # en dash
        "Apache\u20142.0",  # em dash
        "Apache\u20102.0",  # hyphen U+2010
        "Apache\u22122.0",  # minus sign: a dash of normalize_text
        "Apache\ufe632.0",  # small hyphen-minus
        "Apache\uff0d2.0",  # fullwidth hyphen-minus
    ],
)
def test_nothing_is_dropped(text: str) -> None:
    assert dropped(text) == ""


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Apache\u301c2.0", "\u301c"),  # wave dash: Pd, not a dash of normalize
        ("Apache\u30a02.0", "\u30a0"),  # katakana-hiragana double hyphen: Pd
        ("\u02bcMIT\u02bc", "\u02bc"),  # modifier letters: alphanumeric, but quotes
        ("MIT\u02b9\u02ba", "\u02b9\u02ba"),
        ("\u00abMIT\u00bb", "\u00ab\u00bb"),
    ],
)
def test_the_sets_are_those_of_normalize_not_a_unicode_category(
    text: str, expected: str
) -> None:
    assert dropped(text) == expected


def test_code_points() -> None:
    assert code_points("?!") == "U+003F U+0021"
    assert code_points("\U0001f600") == "U+1F600"
    assert code_points("\udcff") == "U+DCFF"
    assert code_points("") == ""


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
