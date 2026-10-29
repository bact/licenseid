# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""``licenseid.quotes.unquote`` and ``normalize.QUOTE_KIND`` (task T6b)."""

# pylint: disable=missing-function-docstring

import itertools
import time

import pytest
from resolver_corpus import EXCEPTION_LIST, LICENSE_LIST, list_rows

from licenseid.normalize import QUOTE_KIND, RE_QUOTES
from licenseid.quotes import STRAY_MARKS, Unquoted, unquote

SINGLE = [mark for mark, kind in QUOTE_KIND.items() if kind == "single"]
DOUBLE = [mark for mark, kind in QUOTE_KIND.items() if kind == "double"]


def test_the_kinds_cover_every_quote_of_normalize() -> None:
    """One reader: every mark RE_QUOTES folds has a kind, and the only marks
    added are the ASCII apostrophe and the grave accent."""
    folded = {chr(code) for code in range(0x110000) if RE_QUOTES.match(chr(code))}
    assert folded <= set(QUOTE_KIND)
    assert set(QUOTE_KIND) - folded == {"'", "`"}
    assert set(QUOTE_KIND.values()) == {"single", "double"}


@pytest.mark.parametrize("marks", [SINGLE, DOUBLE], ids=["single", "double"])
def test_any_two_marks_of_one_kind_pair(marks: list[str]) -> None:
    for opening, closing in itertools.product(marks, repeat=2):
        assert unquote(f"{opening}MIT{closing}") == Unquoted("MIT", True, "balanced")


def test_marks_of_two_kinds_do_not_pair() -> None:
    for single, double in itertools.product(SINGLE, DOUBLE):
        assert unquote(f"{single}MIT{double}") is None
        assert unquote(f"{double}MIT{single}") is None


PAIR_ONLY = sorted(set(QUOTE_KIND) - STRAY_MARKS)


def test_only_primes_and_modifier_letters_pair_without_straying() -> None:
    assert PAIR_ONLY == list("\u02b9\u02ba\u02bb\u02bc\u02bd\u2032\u2033\u2034")


@pytest.mark.parametrize("mark", sorted(STRAY_MARKS))
def test_a_mark_on_one_end_is_the_stray(mark: str) -> None:
    assert unquote(f"{mark}MIT") == Unquoted("MIT", False, "unbalanced, start")
    assert unquote(f"MIT{mark}") == Unquoted("MIT", False, "unbalanced, end")


@pytest.mark.parametrize("mark", PAIR_ONLY)
def test_a_prime_or_modifier_letter_pairs_but_is_never_the_stray(mark: str) -> None:
    """``GPL-2.0'`` (a prime), ``ʻMIT`` (a letter, the okina) and ``MITʼ``
    are not a quote left over."""
    assert unquote(f"{mark}MIT{mark}") == Unquoted("MIT", True, "balanced")
    assert unquote(f"{mark}MIT") is None
    assert unquote(f"MIT{mark}") is None
    assert unquote(f"GPL-2.0{mark}") is None
    other = "'" if QUOTE_KIND[mark] == "double" else '"'
    assert unquote(f"{other}MIT{mark}") is None  # nor next to a mark of another kind
    assert unquote(f"{mark}MIT{other}") is None


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ('"MIT"', Unquoted("MIT", True, "balanced")),
        ('  "MIT"  ', Unquoted("MIT", True, "balanced")),
        ('"  MIT  "', Unquoted("MIT", True, "balanced")),
        ('"MIT ', Unquoted("MIT", False, "unbalanced, start")),
        (' MIT"', Unquoted("MIT", False, "unbalanced, end")),
        ('"\tMIT', Unquoted("MIT", False, "unbalanced, start")),
        ('""MIT""', Unquoted("MIT", True, "balanced, 2 layers")),
        ("\"'`MIT`'\"", Unquoted("MIT", True, "balanced, 3 layers")),
        ('""MIT"', Unquoted("MIT", False, "unbalanced, start")),
        ('"MIT""', Unquoted("MIT", False, "unbalanced, end")),
        ('"GPLv2 or later"', Unquoted("GPLv2 or later", True, "balanced")),
        ("'AMD's plpa'", Unquoted("AMD's plpa", True, "balanced")),
        ("’Don’t’", Unquoted("Don’t", True, "balanced")),
        ('"A B"', Unquoted("A B", True, "balanced")),
        (
            "'a'b'",
            Unquoted("a'b", True, "balanced"),
        ),  # the middle mark is an apostrophe
    ],
)
def test_the_shapes(text: str, expected: Unquoted) -> None:
    assert unquote(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        "",
        " ",
        "MIT",
        "MIT License",
        '""',
        '"',
        "'",
        '"""',
        '" "',
        '"  "',
        '""""',
        "\"MIT'",  # two kinds
        '"MIT" or "Apache-2.0"',  # first mark does not close the last
        'MIT "or" Apache-2.0',
        'Apache "2.0"',
        '"Apache" 2.0',
        '"MIT"x',
        'x"MIT"',
        '"MIT"."',
        '"a"b"',
        '"a"b"c"d"',
        '""MIT',  # one stray mark is taken off, not a run of them
        'MIT""',
        '"MIT"""',
        'MIT"s"',
        "\"'MIT",  # a mark inside the value, at its start
        "'\"MIT",
    ],
    ids=lambda text: ascii(text)[:30],
)
def test_nothing_to_take_off(text: str) -> None:
    assert unquote(text) is None


def test_an_apostrophe_between_letters_is_not_a_mark() -> None:
    assert unquote("'AMD's'") == Unquoted("AMD's", True, "balanced")
    assert unquote("'AMD's") == Unquoted("AMD's", False, "unbalanced, start")
    # not between two letters or digits
    assert unquote("'AMD 's'") is None
    assert unquote("'AMD' s'") is None
    # a double mark is never an apostrophe
    assert unquote('"AMD"s"') is None
    assert unquote("'A'") == Unquoted("A", True, "balanced")


def test_unquote_does_not_change_its_input_beyond_the_marks() -> None:
    assert unquote('"Apache  2.0"') == Unquoted("Apache  2.0", True, "balanced")


@pytest.mark.parametrize("size", [1_000, 500_000])
def test_a_long_run_is_linear(size: int) -> None:
    texts = [
        '"' * size + "MIT" + '"' * size,
        '"' * size + "MIT" + '"' * (size - 1),
        '"' * size,
        '" "' * size,
        "'" + "a'" * size + "'",
        '"' + 'a"' * size,
        " " * size + '"MIT"' + " " * size,
        '"' + " " * size + "MIT",
    ]
    start = time.monotonic()
    got = [unquote(text) for text in texts]
    assert time.monotonic() - start < 5
    assert got[0] == Unquoted("MIT", True, f"balanced, {size} layers")
    assert got[1] == Unquoted("MIT", False, "unbalanced, start")
    assert got[2:6] == [
        None,
        None,
        Unquoted("a'" * (size - 1) + "a", False, "unbalanced, end"),
        None,
    ]
    assert got[6] == Unquoted("MIT", True, "balanced")
    assert got[7] == Unquoted("MIT", False, "unbalanced, start")


def test_no_listed_id_or_name_starts_or_ends_with_a_mark() -> None:
    """Reading a quoted value would break the name of a licence that begins or
    ends with a mark. 3.29.0 has none; the names have marks only inside."""
    rows = list_rows(LICENSE_LIST, "licenses") + list_rows(EXCEPTION_LIST, "exceptions")
    names = [str(text) for row in rows for text in row[:2]]
    assert len(names) > 1_000
    assert [n for n in names if n[0] in QUOTE_KIND or n[-1] in QUOTE_KIND] == []
    with_marks = {n for n in names if any(c in QUOTE_KIND for c in n)}
    assert 'BSD 3-Clause "New" or "Revised" License' in with_marks
    assert "AMD's plpa_map.c License" in with_marks


def test_the_names_of_the_list_with_marks_are_not_changed() -> None:
    """A listed name is never a whole value in quotes: it has nothing to take
    off, with the apostrophes and double marks it holds."""
    rows = list_rows(LICENSE_LIST, "licenses") + list_rows(EXCEPTION_LIST, "exceptions")
    for row in rows:
        for text in map(str, row[:2]):
            assert unquote(text) is None, text
