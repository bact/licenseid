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
search reads it from any thread. Cores are coded at build time.

The database stores the codes (``TextCorpus.stored_rows``), so that a process
reads them (``TextCorpus.restore``) instead of coding every text again: 0.18 s
once per process, against about 15 ms. A stored check value (a SHA-256 of the
List texts, cores, codes and vocabulary, and of ``CODING_VERSION``) makes a
restore give the corpus ``build`` gives or nothing: codes of other rows, or of
another coding, are never taken. Both are pure functions of rows; the database
is read and written elsewhere.

Standard library only, apart from ``licenseid.similarity``'s list of
critical words.
"""

import hashlib
import json
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
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
_TOKEN: Final = re.compile(f"[{_CJK}]|[^\\s{_CJK}]+")

# Word numbers run from 1 (0 is UNKNOWN); a code point is never a surrogate,
# which a str may hold but RapidFuzz and the encoders refuse.
_SURROGATES: Final = 0xD800
_SURROGATE_COUNT: Final = 0x800
_LAST_NUMBER: Final = 0x10FFFF - _SURROGATE_COUNT

#: The critical words in a fixed order, for the counts of a text and a span.
CRITICAL_ORDER: Final = tuple(sorted(CRITICAL_TOKENS))
#: Words counted with a critical word: "Neither A nor B may be used" says
#: what "A and B may not be used" says (a common rewording of BSD-3-Clause),
#: so the two count alike; a copy that drops either still differs.
COUNTED_WITH: Final = MappingProxyType({"not": ("not", "neither")})
_CLASSES: Final = tuple(COUNTED_WITH.get(word, (word,)) for word in CRITICAL_ORDER)

Span = tuple[int, int]

#: Raised on a change to the coding (what a token is, which code point a word
#: gets) that no change to the rows of a database shows: a corpus stored by an
#: older coding then fails its check and is built, not read.
CODING_VERSION: Final = 1

#: One row of the stored corpus: ``(kind, owner_id, body)``. The vocabulary
#: is one row (``WORDS``, no owner), its check value another (``CHECK``, no
#: owner), each text and core one row of codes (``TEXT``, ``CORE``; the owner
#: is the name of its same-text group).
StoredRow = tuple[str, str, str]
WORDS: Final = "words"
CHECK: Final = "check"
TEXT: Final = "text"
CORE: Final = "core"


def split_words(text: str) -> list[str]:
    """The tokens of *text*: its words, and each Han or kana character
    alone. ASCII text is split on white space only (the fast path)."""
    if text.isascii():
        return text.split()
    return _TOKEN.findall(text)


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
    for match in _TOKEN.finditer(text):
        words.append(match.group())
        spans.append(match.span())
        if len(words) > limit:
            break
    return words, spans


def token_spans(text: str) -> list[Span]:
    """Where each token of *text* (as ``split_words``) starts and ends."""
    return [match.span() for match in _TOKEN.finditer(text)]


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
                return
        self._spans = token_spans(text)

    def of(self, start: int, end: int) -> int:
        """The characters of tokens *start* to *end* (end > start)."""
        if self._sums is not None:
            return self._sums[end] - self._sums[start] + end - start - 1
        return self._spans[end - 1][1] - self._spans[start][0]


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


def _code(number: int) -> str:
    """The code point of the word numbered *number* (from 1)."""
    number = min(number, _LAST_NUMBER)
    return chr(number if number < _SURROGATES else number + _SURROGATE_COUNT)


@dataclass(frozen=True)
class TextRow:
    """One licence of the List: its normalised text, its core (the text
    without its optional parts, ``licenseid.coretext``) and the IDs whose
    text is the very same (``same_text``, itself included)."""

    license_id: str
    text: str
    core: str | None
    group: tuple[str, ...]


@dataclass(frozen=True)
class CodedText:
    """A text (or core) of the List: its characters, its word codes and its
    counts of critical words. *row_id* names its same-text group."""

    row_id: str
    is_core: bool
    text: str
    codes: str
    critical: tuple[int, ...]


@dataclass(frozen=True)
class CorpusEntry:
    """The text of one same-text group, and its core when it differs."""

    text: CodedText
    core: CodedText | None


class _Vocabulary:
    """Word codes in the order words are first seen (build time only)."""

    def __init__(self) -> None:
        self.codes: dict[str, str] = {}

    def code(self, text: str, row_id: str, is_core: bool) -> CodedText:
        """*text* coded, new words numbered as they come."""
        words = split_words(text)
        codes = self.codes
        for word in words:
            if word not in codes:
                codes[word] = _code(len(codes) + 1)
        return CodedText(
            row_id=row_id,
            is_core=is_core,
            text=text,
            codes="".join([codes[word] for word in words]),
            critical=critical_counts(words),
        )


def _representative(row: TextRow) -> str:
    """The ID that names *row*'s same-text group: the least of its IDs."""
    return min((row.license_id, *row.group))


def _groups(rows: Iterable[TextRow]) -> tuple[dict[str, TextRow], dict[str, str]]:
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


def _core_of(row: TextRow) -> str | None:
    """*row*'s core, or None when it has none or it is the text."""
    return row.core if row.core and row.core != row.text else None


class _Stored(NamedTuple):
    """The stored rows read: the vocabulary, the check value and the codes
    by ``(kind, owner)``."""

    words: list[str]
    check: str
    codes: dict[tuple[str, str], str]


def _parse_words(body: str) -> list[str] | None:
    """The vocabulary in *body* (a JSON list of strings), or None."""
    try:
        loaded = json.loads(body)
    except ValueError:
        return None
    if not isinstance(loaded, list) or not all(map(_is_str, loaded)):
        return None
    return loaded


def _parse_stored(stored: Iterable[StoredRow]) -> _Stored | None:
    """The vocabulary, the check value and the codes of *stored*, or None
    when a row has a kind, owner or body that is not text (a BLOB read as
    bytes), is of no kind, repeated, or empty, or the vocabulary is not a list
    of strings or a row of the vocabulary or the check is missing."""
    words: list[str] | None = None
    check: str | None = None
    codes: dict[tuple[str, str], str] = {}
    for row in stored:
        if not all(map(_is_str, row)):
            return None
        kind, owner, body = row
        if kind == WORDS and words is None and not owner:
            words = _parse_words(body)
            if words is None:
                return None
        elif kind == CHECK and check is None and not owner:
            check = body
        elif kind in (TEXT, CORE) and body and (kind, owner) not in codes:
            codes[(kind, owner)] = body
        else:
            return None
    if words is None or check is None:
        return None
    return _Stored(words, check, codes)


def _is_str(value: object) -> bool:
    return isinstance(value, str)


def _fingerprint(words: Sequence[str], entries: Iterable[CorpusEntry]) -> str:
    """The SHA-256 (hex) of the coding, the vocabulary *words* and, per
    entry, its group name, text, core and codes: equal for the corpus
    ``build`` makes and the one ``restore`` reads from its rows only when
    every stored code is the one ``build`` gives. Each part has its length
    in front, so no two corpora join to the same bytes."""
    digest = hashlib.sha256()

    def add(part: str, encoding: str = "utf-8") -> None:
        data = part.encode(encoding, "surrogatepass")
        digest.update(len(data).to_bytes(8, "big"))
        digest.update(data)

    # Codes are Unicode beyond ASCII: UTF-32 is a copy, UTF-8 a conversion.
    def add_codes(codes: str) -> None:
        add(codes, "utf-32-le")

    add(f"{CODING_VERSION}\n{_TOKEN.pattern}\n{len(words)}")
    add("\n".join(words))  # a token holds no white space: no word has a "\n"
    for entry in entries:
        add(entry.text.row_id)
        add(entry.text.text)
        add_codes(entry.text.codes)
        core = entry.core
        add("" if core is None else core.text)  # a core is never empty
        add_codes("" if core is None else core.codes)
    return digest.hexdigest()


def _stored_entry(
    row: TextRow,
    name: str,
    codes: dict[tuple[str, str], str],
    counted: tuple[tuple[str, ...], ...],
) -> CorpusEntry | None:
    """The entry of group *name* from the stored *codes* (taken out of it),
    or None when its text, or a core it needs, has none, or a core is stored
    that *row* does not have."""
    core = _core_of(row)
    text_codes = codes.pop((TEXT, name), None)
    core_codes = codes.pop((CORE, name), None)
    if text_codes is None or (core is None) != (core_codes is None):
        return None

    def coded(text: str, body: str, is_core: bool) -> CodedText:
        return CodedText(
            row_id=name,
            is_core=is_core,
            text=text,
            codes=body,
            critical=critical_counts_of_codes(body, counted),
        )

    return CorpusEntry(
        text=coded(row.text, text_codes, False),
        core=None
        if core is None or core_codes is None
        else coded(core, core_codes, True),
    )


@dataclass(frozen=True)
class TextCorpus:
    """Every List text with a non-empty text, one entry per same-text group
    (twins are scanned once), coded with one vocabulary. Immutable."""

    vocabulary: Mapping[str, str]
    entries: tuple[CorpusEntry, ...]
    representatives: Mapping[str, str]

    @classmethod
    def build(cls, rows: Iterable[TextRow]) -> "TextCorpus":
        """The corpus of *rows*. A group is coded from the first of its rows;
        a core equal to the text, or empty, is dropped."""
        first, representatives = _groups(rows)
        vocabulary = _Vocabulary()
        entries = []
        for name in sorted(first):
            row = first[name]
            core = _core_of(row)
            entries.append(
                CorpusEntry(
                    text=vocabulary.code(row.text, name, False),
                    core=None if core is None else vocabulary.code(core, name, True),
                )
            )
        return cls(
            vocabulary=MappingProxyType(vocabulary.codes),
            entries=tuple(entries),
            representatives=MappingProxyType(representatives),
        )

    def stored_rows(self) -> list[StoredRow]:
        """The codes of this corpus as rows to store: the vocabulary (its
        words in code order, as JSON), its check value and the codes of each
        text and core. ``restore`` reads them back."""
        words = list(self.vocabulary)
        rows = [
            (WORDS, "", json.dumps(words, separators=(",", ":"))),
            (CHECK, "", _fingerprint(words, self.entries)),
        ]
        for entry in self.entries:
            rows.append((TEXT, entry.text.row_id, entry.text.codes))
            if entry.core is not None:
                rows.append((CORE, entry.core.row_id, entry.core.codes))
        return rows

    @classmethod
    def restore(
        cls, rows: Iterable[TextRow], stored: Iterable[StoredRow]
    ) -> "TextCorpus | None":
        """The corpus ``build(rows)`` gives, read from the *stored* rows of
        that corpus instead of coded again; None when *stored* is not exactly
        the codes of *rows* (empty, damaged, of other rows or of another
        coding: its check value then differs): the caller then builds."""
        parsed = _parse_stored(stored)
        if parsed is None:
            return None
        words, check, codes = parsed
        vocabulary = dict(zip(words, map(_code, range(1, len(words) + 1))))
        if len(vocabulary) != len(words) or len(words) > _LAST_NUMBER:
            return None
        counted = critical_codes(vocabulary)
        first, representatives = _groups(rows)
        entries = []
        for name in sorted(first):
            entry = _stored_entry(first[name], name, codes, counted)
            if entry is None:
                return None
            entries.append(entry)
        if codes or check != _fingerprint(words, entries):
            return None  # a text no row of *rows* holds, or other codes
        return cls(
            vocabulary=MappingProxyType(vocabulary),
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
