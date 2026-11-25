# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The gap guard of the ``TEXTS`` search: a text whose span misses a run of
150 characters or more of it is not held whole, however close the rest.

The texts are made up. ``LONG`` is 400 numbered words of 4 characters (1,999
characters) with words of 5 at positions 10, 100 and 385: a run of 30
words is 149 characters, or 150 with one of them in it. Without 30 words it still
fits at 0.96, over MIN_SIMILARITY."""
# pylint: disable=missing-function-docstring

import pytest
from test_wholetexts import FILLER, corpus_of, fake

from licenseid import wholetexts
from licenseid.textcorpus import RunChars
from licenseid.textlocate import Alignment, Budget, align, longest_gap, span_fit
from licenseid.wholetexts import found_rows

LONG_WORDS = [f"w{i:04d}" if i in (10, 100, 385) else f"w{i:03d}" for i in range(400)]
LONG = " ".join(LONG_WORDS)
CORPUS = corpus_of({"T": LONG})


def _without(start: int, count: int) -> str:
    """``LONG`` without its words *start* to *start + count*."""
    return " ".join(LONG_WORDS[:start] + LONG_WORDS[start + count :])


@pytest.mark.parametrize(
    ("start", "count", "expected"),
    [(200, 30, ["T"]), (70, 30, ["T"]), (101, 30, ["T"]), (71, 30, None)]
    + [(100, 30, None), (85, 31, None)],
    ids=["149", "149-before", "149-after", "150-ending", "150-starting", "155"],
)
def test_a_run_of_150_characters_missing_is_no_hit(
    start: int, count: int, expected: list[str] | None
) -> None:
    # 30 words of 4 characters and 29 spaces: 149 characters; 150 with the
    # word of 5 (word 100) at either end of the run; 31 words holding it: 155.
    assert found_rows(_without(start, count), CORPUS, "Z") == expected


def test_spread_changes_are_no_gap() -> None:
    # 20 words changed, 20 apart: a fit of 0.96, as without a run of 30
    # words, but no run missing.
    words = ["zzzz" if i % 20 == 5 else word for i, word in enumerate(LONG_WORDS)]
    assert found_rows(" ".join(words), CORPUS, "Z") == ["T"]


@pytest.mark.parametrize(("count", "expected"), [(29, ["T"]), (30, None)])
def test_a_missing_end_is_a_gap(count: int, expected: list[str] | None) -> None:
    # 29 words: 145 characters; 30 holding word 385: 150.
    # The last words lost, then another text: nothing beside the span holds
    # them.
    assert found_rows(f"{_without(400 - count, count)} {FILLER}", CORPUS, "Z") == (
        expected
    )


def _repeated(text: str, where: str, count: int = 35) -> str:
    """*text* with ``LONG``'s last *count* words again after 50 other words,
    or its first *count* before them."""
    if where == "after":
        return f"{text} {fake(5, 50)} {' '.join(LONG_WORDS[-count:])}"
    return f"{' '.join(LONG_WORDS[:count])} {fake(5, 50)} {text}"


@pytest.mark.parametrize(("where", "count"), [("before", 35), ("before", 30)])
def test_an_end_matched_to_another_copy_is_looked_for_beside_the_span(
    where: str, count: int
) -> None:
    # The alignment ties the first words (175 or 150 characters) to the
    # other copy, and trimming drops that far block; looked for again beside
    # the span, they are there.
    assert found_rows(_repeated(LONG, where, count), CORPUS, "Z") == ["T"]


@pytest.mark.parametrize(
    ("start", "expected"), [(70, ["T"]), (71, None)], ids=["149", "150"]
)
def test_a_run_missing_after_the_second_look_is_still_a_gap(
    start: int, expected: list[str] | None
) -> None:
    text = _repeated(_without(start, 30), "after")
    assert found_rows(text, CORPUS, "Z") == expected


@pytest.mark.parametrize(
    "text",
    [
        f"{_without(369, 31)} {fake(5, 10)} w380 {fake(6, 10)} w395",
        f"w005 {fake(5, 10)} w020 {fake(6, 10)} {_without(0, 31)}",
    ],
    ids=["after", "before"],
)
def test_stray_words_trimmed_off_an_end_are_not_looked_for_again(
    text: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    # 31 words lost at an end; two of them stray beyond it: trimmed blocks
    # that matched 2 of the 31 words are no copy of that end.
    calls: list[str] = []

    def counted(text: str, window: str) -> Alignment | None:
        calls.append(text)
        return align(text, window)

    monkeypatch.setattr(wholetexts, "align", counted)
    assert found_rows(text, CORPUS, "Z") is None
    assert len(calls) == 1


def test_a_text_missing_a_clause_still_casts_doubt() -> None:
    # The input lacks 31 of T's words (155 characters): no hit, but it fits
    # at 0.960, key 1,689. S, the input with 13 words changed, fits at 0.972
    # (under SURE_SIMILARITY), key 1,740: T is about as close (0.90 of it).
    held = LONG_WORDS[:200] + LONG_WORDS[231:]
    changed = ["zzzz" if i % 30 == 7 else word for i, word in enumerate(held)]
    alone = corpus_of({"S": " ".join(changed)})
    assert found_rows(" ".join(held), alone, "Z") == ["S"]
    both = corpus_of({"T": LONG, "S": " ".join(changed)})
    assert found_rows(" ".join(held), both, "Z") is None


def test_the_gap_is_counted_in_characters_for_han_text() -> None:
    # One token per Han character: 149 missing characters are 149 tokens,
    # still under the guard; 150 are not.
    text = "".join(chr(0x4E00 + i) for i in range(1700))
    corpus = corpus_of({"H": text})
    assert found_rows(text[:800] + text[949:], corpus, "Z") == ["H"]
    assert found_rows(text[:800] + text[950:], corpus, "Z") is None


@pytest.mark.parametrize(
    "text",
    [
        "abcd efgh ijkl mnop qrs t",
        "abcd  efgh ijkl mnop qrs t ",
        "abcd efgh ijkl mnop qrs \u00e9",
    ],
)
@pytest.mark.parametrize(
    ("missing", "expected"),
    [((), 0), (((0, 1),), 4), (((1, 3), (4, 5)), 9), (((0, 1), (2, 4)), 9)]
    + [(((3, 5),), 8)],
)
def test_longest_gap(
    text: str, missing: tuple[tuple[int, int], ...], expected: int
) -> None:
    # From the start of a run's first token to the end of its last: the
    # same with one space between words (the fast path), with more, or in
    # text not ASCII (both by token position).
    assert longest_gap(RunChars(text), missing) == expected


def test_a_fit_is_cached_by_span_not_by_text() -> None:
    # The second look scores a text on a wider span than its first: a fit
    # kept for the first span must not answer for the second.
    # pylint: disable=protected-access
    source = wholetexts._read_input(LONG, CORPUS)
    assert source is not None
    budget = Budget()
    items = wholetexts._items(CORPUS, source, None, budget)
    search = wholetexts._Search(source, items, budget)
    item = items[0]
    narrow, wide = (0, 395), (0, 400)
    fits = [search._fit(item, span) for span in (narrow, wide, narrow)]
    expected = [
        span_fit(item.coded, source.span_text(*span), Budget())
        for span in (narrow, wide, narrow)
    ]
    assert fits == expected
    assert fits[0] != fits[1]
