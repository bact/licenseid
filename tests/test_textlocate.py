# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""``textlocate``: index, votes, windows, alignment, character check and
limits, on word codes written by hand (one letter per word)."""
# pylint: disable=missing-function-docstring

import pytest

from licenseid import textlocate
from licenseid.textcorpus import CodedText, critical_counts
from licenseid.textlocate import (
    MIN_SIMILARITY,
    NEAR_SIMILARITY,
    SURE_SIMILARITY,
    Alignment,
    Budget,
    Fit,
    LimitReached,
    Window,
    align,
    build_index,
    same_critical,
    sample_share,
    span_fit,
    windows,
)

# A "text" of 60 word codes, all distinct, and fillers none of it holds.
_TEXT = "".join(chr(0x4E00 + i) for i in range(60))
_FILLER = "".join(chr(0x3041 + i) for i in range(80))


def _coded(text: str) -> CodedText:
    return CodedText("A", False, text, text, critical_counts(text.split()))


def test_index_lists_every_start() -> None:
    index = build_index("abcdeabcde")
    assert index["abcde"] == [0, 5]
    assert index["bcdea"] == [1]
    assert len(index) == 5


def test_index_of_a_short_input_is_empty() -> None:
    assert not build_index("abcd")


@pytest.mark.parametrize(
    ("codes", "share"),
    [(_TEXT, 1.0), (_FILLER[30:], 0.0), ("abcd", 0.0)],
    ids=["present", "absent", "short"],
)
def test_sample_share(codes: str, share: float) -> None:
    assert sample_share(codes, build_index(_FILLER[:30] + _TEXT)) == share


def test_sample_share_counts_the_part_present() -> None:
    index = build_index(_TEXT[:28])
    assert 0.3 < sample_share(_TEXT, index) < 0.5


def test_one_window_per_copy() -> None:
    source = _FILLER[:30] + _TEXT + _FILLER[30:50] + _TEXT
    found = windows(_TEXT, build_index(source), len(source), Budget())
    assert sorted((w.start, w.end) for w in found) == [(30, 90), (110, 170)]
    first = min(found, key=lambda w: w.start)
    assert (first.pad_start, first.pad_end) == (20, 100)


def test_the_window_stays_inside_the_input() -> None:
    found = windows(_TEXT, build_index(_TEXT), 60, Budget())
    assert found == [Window(0, 60, 0, 60)]


def test_no_window_under_the_vote_share() -> None:
    source = _TEXT[:15] + _FILLER
    assert not windows(_TEXT, build_index(source), len(source), Budget())


def test_a_window_for_a_word_changed_every_eight() -> None:
    # 21 of 56 anchors are left (0.375): over the share of 0.30.
    source = "".join("x" if i % 8 == 7 else code for i, code in enumerate(_TEXT))
    found = windows(_TEXT, build_index(source), len(source), Budget())
    assert [(w.start, w.end) for w in found] == [(0, 60)]


def test_align_trims_the_padding() -> None:
    window = _FILLER[:10] + _TEXT + _FILLER[10:20]
    assert align(_TEXT, window) == Alignment(10, 70, ())


def test_align_keeps_a_changed_word_inside() -> None:
    changed = _TEXT[:30] + "x" + _TEXT[31:]
    assert align(_TEXT, _FILLER[:10] + changed + _FILLER[10:20]) == Alignment(
        10, 70, ((30, 31),)
    )


def test_align_drops_a_stray_match_at_the_edge() -> None:
    window = _TEXT[59] + _FILLER[:20] + _TEXT + _FILLER[20:25]
    assert align(_TEXT, window) == Alignment(21, 81, ())


def test_align_trims_a_block_far_from_the_rest() -> None:
    # The first word 20 words before the others: dropping it raises the
    # ratio from 120 / 140 to 118 / 119.
    window = _TEXT[0] + _FILLER[:20] + _TEXT[1:]
    assert align(_TEXT, window) == Alignment(21, 80, ((0, 1),), (1, 0))


def test_align_refuses_words_spread_thin() -> None:
    # Every word there (LCS 60), one filler word after each: 120 / 179.
    window = "".join(code + filler for code, filler in zip(_TEXT, _FILLER))
    assert align(_TEXT, window) is None


@pytest.mark.parametrize(
    ("present", "expected"),
    [
        (54, Alignment(0, 54, ((54, 60),))),
        (40, Alignment(0, 40, ((40, 60),))),
        (39, None),
    ],
)
def test_align_word_gate(present: int, expected: Alignment | None) -> None:
    assert align(_TEXT, _TEXT[:present] + _FILLER[:6]) == expected


def _boundary_text() -> str:
    words = [f"q{i:03d}" for i in range(60)]
    text = " ".join(words[:30] + ["x" * 32, "y" * 34, "z" * 32] + words[30:])
    assert len(text) == 400
    return text


def _fit_of(text: str, span: str) -> Fit | None:
    return span_fit(_coded(text), span, Budget())


@pytest.mark.parametrize(
    ("changed", "key", "hit"),
    [(0, 400, True), (20, 360, True), (21, 358, False), (28, 344, False)],
)
def test_span_fit_threshold(changed: int, key: int, hit: bool) -> None:
    # Each "#" costs 2 of the 800 characters: 95 % allows 20, 93 % 28.
    text = _boundary_text()
    start = text.index("y")
    span = text[:start] + "#" * changed + text[start + changed :]
    fit = _fit_of(text, span)
    assert fit is not None
    assert (fit.key, fit.reaches(MIN_SIMILARITY)) == (key, hit)


def test_span_fit_is_none_under_the_look_alike_floor() -> None:
    text = _boundary_text()
    start = text.index("y")
    assert _fit_of(text, text[:start] + "#" * 29 + text[start + 29 :]) is None


@pytest.mark.parametrize(
    ("kept", "key", "hit"),
    [(("x" * 14, "y" * 14), 324, True), (("x" * 13, "y" * 14), 322, False)],
)
def test_span_fit_threshold_on_deletions(
    kept: tuple[str, str], key: int, hit: bool
) -> None:
    # 38 characters deleted: 762 in all, 38 within 5 %; 39 of 761 is not.
    text = _boundary_text()
    span = text.replace("x" * 32 + " " + "y" * 34, " ".join(kept))
    fit = _fit_of(text, span)
    assert fit is not None
    assert (fit.key, fit.reaches(MIN_SIMILARITY)) == (key, hit)


def test_span_fit_counts_a_longer_span_as_found_less_missing() -> None:
    text = _boundary_text()
    # 404 characters, distance 4: 400 found, 4 extra.
    assert _fit_of(text, text + " abc") == Fit(key=400, distance=4, total=804)


@pytest.mark.parametrize(
    ("similarity", "distance", "reaches"),
    [
        (NEAR_SIMILARITY, 56, True),
        (NEAR_SIMILARITY, 57, False),
        (MIN_SIMILARITY, 40, True),
        (MIN_SIMILARITY, 41, False),
        (SURE_SIMILARITY, 16, True),
        (SURE_SIMILARITY, 17, False),
    ],
)
def test_fit_reaches_in_whole_numbers(
    similarity: float, distance: int, reaches: bool
) -> None:
    # 800 characters: 7 % is 56, 5 % is 40, 2 % is 16.
    assert Fit(key=0, distance=distance, total=800).reaches(similarity) is reaches


def test_similarity_levels_are_the_documented_ones() -> None:
    assert (NEAR_SIMILARITY, MIN_SIMILARITY, SURE_SIMILARITY) == (0.93, 0.95, 0.98)


@pytest.mark.parametrize(
    "span_words",
    [["do", "copy"], ["do", "not", "not", "copy"], ["do", "unless", "copy"]],
)
def test_same_critical_wants_each_word_as_often(span_words: list[str]) -> None:
    text = " ".join(["do", "not", "copy"] * 20)
    coded = CodedText("A", False, text, "", critical_counts(text.split()))
    assert not same_critical(coded, span_words * 20)
    assert same_critical(coded, text.split())


def test_span_fit_leaves_the_critical_words_to_same_critical() -> None:
    # One "not" of 20 dropped: 4 of 239 characters, a fit all the same.
    text = " ".join(["do", "not", "copy"] * 20)
    coded = CodedText("A", False, text, "", critical_counts(text.split()))
    span = text.replace(" not", "", 1)
    assert span_fit(coded, span, Budget()) == Fit(key=231, distance=4, total=474)
    assert not same_critical(coded, span.split())


def test_same_critical_counts_neither_as_not() -> None:
    held = [f"q{i:03d}" for i in range(50)]
    text = " ".join([*held, "neither", "a", "nor", "b", "may", "be", "used"])
    coded = CodedText("A", False, text, "", critical_counts(text.split()))
    words = [*held, "a", "and", "b", "may", "not", "be", "used"]
    assert same_critical(coded, words)


@pytest.mark.parametrize(
    ("limit", "charge"),
    [
        ("MAX_VOTES", Budget.charge_votes),
        ("MAX_WINDOWS", Budget.charge_windows),
        ("MAX_WORD_CELLS", Budget.charge_word_cells),
        ("MAX_CHAR_CELLS", Budget.charge_char_cells),
    ],
)
def test_budget_allows_the_limit_and_not_one_more(
    monkeypatch: pytest.MonkeyPatch, limit: str, charge: object
) -> None:
    monkeypatch.setattr(textlocate, limit, 10)
    budget = Budget()
    charge(budget, 4)  # type: ignore[operator]
    charge(budget, 6)  # type: ignore[operator]
    with pytest.raises(LimitReached):
        charge(budget, 1)  # type: ignore[operator]


def test_windows_charge_their_votes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(textlocate, "MAX_VOTES", 10)
    with pytest.raises(LimitReached):
        windows(_TEXT, build_index(_TEXT), 60, Budget())


def test_windows_charge_their_count(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(textlocate, "MAX_WINDOWS", 1)
    source = _TEXT + _FILLER[:20] + _TEXT
    with pytest.raises(LimitReached):
        windows(_TEXT, build_index(source), len(source), Budget())
