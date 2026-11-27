# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The List texts as word codes, for the search of whole texts in an input.

Every distinct word of the List texts gets one code point, so a text of
7,000 words becomes a string of 7,000 characters: RapidFuzz then compares
words, not characters, and a word 5-gram is a slice of 5 characters (a cheap
dictionary key). The character texts are kept too: the last check of a hit
compares characters (``licenseid.textlocate``).

A corpus is built once (``TextCorpus.build``) and never changed after: a
search reads it from any thread. Cores are coded at build time. The database
stores it (``licenseid.textstore``).

Standard library only, apart from ``licenseid.similarity``'s list of
critical words.
"""

import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from itertools import accumulate
from types import MappingProxyType
from typing import Final, NamedTuple

from licenseid.similarity import CRITICAL_TOKENS

#: The code of an input word that no List text holds: it matches nothing.
UNKNOWN: Final = "\0"

# Han and kana are written without spaces between words, so each of their
# characters is a token of its own; a phrase of 60 characters as one "word"
# would make a one-character change a whole-word miss.
_CJK: Final = "぀-ヿ㐀-䶿一-鿿豈-﫿"
TOKEN: Final = re.compile(f"[{_CJK}]|[^\\s{_CJK}]+")

# Word numbers run from 1 (0 is UNKNOWN); a code point is never a surrogate,
# which a str may hold but RapidFuzz and the encoders refuse.
_SURROGATES: Final = 0xD800
_SURROGATE_COUNT: Final = 0x800
LAST_NUMBER: Final = 0x10FFFF - _SURROGATE_COUNT

#: The critical words in a fixed order, for the counts of a text and a span.
CRITICAL_ORDER: Final = tuple(sorted(CRITICAL_TOKENS))
#: Words counted with a critical word: "Neither A nor B may be used" says
#: what "A and B may not be used" says (a common rewording of BSD-3-Clause),
#: so the two count alike; a copy that drops either still differs.
COUNTED_WITH: Final = MappingProxyType({"not": ("not", "neither")})
_CLASSES: Final = tuple(COUNTED_WITH.get(word, (word,)) for word in CRITICAL_ORDER)

Span = tuple[int, int]


def split_words(text: str) -> list[str]:
    """The tokens of *text*: its words, and each Han or kana character
    alone. ASCII text is split on white space only (the fast path)."""
    if text.isascii():
        return text.split()
    return TOKEN.findall(text)


def input_tokens(text: str, limit: int) -> tuple[list[str], list[Span] | None]:
    """The tokens of *text* (as ``split_words``) and, for non-ASCII text,
    where each starts and ends in *text*: Han and kana tokens have no space
    between them, so a span of tokens is a slice of *text*, not a join.

    The count stops after ``limit + 1`` tokens of non-ASCII text: a caller
    that refuses more than *limit* then pays nothing for a long blob."""
    if text.isascii():
        return text.split(), None
    words: list[str] = []
    spans: list[Span] = []
    for match in TOKEN.finditer(text):
        words.append(match.group())
        spans.append(match.span())
        if len(words) > limit:
            break
    return words, spans


def token_spans(text: str) -> list[Span]:
    """Where each token of *text* (as ``split_words``) starts and ends."""
    return [match.span() for match in TOKEN.finditer(text)]


class RunChars:
    """The characters of a run of tokens of one text, from the start of its
    first token to the end of its last."""

    def __init__(self, text: str) -> None:
        self._sums: list[int] | None = None
        self._spans: list[Span] = []
        if text.isascii():
            words = text.split()
            sums = list(accumulate(map(len, words), initial=0))
            # One space between words and none at the ends (every ASCII text
            # of the List is so normalised): no position of each token needed.
            if sums[-1] + len(words) - 1 == len(text):
                self._sums = sums
                self.count = len(words)
                return
        self._spans = token_spans(text)
        #: How many tokens the text has.
        self.count = len(self._spans)

    def bounds(self, start: int, end: int) -> Span:
        """Where tokens *start* to *end* (end > start) start and end in the
        text, in characters."""
        if self._sums is not None:
            return self._sums[start] + start, self._sums[end] + end - 1
        return self._spans[start][0], self._spans[end - 1][1]

    def of(self, start: int, end: int) -> int:
        """The characters of tokens *start* to *end* (end > start)."""
        first, last = self.bounds(start, end)
        return last - first


def critical_counts(words: Sequence[str]) -> tuple[int, ...]:
    """How often *words* hold each of CRITICAL_ORDER, with the words
    COUNTED_WITH it: a copy that drops a "not" says the opposite, however
    close its characters."""
    return tuple(sum(map(words.count, counted)) for counted in _CLASSES)


def critical_codes(vocabulary: Mapping[str, str]) -> tuple[tuple[str, ...], ...]:
    """The codes of the words counted with each critical word (the words no
    List text holds have none): what ``critical_counts_of_codes`` counts."""
    return tuple(
        tuple(vocabulary[word] for word in counted if word in vocabulary)
        for counted in _CLASSES
    )


def critical_counts_of_codes(
    codes: str, counted: tuple[tuple[str, ...], ...]
) -> tuple[int, ...]:
    """What ``critical_counts`` gives for the words *codes* stand for: the
    same count, from the codes and the *counted* codes of the vocabulary
    (``critical_codes``)."""
    return tuple(sum(map(codes.count, classes)) for classes in counted)


def word_code(number: int) -> str:
    """The code point of the word numbered *number* (from 1)."""
    number = min(number, LAST_NUMBER)
    return chr(number if number < _SURROGATES else number + _SURROGATE_COUNT)


class VarRegion(NamedTuple):
    """A variable part of a text (``licenseid.templatevars``): its tokens
    *start* to *end* (*start* == *end*: a point where the template has an
    empty one) and the ``match`` *pattern* the List gives it."""

    start: int
    end: int
    pattern: str


@dataclass(frozen=True)
class TextRow:
    """One licence of the List: its normalised text, its core (the text
    without its optional parts, ``licenseid.coretext``), the IDs whose text
    is the very same (``same_text``, itself included) and the variable parts
    of the text and of the core (``licenseid.templatevars``; none unknown)."""

    license_id: str
    text: str
    core: str | None
    group: tuple[str, ...]
    regions: tuple[VarRegion, ...] = ()
    core_regions: tuple[VarRegion, ...] = ()


@dataclass(frozen=True)
class CodedText:
    """A text (or core) of the List: its characters, its word codes, its
    counts of critical words and the *regions* of its template's variable
    parts (none when unknown). *row_id* names its same-text group."""

    row_id: str
    is_core: bool
    text: str
    codes: str
    critical: tuple[int, ...]
    regions: tuple[VarRegion, ...] = ()
    #: The characters of the text with its variable parts cut out as
    #: ``textmask`` cuts them (the pieces left joined by one space): the
    #: least a copy with every part left empty has to fit (``wholetexts``).
    least: int = field(init=False, compare=False, repr=False)

    def __post_init__(self) -> None:
        least = len(self.text)
        if self.regions:
            chars = RunChars(self.text)
            for start, end in _token_runs(self.regions):
                # From the end of the token before to the start of the one
                # after (or the text's end); one space joins what is left
                # on both sides (none between Han tokens before the cut).
                left = chars.bounds(start - 1, start)[1] if start else 0
                inner = end < chars.count
                right = chars.bounds(end, end + 1)[0] if inner else len(self.text)
                least -= right - left - (1 if start and inner else 0)
        object.__setattr__(self, "least", least)


def _token_runs(regions: Sequence[VarRegion]) -> list[Span]:
    """The token runs of *regions* that hold a token, sorted, those that
    touch or overlap made one."""
    runs: list[Span] = []
    for region in sorted(regions):
        if region.end <= region.start:
            continue
        if runs and region.start <= runs[-1][1]:
            runs[-1] = (runs[-1][0], max(runs[-1][1], region.end))
        else:
            runs.append((region.start, region.end))
    return runs


@dataclass(frozen=True)
class CorpusEntry:
    """The text of one same-text group, and its core when it differs."""

    text: CodedText
    core: CodedText | None


class _Vocabulary:
    """Word codes in the order words are first seen (build time only)."""

    def __init__(self) -> None:
        self.codes: dict[str, str] = {}

    def code(
        self,
        text: str,
        row_id: str,
        is_core: bool,
        regions: tuple[VarRegion, ...] = (),
    ) -> CodedText:
        """*text* coded, new words numbered as they come."""
        words = split_words(text)
        codes = self.codes
        for word in words:
            if word not in codes:
                codes[word] = word_code(len(codes) + 1)
        return CodedText(
            row_id=row_id,
            is_core=is_core,
            text=text,
            codes="".join([codes[word] for word in words]),
            critical=critical_counts(words),
            regions=regions,
        )


def _representative(row: TextRow) -> str:
    """The ID that names *row*'s same-text group: the least of its IDs."""
    return min((row.license_id, *row.group))


def group_rows(rows: Iterable[TextRow]) -> tuple[dict[str, TextRow], dict[str, str]]:
    """The first row of each same-text group by its name, and the name of the
    group of each ID. A row with no text has none."""
    first: dict[str, TextRow] = {}
    representatives: dict[str, str] = {}
    for row in rows:
        if not row.text:
            continue
        name = _representative(row)
        first.setdefault(name, row)
        for member in (row.license_id, *row.group):
            representatives.setdefault(member, name)
    return first, representatives


def core_of_row(row: TextRow) -> str | None:
    """*row*'s core, or None when it has none or it is the text."""
    return row.core if row.core and row.core != row.text else None


@dataclass(frozen=True)
class TextCorpus:
    """Every List text with a non-empty text, one entry per same-text group
    (twins are scanned once), coded with one vocabulary. Immutable."""

    vocabulary: Mapping[str, str]
    entries: tuple[CorpusEntry, ...]
    representatives: Mapping[str, str]

    @classmethod
    def build(cls, rows: Iterable[TextRow]) -> "TextCorpus":
        """The corpus of *rows*. A group is coded from the first of its rows,
        with its regions; a core equal to the text, or empty, is dropped."""
        first, representatives = group_rows(rows)
        vocabulary = _Vocabulary()
        entries = []
        for name in sorted(first):
            row = first[name]
            core = core_of_row(row)
            entries.append(
                CorpusEntry(
                    text=vocabulary.code(row.text, name, False, row.regions),
                    core=None
                    if core is None
                    else vocabulary.code(core, name, True, row.core_regions),
                )
            )
        return cls(
            vocabulary=MappingProxyType(vocabulary.codes),
            entries=tuple(entries),
            representatives=MappingProxyType(representatives),
        )

    def representative(self, license_id: str) -> str | None:
        """The ID that names *license_id*'s same-text group, or None when
        the corpus has no text of it."""
        return self.representatives.get(license_id)

    def encode(self, words: Iterable[str]) -> str:
        """*words* as codes; a word no List text holds is UNKNOWN."""
        get = self.vocabulary.get
        return "".join([get(word, UNKNOWN) for word in words])
