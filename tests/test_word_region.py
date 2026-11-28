# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Where Tier 2 aligns a fragment, located by word codes first
(``licenseid.wordregion``), how the characters are aligned there
(``licenseid.regionalign``), and the window ``--diff`` widens to whole words
(``textgrams.whole_tokens``): rules on made-up texts. Through ``detect()``:
``test_word_region_detect``."""
# pylint: disable=missing-function-docstring

import random
from collections import Counter
from unittest import mock

import pytest
from rapidfuzz import fuzz

from licenseid import regionalign, similarity, wordregion
from licenseid.textcorpus import TextCorpus, TextRow
from licenseid.textgrams import split_words, whole_tokens
from licenseid.types import CandidateMatch
from licenseid.wordregion import WordRegions, best_possible, located

# A text of 100 distinct five-letter words, unlike in their characters too.
_RANDOM = random.Random(7)
WORDS = [
    "".join(_RANDOM.choices("abcdefghijklmnopqrstuvwxyz", k=5)) for _ in range(100)
]
TEXT = " ".join(WORDS)


def corpus_of(text: str) -> TextCorpus:
    return TextCorpus.build([TextRow("T-1.0", text, None, ("T-1.0",))])


CORPUS = corpus_of(TEXT)


def words(start: int, end: int) -> str:
    return " ".join(WORDS[start:end])


def chars(start: int, end: int) -> tuple[int, int]:
    """Where words *start* to *end* are in TEXT."""
    first = len(words(0, start)) + (1 if start else 0)
    return first, first + len(words(start, end))


def region_of(norm_input: str, text: str = TEXT) -> str | None:
    """The region of *text* (in the corpus as ``T-1.0``) that *norm_input*
    is aligned with, or None."""
    corpus = corpus_of(text)
    span = WordRegions(norm_input, lambda: corpus).region("T-1.0", text)
    return None if span is None else text[span[0] : span[1]]


def test_the_made_up_words_are_distinct() -> None:
    assert len(set(WORDS)) == 100


@pytest.mark.parametrize(
    ("norm_input", "region"),
    [
        (words(0, 12), words(0, 16)),  # at the start: no padding before
        (words(40, 60), words(36, 64)),  # in the middle: 4 words each side
        (words(90, 100), words(86, 100)),  # at the end
        (words(50, 51), words(46, 55)),  # one word
        # One word changed in every five: still located, at the same place.
        (
            " ".join("x" if i % 5 == 2 else WORDS[i] for i in range(40, 60)),
            words(36, 64),
        ),
        # RapidFuzz trims its window at an end of the text (words 0 to 10
        # for an input of 16): the region holds 16 words, then the padding.
        (" ".join([*(f"z{i}" for i in range(6)), *WORDS[:10]]), words(0, 20)),
        (" ".join([*WORDS[90:], *(f"z{i}" for i in range(6))]), words(80, 100)),
    ],
    ids=[
        "start",
        "middle",
        "end",
        "one-word",
        "one-in-five-changed",
        "trimmed-at-start",
        "trimmed-at-end",
    ],
)
def test_a_fragment_is_located_and_padded_by_4_words(
    norm_input: str, region: str
) -> None:
    assert region_of(norm_input) == region


def test_a_fragment_twice_in_the_text_takes_the_first() -> None:
    text = " ".join([*WORDS[:50], *WORDS[10:20], *WORDS[50:]])  # words 10-19 twice
    assert region_of(words(10, 20), text) == words(6, 24)


@pytest.mark.parametrize(
    "norm_input",
    [
        "",
        " ".join(reversed(WORDS[30:60])),  # every word, in reverse order
        " ".join(WORDS[30:60:2] + WORDS[31:60:2]),  # scattered over the text
        " ".join(f"other{i}" for i in range(20)),  # no word of the text
        words(10, 20) + " " + words(10, 20),  # the fragment twice: 50
        " ".join([WORDS[10], WORDS[11]] * 20),  # one phrase, repeated
    ],
    ids=["empty", "reversed", "scattered", "unknown-words", "twice", "repeated"],
)
def test_a_weak_word_alignment_locates_nothing(norm_input: str) -> None:
    assert region_of(norm_input) is None


def _matching(count: int) -> tuple[str, str]:
    """An input of 100 words and a text whose best window of 100 words holds
    *count* of them in order: a word alignment of *count* exactly."""
    query = [f"q{i:03d}" for i in range(100)]
    window = [query[i] if i < count else f"y{i:03d}" for i in range(100)]
    outside = [f"x{i:03d}" for i in range(100)]
    return " ".join(query), " ".join([*outside[:50], *window, *outside[50:]])


@pytest.mark.parametrize(("count", "found"), [(59, False), (60, True), (61, True)])
def test_a_word_alignment_of_60_is_accepted_and_59_is_not(
    count: int, found: bool
) -> None:
    norm_input, text = _matching(count)
    assert fuzz.partial_ratio(norm_input.split(), text.split()) == pytest.approx(count)
    # The window starts one word early (x049 ties with the first match).
    expected = " ".join(text.split()[45:153]) if found else None
    assert region_of(norm_input, text) == expected


# -- best_possible: an alignment that cannot reach 60 is not made ------------


@pytest.mark.parametrize("seed", range(40))
def test_no_alignment_scores_over_its_bound(seed: int) -> None:
    rng = random.Random(seed)
    alphabet = "abcdefghij"[: rng.randint(2, 10)]
    first, second = (
        "".join(rng.choices(alphabet, k=rng.randint(1, 150))) for _ in range(2)
    )
    alignment = fuzz.partial_ratio_alignment(first, second)
    assert alignment is not None
    assert alignment.score <= best_possible(Counter(first), len(first), second) + 1e-9


@pytest.mark.parametrize(
    ("text_codes", "bound"),
    [("abcHIJKLMN", 60.0), ("abHIJKLMN", 400 / 9), ("HIJ", 0.0), ("abcdefg", 100.0)],
    ids=["shares-3-of-7", "shares-2-of-7", "shares-none", "equal"],
)
def test_the_bound_counts_the_shared_codes(text_codes: str, bound: float) -> None:
    """2 x shared / (shorter + shared): 3 of 7 codes shared reach 60."""
    assert best_possible(Counter("abcdefg"), 7, text_codes) == pytest.approx(bound)


@pytest.mark.parametrize(
    ("text_codes", "aligned"),
    [("abcHIJKLMN", True), ("abHIJKLMN", False), ("", False)],
    ids=["bound-60", "bound-44", "empty"],
)
def test_an_alignment_under_60_by_its_bound_is_not_made(
    text_codes: str, aligned: bool
) -> None:
    text = " ".join(text_codes)
    real = fuzz.partial_ratio_alignment
    alignment = mock.create_autospec(real, side_effect=real)
    with mock.patch.object(fuzz, "partial_ratio_alignment", alignment):
        found = located("abcdefg", text_codes, text)
    assert alignment.called is aligned
    # The bound is reached: "abc" at the text's start (a window trimmed to 3
    # codes) scores 2 x 3 / (7 + 3) = 60.
    assert (found is not None) is aligned


def test_the_counts_given_are_used() -> None:
    """WordRegions counts the input once and passes the counts."""
    assert located("abc", "abc", "a b c", Counter()) is None
    assert located("abc", "abc", "a b c") == (0, 5)


# Japanese: each Han or kana character is a token, so the padding is 4
# characters; a copy wrapped at another width is located alike.
HAN = "第一条本契約は甲及び乙の間で締結される著作物の利用許諾に関する条件を定める"


@pytest.mark.parametrize(
    "norm_input",
    [HAN[10:20], " ".join(HAN[10:20]), HAN[10:15] + " " + HAN[15:20]],
    ids=["as-is", "every-character", "wrapped"],
)
def test_han_and_kana_are_padded_by_4_characters(norm_input: str) -> None:
    assert region_of(norm_input, HAN) == HAN[6:24]


def test_a_region_ends_on_tokens_of_any_script() -> None:
    """Astral characters, combining marks and a word of several scripts are
    never cut: a region starts and ends where a token does."""
    tokens = ["ño", "\U0001f600x", "ab\U00020000", *WORDS[:20], "é", "z"]
    text = " ".join(tokens)
    assert region_of(words(2, 12), text) == " ".join(tokens[1:19])


# -- WordRegions: the candidate's own codes, coded once ------------------------


def test_no_codes_no_region() -> None:
    regions = WordRegions(words(40, 60), lambda: CORPUS)
    assert regions.region("T-1.0", TEXT) == located(
        CORPUS.encode(WORDS[40:60]), CORPUS.entries[0].text.codes, TEXT
    )
    assert regions.region("Other-1.0", TEXT) is None  # no text in the corpus
    assert regions.region("T-1.0", TEXT + " more") is None  # another text


def test_the_input_is_coded_once_and_only_when_asked() -> None:
    corpus = mock.Mock(return_value=CORPUS)
    with mock.patch.object(
        wordregion, "split_words", autospec=True, wraps=split_words
    ) as split:
        regions = WordRegions(words(40, 60), corpus)
        corpus.assert_not_called()
        for _ in range(3):
            regions.region("T-1.0", TEXT)
            regions.region("Other-1.0", TEXT)
    corpus.assert_called_once_with()
    split.assert_called_once_with(words(40, 60))


# -- The characters on the region (regionalign) --------------------------------

CANDIDATE: CandidateMatch = {"license_id": "T-1.0", "search_text": TEXT}


class Fixed:  # pylint: disable=too-few-public-methods
    """Regions that give one span for every candidate."""

    def __init__(self, span: tuple[int, int] | None) -> None:
        self.span = span

    def region(self, license_id: str, text: str) -> tuple[int, int] | None:
        del license_id, text
        return self.span


def aligned_lengths(
    norm_input: str, span: tuple[int, int] | None, text: str = TEXT
) -> tuple[list[int], float, str]:
    """The lengths of the texts the alignment was given for *norm_input* in
    the region *span* of *text*, and the similarity and window found."""
    query = similarity.query_of(norm_input, Fixed(span))
    real = fuzz.partial_ratio_alignment
    spy = mock.create_autospec(real, side_effect=real)
    with mock.patch.object(fuzz, "partial_ratio_alignment", spy):
        score, window = similarity.fragment_similarity(query, "T-1.0", text)
    return [len(call.args[1]) for call in spy.call_args_list], score, window


def test_the_alignment_is_given_the_region_between_two_walls() -> None:
    norm_input = words(40, 60)
    span = WordRegions(norm_input, lambda: CORPUS).region("T-1.0", TEXT)
    assert span == (chars(36, 64)[0], chars(36, 64)[1])
    lengths, score, window = aligned_lengths(norm_input, span)
    assert lengths == [len(words(36, 64)) + 2 * len(norm_input)]
    assert (score, window) == (1.0, norm_input)
    # The whole text: one alignment of it, the same answer.
    assert aligned_lengths(norm_input, None) == ([len(TEXT)], 1.0, norm_input)


def test_a_region_at_an_end_of_the_text_has_one_wall() -> None:
    norm_input = words(0, 20)
    lengths, score, window = aligned_lengths(norm_input, (0, chars(0, 24)[1]))
    assert lengths == [len(words(0, 24)) + len(norm_input)]
    assert (score, window) == (1.0, norm_input)


@pytest.mark.parametrize(
    "region", [(30, 52), (48, 70)], ids=["runs-into-right", "runs-into-left"]
)
def test_a_window_that_runs_into_a_wall_grows_the_region(
    region: tuple[int, int],
) -> None:
    """The words located the input a few words off (a distorted copy): the
    window runs into the wall, and the region grows by the input's length
    on that side; there the input aligns whole."""
    norm_input = words(40, 60)
    span = (chars(*region)[0], chars(*region)[1])
    lengths, score, window = aligned_lengths(norm_input, span)
    # Grown once, not yet the whole text (100 words, no wall).
    assert len(lengths) == 2
    assert lengths[0] < lengths[1] < len(TEXT)
    assert (score, window) == (1.0, norm_input)


def test_a_region_grows_twice_then_the_whole_text_is_aligned(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    norm_input = words(40, 60)
    span = (chars(30, 52)[0], chars(30, 52)[1])
    monkeypatch.setattr(regionalign, "GROWTHS", 0)
    lengths, score, window = aligned_lengths(norm_input, span)
    assert lengths == [len(words(30, 52)) + 2 * len(norm_input), len(TEXT)]
    assert (score, window) == (1.0, norm_input)
    monkeypatch.setattr(regionalign, "GROWTHS", 2)
    walled = len(words(30, 52)) + 2 * len(norm_input)
    assert aligned_lengths(norm_input, span)[0][0] == walled


def test_a_region_no_longer_than_the_input_is_held_whole_without_a_scan() -> None:
    """An input that holds more than the region (here a blob after the
    fragment): no alignment, the region's common characters over the
    input's length; the window is the region widened to the input."""
    norm_input = words(40, 60) + " " + "z" * 20
    span = (chars(40, 60)[0], chars(40, 60)[1])
    lengths, score, window = aligned_lengths(norm_input, span)
    assert lengths == []
    assert window == TEXT[span[0] - 10 : span[1] + 11]
    assert score == fuzz.token_sort_ratio(norm_input, window) / 100.0
    fast = regionalign.walled(norm_input, "\0", TEXT, span)[0]
    assert fast == len(words(40, 60)) / len(norm_input)


@pytest.mark.parametrize("seed", range(40))
def test_held_whole_is_the_walled_alignment(seed: int) -> None:
    rnd = random.Random(seed)
    text = " ".join(rnd.choices(WORDS[:12], k=rnd.randint(20, 60)))
    norm_input = " ".join(rnd.choices([*WORDS[:12], "zz"], k=rnd.randint(8, 30)))
    start = rnd.randint(1, len(text) // 2)
    end = min(len(text) - 1, start + rnd.randint(1, len(norm_input)))
    wall = "\0" * len(norm_input)
    scan = fuzz.partial_ratio_alignment(norm_input, wall + text[start:end] + wall)
    assert scan is not None
    found = regionalign.held_whole(norm_input, text, (start, end))[0]
    assert found == pytest.approx(scan.score / 100.0)


@pytest.mark.parametrize("seed", range(40))
def test_a_region_never_aligns_higher_than_the_whole_text(seed: int) -> None:
    rnd = random.Random(seed)
    norm_input = " ".join(rnd.choices([*WORDS[:30], "zz"], k=rnd.randint(5, 25)))
    start = rnd.randint(0, len(TEXT) - 2)
    end = rnd.randint(start + 1, len(TEXT))
    region = regionalign.walled(norm_input, "\0", TEXT, (start, end))[0]
    assert region <= fuzz.partial_ratio(norm_input, TEXT) / 100.0 + 1e-9


def test_a_poor_alignment_keeps_its_score_and_the_whole_text() -> None:
    norm_input = " ".join(["qqqq"] * 20)
    lengths, score, window = aligned_lengths(norm_input, (0, 200))
    assert lengths == [200 + len(norm_input)]
    assert score < 0.6
    assert window == TEXT


def test_the_wall_is_a_character_the_input_lacks() -> None:
    assert similarity.query_of("abc").wall == "\0"
    assert similarity.query_of("a\0b\x01").wall == "\x02"


def test_the_exact_text_asks_no_region() -> None:
    regions = mock.Mock(spec=["region"])
    query = similarity.query_of(TEXT, regions)
    assert similarity.calculate_base_similarity(query, CANDIDATE)[0] == 1.0
    regions.region.assert_not_called()


# -- whole_tokens: --diff's window -------------------------------------------


@pytest.mark.parametrize(
    ("text", "start", "end", "expected"),
    [
        ("alpha beta gamma", 2, 13, "alpha beta gamma"),  # both ends inside
        ("alpha beta gamma", 6, 10, "beta"),  # already on a token
        ("alpha beta gamma", 5, 11, " beta "),  # on white space: kept
        ("alpha beta gamma", 0, 16, "alpha beta gamma"),
        ("alpha", 0, 0, ""),
        ("著作権者abc", 1, 5, "作権者abc"),  # a Han character is a token
        ("著作権者abc", 0, 6, "著作権者abc"),
        ("x \U0001f600\U0001f601y z", 3, 4, "\U0001f600\U0001f601y"),
    ],
)
def test_a_window_is_widened_to_whole_tokens(
    text: str, start: int, end: int, expected: str
) -> None:
    first, last = whole_tokens(text, start, end)
    assert text[first:last] == expected


def test_diff_windows_are_snapped_and_scores_are_not() -> None:
    """--diff widens the window it shows; the similarity is the window's as
    aligned (the sorted words of a cut window)."""
    norm_input = words(40, 60)[3:-3]  # cut inside its first and last words
    plain = similarity.query_of(norm_input)
    snapped = similarity.query_of(norm_input, snap=True)
    score, window = similarity.fragment_similarity(plain, "T-1.0", TEXT)
    assert window == norm_input
    assert similarity.fragment_similarity(snapped, "T-1.0", TEXT) == (
        score,
        words(40, 60),
    )
