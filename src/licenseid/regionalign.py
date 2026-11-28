# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Tier 2's character alignment of a fragment with a region of a licence
text (``licenseid.wordregion`` locates it), as it would be aligned with the
whole text: never a window the text does not offer, never an alignment score
above the whole text's. ``licenseid.similarity.fragment_similarity`` calls
it, with the whole text as the region when there is none.

RapidFuzz's alignment of a fragment (``partial_ratio_alignment``) slides it
over the text and also scores windows trimmed at the text's two ends. Given
a region alone, it takes the region's cut ends for the text's ends: it
scores trimmed windows the text does not offer, which can win, and which
cost time in the cube of the fragment's characters when the fit is poor. So
where a region cuts the text, a wall stands for the rest of the text: a run
of a character the fragment lacks, as long as the fragment. A window may
run into it, as into the text, but matches nothing there.

A window that runs into a wall says the characters align past where the
words located them (a distorted copy has other tokens): the region grows on
that side and is aligned again (:func:`aligned`).

RapidFuzz only, and the tokens of ``licenseid.textgrams``.
"""

from typing import Final, cast

from rapidfuzz import fuzz
from rapidfuzz.distance import LCSseq, ScoreAlignment

from licenseid.textgrams import whole_tokens

#: How often a region grows on the side its window ran into, each time by
#: the fragment's length, before the whole text is aligned.
GROWTHS: Final = 2

#: The least alignment score whose window Tier 2 scores again by sorted
#: words; under it the alignment score is the similarity.
WINDOW_SCORE: Final = 0.6

Span = tuple[int, int]
Aligned = tuple[float, Span]


def walled(norm_input: str, wall: str, text: str, region: Span) -> Aligned:
    """The alignment score (0 to 1) of *norm_input* with the *region* of
    *text*, walls of *wall* (a character *norm_input* lacks) at its cut
    ends, and the window of *text* it aligned with, as it sits in the text
    (past a cut end too). The whole text has no wall: its alignment is
    RapidFuzz's."""
    start, end = region
    if 0 < start and end < len(text) and end - start <= len(norm_input):
        return held_whole(norm_input, text, region)
    walls = wall * len(norm_input)
    before = walls if start > 0 else ""
    haystack = before + text[start:end] + (walls if end < len(text) else "")
    # None only under a score_cutoff, which is not given.
    alignment = cast(ScoreAlignment, fuzz.partial_ratio_alignment(norm_input, haystack))
    offset = start - len(before)
    window_end = min(len(text), alignment.dest_end + offset)
    window = (max(0, alignment.dest_start + offset), window_end)
    return alignment.score / 100.0, window


def held_whole(norm_input: str, text: str, region: Span) -> Aligned:
    """:func:`walled` of a region cut at both ends and no longer than
    *norm_input* (which holds more: a blob, other words), without the scan.
    A window of the input's length that holds the region whole matches all
    any window can, so the best score is the longest common subsequence of
    the two over the input's length; its window is the region widened to
    the input's length, centred, within the text."""
    start, end = region
    fast_score = LCSseq.similarity(norm_input, text[start:end]) / len(norm_input)
    window_start = max(0, start - (len(norm_input) - (end - start)) // 2)
    window_end = min(len(text), window_start + len(norm_input))
    return fast_score, (max(0, window_end - len(norm_input)), window_end)


def aligned(norm_input: str, wall: str, text: str, region: Span) -> Aligned:
    """:func:`walled` of *region*, grown on the side where its window runs
    into a wall, by the input's length, at most GROWTHS times; then of the
    whole text. A region no longer than the input does not grow: the input
    holds more than it, and any window runs into a wall."""
    for _ in range(GROWTHS + 1):
        fast_score, window = walled(norm_input, wall, text, region)
        start, end = region
        before, after = window[0] < start, window[1] > end
        if end - start <= len(norm_input) or not (before or after):
            return fast_score, window
        size = len(norm_input)
        region = whole_tokens(
            text,
            max(0, start - size) if before else start,
            min(len(text), end + size) if after else end,
        )
    return walled(norm_input, wall, text, (0, len(text)))
