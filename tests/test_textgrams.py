# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Tokens, word 3-grams, their stable hashes and the score rule of
``licenseid.textgrams``."""
# pylint: disable=missing-function-docstring

import hashlib
import struct

import pytest

from licenseid import textgrams
from licenseid.textgrams import (
    GramScore,
    GramTable,
    gram_hash,
    gram_strings,
    input_grams,
    ranked,
    score_rows,
    split_words,
)


@pytest.mark.parametrize(
    ("text", "tokens"),
    [
        ("permission is hereby granted", ["permission", "is", "hereby", "granted"]),
        ("a\tb\n c  d", ["a", "b", "c", "d"]),
        ("許諾書", ["許", "諾", "書"]),
        ("ライセンス", ["ラ", "イ", "セ", "ン", "ス"]),
        ("ひらがな", ["ひ", "ら", "が", "な"]),
        (
            "本ソフトウェアMIT license",
            ["本", "ソ", "フ", "ト", "ウ", "ェ", "ア", "MIT", "license"],
        ),
        ("café 許可 ok", ["café", "許", "可", "ok"]),
        ("\uf900\ufaff", ["\uf900", "\ufaff"]),  # compatibility ideographs
        ("ｶﾅ", ["ｶﾅ"]),  # half-width kana: outside the ranges, one word
        ("", []),
        ("   ", []),
    ],
    ids=[
        "ascii",
        "white-space",
        "han",
        "katakana",
        "hiragana",
        "mixed",
        "latin-and-han",
        "compatibility",
        "half-width",
        "empty",
        "spaces",
    ],
)
def test_tokens(text: str, tokens: list[str]) -> None:
    assert split_words(text) == tokens


@pytest.mark.parametrize(
    ("text", "grams"),
    [
        ("", []),
        ("one", []),
        ("one two", []),
        ("one two three", ["one two three"]),
        ("a b c d", ["a b c", "b c d"]),
        ("a b c a b c", ["a b c", "b c a", "c a b", "a b c"]),  # repeats kept
        ("許諾書", ["許 諾 書"]),
    ],
    ids=["empty", "one-word", "two-words", "three", "four", "repeats", "han"],
)
def test_grams(text: str, grams: list[str]) -> None:
    assert gram_strings(split_words(text)) == grams


@pytest.mark.parametrize(
    ("gram", "value"),
    [
        ("permission is hereby", -3386301251751753373),
        ("許 諾 書", 8178322529682305809),
    ],
)
def test_the_hash_of_a_gram_is_stable(gram: str, value: int) -> None:
    """Literal values: a change of hash changes every stored posting."""
    assert gram_hash(gram) == value
    digest = hashlib.blake2b(gram.encode(), digest_size=8).digest()
    assert struct.unpack("<q", digest)[0] == value  # signed, little-endian


def test_a_lone_surrogate_is_hashed_not_refused() -> None:
    assert gram_hash("a \ud800 b") != gram_hash("a b c")


def test_input_grams_are_distinct_in_first_order() -> None:
    expected = [gram_hash(g) for g in ("a b c", "b c a", "c a b")]
    assert input_grams("a b c a b c") == expected
    assert not input_grams("one two")


@pytest.mark.parametrize("size", [1, 3, 7])
@pytest.mark.parametrize("limit", [0, 1, 2, 5, 9, 1000])
@pytest.mark.parametrize(
    "text",
    [
        "a b c a b c a b c d e f g h",
        "ab" * 11 + " cd ef gh ij kl",  # a run longer than a piece
        "許可 \u3000 ライセンス ok café\u00a0x y z",
        "本ソフトウェアはMITlicenseです 本ソフトウェア x1 x2 x3",
        "\n\t a  b\u2003c\u200bd e f g",
    ],
)
def test_a_limit_reads_the_first_grams_of_the_whole_input(
    text: str, limit: int, size: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Read a piece at a time (here of 1, 3 or 7 characters, cut where no
    token runs across), an input gives the first ``limit + 1`` grams it gives
    whole."""
    monkeypatch.setattr(textgrams, "CHUNK_CHARS", size)
    assert input_grams(text, limit) == input_grams(text)[: limit + 1]


def test_the_score_is_shared_over_the_smaller_side() -> None:
    """Text 0 holds 2 of 4 input grams and has 10: 2 / 4. Text 2 holds 3
    and has 3: 3 / 3. Text 1 shares none and has no row."""
    rows = score_rows({2: 3, 0: 2}, 4, ("A", "B", "C"), (10, 5, 3))
    assert rows == (GramScore("A", 2, 10, 0.5), GramScore("C", 3, 3, 1.0))


def test_equal_scores_keep_row_order() -> None:
    """Rows 0, 1 and 3 score 0.5, in that order (not the order of their
    IDs), whatever order the counts come in; row 2 scores 1.0 and comes
    first."""
    shared = {3: 1, 1: 1, 2: 2, 0: 1}
    rows = score_rows(shared, 2, ("D", "B", "C", "A"), (2, 4, 2, 2))
    assert [row.license_id for row in ranked(rows)] == ["C", "D", "B", "A"]
    assert [row.score for row in ranked(rows)] == [1.0, 0.5, 0.5, 0.5]


@pytest.mark.parametrize(("grams", "total", "bounded"), [(3, 3, False), (2, 3, True)])
def test_a_table_says_whether_a_bound_cut_the_grams(
    grams: int, total: int, bounded: bool
) -> None:
    assert GramTable((), grams, total).bounded is bounded
