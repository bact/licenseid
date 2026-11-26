# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The fit of a List text in its span with the template's variable parts
left out (SPDX matching guidelines B.3.3, "Replaceable text").

A copy of BSD-3-Clause names its own copyright holder in the copyright line
and in both disclaimers; compared character by character it loses 2 to 5
points on words the guidelines let vary, then sits under the hit's 0.98 where
a near twin (BSD-3-Clause-HP, whose fixed text says "the author") doubts it
(``licenseid.wholetexts``). Here each variable part of the text
(``licenseid.templatevars``) and its fill in the span (the span's tokens
between the matched tokens around it, read off the alignment's blocks) are
left out of both sides, and the rest is compared as ``textlocate.span_fit``
compares the whole:

* a fill counts only when its var's pattern accepts it whole
  (``templatevars.fill_matches``) and it is at most FILL_SLACK characters
  longer than the List's words of the var, else the var's words stay in, as
  today: a var takes no clause its pattern refuses, and at most FILL_SLACK
  characters of one an open pattern (``.*``, ``.+``) accepts. Known limit,
  chosen: a clause of fewer characters written into an open var (a
  restriction of 120 characters in BSD-3-Clause's disclaimer holder) is
  left out with it, and the text is named;
* a var is left out only where the words on both sides of it match the
  text: a word replaced beside it would else be charged only half (the old
  word compared, the new one left out in the fill); vars side by side
  ("THE COPYRIGHT HOLDER" then "DISCLAIM") are one, their fill fitting
  their patterns in turn;
* the fill is cut by token positions, never by characters per word: Han and
  kana have one token per character and no space between them;
* the similarity is that of the fixed text; the key is found less missing,
  a fill found up to the length of its List words: an exact copy keys the
  text's length whatever its fills, a long fill keys no near twin above it,
  and a short one keys no twin whose words there are longer above an exact
  copy of the true text;
* a look-alike against a masked hit (``exempt_runs(unbounded=True)``) has
  no touch or FILL_SLACK bound: a longer text with a long clause in a var
  still doubts a shorter text inside it.

Measurements: roadmap item 64, ``working-docs/implementation/whole-texts.md``
section 10.
"""

import re
from bisect import bisect_left, bisect_right
from collections.abc import Sequence
from typing import Final

from rapidfuzz.distance import Indel

from licenseid.templatevars import fill_matches
from licenseid.textcorpus import CodedText, RunChars, Span, VarRegion
from licenseid.textlocate import (
    NEAR_SIMILARITY,
    Block,
    Budget,
    Fit,
    allowed_distance,
    span_fit,
)

#: How many characters a fill may be longer than the List's words of its
#: var. The copyright lines and holders of the real files and of a 147-character
#: made-up holder line fit under it; a restrictive clause of 170 characters
#: written into an open var does not (100 loses 13 of the long holder lines;
#: 300 lets a 300-character clause through; whole-texts.md, section 10).
FILL_SLACK: Final = 150


class _Fills:
    """Where each text token the blocks match sits in the span."""

    def __init__(
        self, blocks: Sequence[Block], text_count: int, span_count: int
    ) -> None:
        self.blocks = blocks
        self.text_starts = [block[0] for block in blocks]
        self.text_count = text_count
        self.span_count = span_count

    def matched(self, token: int) -> bool:
        """Whether a block matches the text token *token*."""
        at = bisect_right(self.text_starts, token) - 1
        return at >= 0 and token < self.text_starts[at] + self.blocks[at][2]

    def touches(self, start: int, end: int) -> bool:
        """Whether the text tokens beside ``[start, end)`` are matched (or
        it starts or ends the text)."""
        return (start == 0 or self.matched(start - 1)) and (
            end == self.text_count or self.matched(end)
        )

    def before(self, token: int) -> int:
        """The span token after the last matched text token before *token*,
        or 0."""
        at = bisect_left(self.text_starts, token) - 1
        if at < 0:
            return 0
        text_start, span_start, size = self.blocks[at]
        return span_start + min(size, token - text_start)

    def after(self, token: int) -> int:
        """The span token of the first matched text token at *token* or
        after, or the span's end."""
        at = bisect_right(self.text_starts, token) - 1
        if at >= 0:
            text_start, span_start, size = self.blocks[at]
            if token < text_start + size:
                return span_start + token - text_start
        if at + 1 < len(self.blocks):
            return self.blocks[at + 1][1]
        return self.span_count


def _cut(text: str, chars: RunChars, dropped: Sequence[Span]) -> str:
    """*text* without its tokens in the *dropped* runs (sorted), the runs
    left joined by one space."""
    kept: list[str] = []
    at = 0
    for start, end in [*dropped, (chars.count, chars.count)]:
        if start > at:
            first, last = chars.bounds(at, start)
            kept.append(text[first:last])
        at = max(at, end)
    return " ".join(kept)


def _merged(runs: list[Span]) -> list[Span]:
    """*runs* sorted, those that touch or overlap made one."""
    merged: list[Span] = []
    for start, end in sorted(runs):
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


#: A pattern of any characters: ``.+``, ``.*``, ``.{0,20}`` (lazy or not).
_ANY: Final = re.compile(r"\.(?:([*+])|\{(\d*),(\d*)\})\??")


def _bounds(pattern: str) -> tuple[int, int | None] | None:
    """The least and most characters of *pattern* when it is any characters
    (``_ANY``; None for no most), else None."""
    found = _ANY.fullmatch(pattern)
    if found is None:
        return None
    sign, low, high = found.groups()
    if sign:
        return (1 if sign == "+" else 0), None
    return int(low or 0), (int(high) if high else None)


def chain_pattern(patterns: Sequence[str]) -> str:
    """One pattern for the fill of vars side by side, each white space
    between them optional (``templatevars.fill_matches``). A run of vars of
    any characters is one: ``(.+) (.+) (.+)`` read as three would try every
    way to cut a fill that fails (0.19 s on 252 characters)."""
    parts: list[str] = []
    run: list[tuple[int, int | None]] = []

    def close() -> None:
        if run:
            low = sum(bound[0] for bound in run)
            highs = [bound[1] for bound in run]
            high = (
                "" if None in highs else str(sum(h or 0 for h in highs) + len(run) - 1)
            )
            parts.append(f".{{{low},{high}}}")
            run.clear()

    for pattern in patterns:
        bounds = _bounds(pattern)
        if bounds is None:
            close()
            parts.append(pattern)
        else:
            run.append(bounds)
    close()
    return parts[0] if len(parts) == 1 else " ".join(f"({part})" for part in parts)


def _chains(regions: Sequence[VarRegion]) -> list[list[VarRegion]]:
    """*regions* (in order) in runs whose each next one starts where the
    one before ends: two vars side by side ("the copyright holder" then
    "disclaim" in MIT-CMU) have no matched word between them."""
    chains: list[list[VarRegion]] = []
    for region in regions:
        if chains and region.start == chains[-1][-1].end:
            chains[-1].append(region)
        else:
            chains.append([region])
    return chains


class Exempt:
    """The runs of text and span tokens left out of one fit
    (``exempt_runs``), what the fills miss of the List's words, and whether
    they are the text's own."""

    def __init__(
        self,
        text: str,
        blocks: Sequence[Block],
        text_chars: RunChars,
        span_text: str,
        unbounded: bool = False,
    ) -> None:
        span_chars = RunChars(span_text)
        self.unbounded = unbounded
        self.fills = _Fills(blocks, text_chars.count, span_chars.count)
        self.text = text
        self.text_chars = text_chars
        self.span_text = span_text
        self.span_chars = span_chars
        self.text_runs: list[Span] = []
        self.span_runs: list[Span] = []
        # What the fills miss of the List's words (``masked_fit``).
        self.short = 0
        # Whether every fill left out is the text's own words.
        self.own = True

    def take(self, regions: Sequence[VarRegion]) -> bool:
        """Leave out *regions* (side by side) and their one fill, if their
        neighbours touch them and the fill fits their patterns in turn,
        each white space between them optional."""
        start, end = regions[0].start, regions[-1].end
        if not self.unbounded and not self.fills.touches(start, end):
            return False
        low, high = self.fills.before(start), self.fills.after(end)
        if start == end and low == high:
            return False
        fill = ""
        if high > low:
            first, last = self.span_chars.bounds(low, high)
            fill = self.span_text[first:last]
        first, last = self.text_chars.bounds(start, end)
        pattern = chain_pattern([region.pattern for region in regions])
        if not self.unbounded and len(fill) > last - first + FILL_SLACK:
            return False
        if not fill_matches(pattern, fill):
            return False
        self.text_runs.append((start, end))
        self.span_runs.append((low, high))
        self.short += max(0, last - first - len(fill))
        self.own = self.own and fill == self.text[first:last]
        return True


def exempt_runs(
    coded: CodedText,
    blocks: Sequence[Block],
    text_chars: RunChars,
    span_text: str,
    unbounded: bool = False,
) -> Exempt:
    """What is left out (:class:`Exempt`): each variable part of *coded* (or
    run of parts side by side) whose matched neighbours touch it and whose
    fill (the span tokens between them) its pattern accepts, at most
    FILL_SLACK characters longer than its words in the text, and that fill.
    A run of parts whose fill fails is tried part by part. An empty part
    with an empty fill leaves nothing out. ``short`` is the characters the
    fills are shorter than their List words. *unbounded* (a look-alike
    against a masked hit) drops the touch and FILL_SLACK bounds: only the
    pattern holds a fill back."""
    exempt = Exempt(coded.text, blocks, text_chars, span_text, unbounded)
    for chain in _chains(coded.regions):
        if not exempt.take(chain) and len(chain) > 1:
            for region in chain:
                exempt.take([region])
    exempt.text_runs = _merged(exempt.text_runs)
    exempt.span_runs = _merged(exempt.span_runs)
    return exempt


def masked_fit(coded: CodedText, exempt: Exempt, budget: Budget) -> Fit | None:
    """The fit of *coded* in its span (``textlocate.span_fit``) with what
    *exempt* (``exempt_runs``) leaves out left out of both, or None under
    NEAR_SIMILARITY. Without a part left out it is the plain fit."""
    span_text = exempt.span_text
    budget.charge_word_cells(len(coded.regions) + len(exempt.fills.blocks))
    if not exempt.text_runs and not exempt.span_runs:
        return span_fit(coded, span_text, budget)
    fixed_text = _cut(coded.text, exempt.text_chars, exempt.text_runs)
    fixed_span = _cut(span_text, exempt.span_chars, exempt.span_runs)
    budget.charge_char_cells(len(fixed_text) * len(fixed_span))
    total = len(fixed_text) + len(fixed_span)
    allowed = allowed_distance(total, NEAR_SIMILARITY)
    distance = Indel.distance(fixed_text, fixed_span, score_cutoff=allowed)
    if distance > allowed:
        return None
    # Found less missing, each fill found up to the length of its List words:
    # an exact copy keys the text's length, a long fill no more, and a short
    # fill keys no look-alike whose words there are longer above the true
    # text (Cornell-Lossless-JPEG and PostgreSQL's core).
    key = len(fixed_span) + len(coded.text) - len(fixed_text) - distance
    key -= exempt.short
    return Fit(key, distance, total, masked=True, own=exempt.own)
