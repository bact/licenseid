# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The stored form of a ``licenseid.textcorpus.TextCorpus``.

The database stores the codes (``stored_rows``), so that a process reads them
(``restore``) instead of coding every text again: 0.18 s once per process,
against about 15 ms. A stored check value (a SHA-256 of the List texts,
cores, codes and vocabulary, and of ``CODING_VERSION``) makes a restore give
the corpus ``TextCorpus.build`` gives or nothing: codes of other rows, or of
another coding, are never taken. Both are pure functions of rows; the
database is read and written elsewhere.

Standard library only, apart from ``licenseid.textcorpus``.
"""

import hashlib
import json
from collections.abc import Iterable, Sequence
from types import MappingProxyType
from typing import Final, NamedTuple

from licenseid.textcorpus import (
    LAST_NUMBER,
    TOKEN,
    CodedText,
    CorpusEntry,
    TextCorpus,
    TextRow,
    VarRegion,
    core_of_row,
    critical_codes,
    critical_counts_of_codes,
    group_rows,
    word_code,
)

#: Raised on a change to the coding (what a token is, which code point a word
#: gets, what a region is) that no change to the rows of a database shows: a
#: corpus stored by an older coding then fails its check and is built, not
#: read. Version 2: the regions of the variable parts (``TEXT_VARS``).
CODING_VERSION: Final = 2

#: One row of the stored corpus: ``(kind, owner_id, body)``. The vocabulary
#: is one row (``WORDS``, no owner), its check value another (``CHECK``, no
#: owner), the ``match`` patterns of the variable parts another (``PATTERNS``,
#: no owner, a JSON list), each text and core one row of codes (``TEXT``,
#: ``CORE``; the owner is the name of its same-text group) and one row of
#: regions when it has some (``TEXT_VARS``, ``CORE_VARS``: a JSON list of
#: ``[start, end, pattern number]``).
StoredRow = tuple[str, str, str]
WORDS: Final = "words"
CHECK: Final = "check"
PATTERNS: Final = "patterns"
TEXT: Final = "text"
CORE: Final = "core"
TEXT_VARS: Final = "textvars"
CORE_VARS: Final = "corevars"

# The kinds stored once, with no owner, and those stored per group.
_SINGLE: Final = (WORDS, CHECK, PATTERNS)
_OWNED: Final = (TEXT, CORE, TEXT_VARS, CORE_VARS)


class _Stored(NamedTuple):
    """The stored rows read: the vocabulary, the check value, the patterns
    and the codes and regions by ``(kind, owner)``."""

    words: list[str]
    check: str
    patterns: list[str]
    codes: dict[tuple[str, str], str]


def _parse_strings(body: str) -> list[str] | None:
    """The JSON list of strings in *body*, or None."""
    try:
        loaded = json.loads(body)
    except (ValueError, RecursionError):  # RecursionError: nested too deep
        return None
    if not isinstance(loaded, list) or not all(map(_is_str, loaded)):
        return None
    return loaded


def _parse_stored(stored: Iterable[StoredRow]) -> _Stored | None:
    """The vocabulary, the check value, the patterns and the codes of
    *stored*, or None when a row has a kind, owner or body that is not text
    (a BLOB read as bytes), is of no kind, repeated, or empty, or the
    vocabulary or the patterns are not a list of strings or a row of the
    vocabulary, the check or the patterns is missing."""
    single: dict[str, str] = {}
    codes: dict[tuple[str, str], str] = {}
    for row in stored:
        if not all(map(_is_str, row)):
            return None
        kind, owner, body = row
        if kind in _SINGLE and kind not in single and not owner:
            single[kind] = body
        elif kind in _OWNED and body and (kind, owner) not in codes:
            codes[(kind, owner)] = body
        else:
            return None
    if len(single) != len(_SINGLE):
        return None
    words = _parse_strings(single[WORDS])
    patterns = _parse_strings(single[PATTERNS])
    if words is None or patterns is None:
        return None
    return _Stored(words, single[CHECK], patterns, codes)


def _is_str(value: object) -> bool:
    return isinstance(value, str)


def _parse_regions(
    body: str | None, length: int, patterns: Sequence[str]
) -> tuple[VarRegion, ...] | None:
    """The regions in *body* (none when it is None) of a text of *length*
    tokens, or None when it is not a JSON list of ``[start, end, pattern
    number]`` with ``0 <= start <= end <= length`` and a number of
    *patterns*."""
    if body is None:
        return ()
    try:
        loaded = json.loads(body)
    except (ValueError, RecursionError):  # RecursionError: nested too deep
        return None
    if not isinstance(loaded, list):
        return None
    regions = [_region(item, length, patterns) for item in loaded]
    if None in regions:
        return None
    return tuple(region for region in regions if region is not None)


def _region(item: object, length: int, patterns: Sequence[str]) -> VarRegion | None:
    """One ``[start, end, pattern number]`` item as a region, or None."""
    if type(item) is not list or len(item) != 3:  # pylint: disable=C0123
        return None
    start, end, number = item
    # ``type(...) is int``: a JSON ``true`` is a bool, which is an int.
    if {type(start), type(end), type(number)} != {int}:
        return None
    if not (0 <= start <= end <= length and 0 <= number < len(patterns)):
        return None
    return VarRegion(start, end, patterns[number])


def _fingerprint(words: Sequence[str], entries: Iterable[CorpusEntry]) -> str:
    """The SHA-256 (hex) of the coding, the vocabulary *words* and, per
    entry, its group name, text, core, codes and regions: equal for the
    corpus ``build`` makes and the one ``restore`` reads from its rows only
    when every stored code and region is the one ``build`` gives. Each part
    has its length in front, so no two corpora join to the same bytes."""
    digest = hashlib.sha256()

    def add(part: str, encoding: str = "utf-8") -> None:
        data = part.encode(encoding, "surrogatepass")
        digest.update(len(data).to_bytes(8, "big"))
        digest.update(data)

    # Codes are Unicode beyond ASCII: UTF-32 is a copy, UTF-8 a conversion.
    def add_coded(coded: CodedText | None) -> None:
        add("" if coded is None else coded.text)  # a core is never empty
        add("" if coded is None else coded.codes, "utf-32-le")
        # Each pattern has its length in front: one may hold a line break.
        regions = () if coded is None else coded.regions
        add(
            "\n".join(
                f"{r.start} {r.end} {len(r.pattern)} {r.pattern}" for r in regions
            )
        )

    add(f"{CODING_VERSION}\n{TOKEN.pattern}\n{len(words)}")
    add("\n".join(words))  # a token holds no white space: no word has a "\n"
    for entry in entries:
        add(entry.text.row_id)
        add_coded(entry.text)
        add_coded(entry.core)
    return digest.hexdigest()


class _Reader(NamedTuple):
    """What every entry of a restore reads: the stored codes and regions
    (taken out as read), the patterns and the counted critical codes."""

    codes: dict[tuple[str, str], str]
    patterns: list[str]
    counted: tuple[tuple[str, ...], ...]

    def coded(self, name: str, text: str, kinds: tuple[str, str]) -> CodedText | None:
        """*text* of group *name* with its stored codes and regions of
        *kinds*, or None when it has no codes or its regions do not read."""
        body = self.codes.pop((kinds[0], name), None)
        if body is None:
            return None  # regions without codes stay: a leftover row
        regions = _parse_regions(
            self.codes.pop((kinds[1], name), None), len(body), self.patterns
        )
        if regions is None:
            return None
        return CodedText(
            row_id=name,
            is_core=kinds[0] == CORE,
            text=text,
            codes=body,
            critical=critical_counts_of_codes(body, self.counted),
            regions=regions,
        )


def _stored_entry(row: TextRow, name: str, reader: _Reader) -> CorpusEntry | None:
    """The entry of group *name* from the stored rows (taken out of the
    reader), or None when its text, or a core it needs, has none, or a core
    or regions are stored that *row* does not have."""
    core = core_of_row(row)
    text = reader.coded(name, row.text, (TEXT, TEXT_VARS))
    stored_core = reader.coded(name, core or "", (CORE, CORE_VARS))
    if text is None or (core is None) != (stored_core is None):
        return None
    return CorpusEntry(text=text, core=stored_core)


def stored_rows(corpus: TextCorpus) -> list[StoredRow]:
    """The codes of *corpus* as rows to store: the vocabulary (its words in
    code order, as JSON), its check value, the patterns of its regions, and
    the codes and regions of each text and core. ``restore`` reads them
    back."""
    words = list(corpus.vocabulary)
    coded = [
        part
        for entry in corpus.entries
        for part in (entry.text, entry.core)
        if part is not None
    ]
    patterns = sorted({region.pattern for part in coded for region in part.regions})
    number = {pattern: at for at, pattern in enumerate(patterns)}
    rows = [
        (WORDS, "", _json(words)),
        (CHECK, "", _fingerprint(words, corpus.entries)),
        (PATTERNS, "", _json(patterns)),
    ]
    for part in coded:
        rows.append((CORE if part.is_core else TEXT, part.row_id, part.codes))
        if part.regions:
            regions = [[r.start, r.end, number[r.pattern]] for r in part.regions]
            kind = CORE_VARS if part.is_core else TEXT_VARS
            rows.append((kind, part.row_id, _json(regions)))
    return rows


def _json(value: object) -> str:
    return json.dumps(value, separators=(",", ":"))


def restore(rows: Iterable[TextRow], stored: Iterable[StoredRow]) -> TextCorpus | None:
    """The corpus ``TextCorpus.build(rows)`` gives, read from the *stored*
    rows of that corpus instead of coded again, regions included (*rows*
    have none: the templates are not in the database); None when *stored*
    is not exactly the codes of *rows* (empty, damaged, of other rows or of
    another coding: its check value then differs): the caller then builds,
    without regions."""
    parsed = _parse_stored(stored)
    if parsed is None:
        return None
    words, check, patterns, codes = parsed
    vocabulary = dict(zip(words, map(word_code, range(1, len(words) + 1))))
    if len(vocabulary) != len(words) or len(words) > LAST_NUMBER:
        return None
    reader = _Reader(codes, patterns, critical_codes(vocabulary))
    first, representatives = group_rows(rows)
    entries = []
    for name in sorted(first):
        entry = _stored_entry(first[name], name, reader)
        if entry is None:
            return None
        entries.append(entry)
    if codes or check != _fingerprint(words, entries):
        return None  # a text no row of *rows* holds, or other codes
    return TextCorpus(
        vocabulary=MappingProxyType(vocabulary),
        entries=tuple(entries),
        representatives=MappingProxyType(representatives),
    )
