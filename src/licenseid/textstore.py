# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The stored form of a ``licenseid.textcorpus.TextCorpus``, and its checks.

The database stores the codes (``stored_rows``), so that a lookup reads the
entries of the texts it needs (``read_entry``) instead of coding every text
again. Each stored value is used only when it is what ``TextCorpus.build``
gives for the rows: ``update`` writes, beside the codes, a SHA-256 of the
head (``head_digest``: the coding, the copy of ``last_update_datetime`` the
rows were written with, the vocabulary, the patterns of the variable parts,
the gram counts of the cores) and one of each entry (``entry_digest``: the
head's, the group's name, its text and core as the rows hold them, and its
stored codes and regions). A read recomputes them from what it read; any
difference, a row of a wrong type or shape, or a row missing gives None, and
the caller then builds the corpus in memory. Pure functions of rows: the
database is read and written elsewhere (``licenseid.textentries``).

Standard library only, apart from ``licenseid.textcorpus`` and the tokens
of ``licenseid.textgrams``.
"""

import hashlib
import json
from collections.abc import Iterable, Mapping, Sequence
from types import MappingProxyType
from typing import Final, NamedTuple

from licenseid.textcorpus import (
    LAST_NUMBER,
    CodedText,
    CorpusEntry,
    TextCorpus,
    VarRegion,
    critical_codes,
    critical_counts_of_codes,
    word_code,
)
from licenseid.textgrams import TOKEN

#: Raised on a change to the coding (what a token is, which code point a word
#: gets, what a region is) that no change to the rows of a database shows:
#: stored codes of an older coding then fail their check and are built, not
#: read. Version 2: the regions of the variable parts (``TEXT_VARS``).
CODING_VERSION: Final = 2

#: One row of ``text_codes``: ``(kind, owner_id, body)``. The head is three
#: rows with no owner: the vocabulary (``WORDS``, a JSON list of the words in
#: code order), the ``match`` patterns of the variable parts (``PATTERNS``, a
#: JSON list) and the distinct word 3-grams of each core (``CORE_GRAMS``, a
#: JSON object by group name; ``licenseid.gramselect.is_held`` reads it for
#: texts it loads no entry of). Each text and core is one row of codes
#: (``TEXT``, ``CORE``; the owner is the name of its same-text group) and one
#: row of regions when it has some (``TEXT_VARS``, ``CORE_VARS``: a JSON list
#: of ``[start, end, pattern number]``).
StoredRow = tuple[str, str, str]
#: One row of ``text_code_checks``: ``(owner_id, digest)``; the head's owner
#: is ``HEAD``.
CheckRow = tuple[str, str]
WORDS: Final = "words"
PATTERNS: Final = "patterns"
CORE_GRAMS: Final = "coregrams"
TEXT: Final = "text"
CORE: Final = "core"
TEXT_VARS: Final = "textvars"
CORE_VARS: Final = "corevars"
HEAD: Final = ""
#: The kinds of the head, and those of an entry.
HEAD_KINDS: Final = (WORDS, PATTERNS, CORE_GRAMS)
ENTRY_KINDS: Final = (TEXT, CORE, TEXT_VARS, CORE_VARS)


def _digest(parts: Iterable[str]) -> str:
    """The SHA-256 (hex) of *parts*, each with its length in front, so that no
    two lists of parts join to the same bytes."""
    digest = hashlib.sha256()
    for part in parts:
        data = part.encode("utf-8", "surrogatepass")
        digest.update(len(data).to_bytes(8, "big"))
        digest.update(data)
    return digest.hexdigest()


def _present(body: str | None) -> str:
    """A stored body as a part of a digest: a row that is not there differs
    from every row that is."""
    return "" if body is None else "+" + body


def head_digest(updated: str, bodies: Mapping[str, str]) -> str:
    """The check of the head: the coding, the token rule, *updated* (the
    ``last_update_datetime`` the rows were written with) and the *bodies* of
    the kinds of ``HEAD_KINDS``. A rebuild of the rows, by ``update`` or by
    hand with a new time, so fails it, as the stamp of the postings does."""
    return _digest(
        (
            str(CODING_VERSION),
            TOKEN.pattern,
            updated,
            *(_present(bodies.get(kind)) for kind in HEAD_KINDS),
        )
    )


def entry_digest(
    head: str, name: str, text: str, core: str | None, bodies: Mapping[str, str]
) -> str:
    """The check of the entry of group *name*: the *head*'s check, its
    *text* and *core* as the rows hold them, and its stored *bodies* by kind
    (``ENTRY_KINDS``)."""
    return _digest(
        (
            head,
            name,
            text,
            _present(core),
            *(_present(bodies.get(kind)) for kind in ENTRY_KINDS),
        )
    )


def _json(value: object) -> str:
    return json.dumps(value, separators=(",", ":"))


def stored_rows(corpus: TextCorpus) -> list[StoredRow]:
    """The codes of *corpus* as rows of ``text_codes``: the head (the
    vocabulary in code order, the patterns of its regions, the gram counts of
    its cores), then the codes and regions of each text and core. The checks
    are written beside them (``licenseid.textentries.write_checks``)."""
    words = list(corpus.vocabulary)
    coded = [
        part
        for entry in corpus.entries
        for part in (entry.text, entry.core)
        if part is not None
    ]
    patterns = sorted({region.pattern for part in coded for region in part.regions})
    number = {pattern: at for at, pattern in enumerate(patterns)}
    core_grams = {
        entry.text.row_id: entry.core.gram_count
        for entry in corpus.entries
        if entry.core is not None
    }
    rows = [
        (WORDS, HEAD, _json(words)),
        (PATTERNS, HEAD, _json(patterns)),
        (CORE_GRAMS, HEAD, _json(core_grams)),
    ]
    for part in coded:
        rows.append((CORE if part.is_core else TEXT, part.row_id, part.codes))
        if part.regions:
            regions = [[r.start, r.end, number[r.pattern]] for r in part.regions]
            kind = CORE_VARS if part.is_core else TEXT_VARS
            rows.append((kind, part.row_id, _json(regions)))
    return rows


class Head(NamedTuple):
    """What every entry of one database reads: the check of the head, the
    vocabulary, the patterns, the counted critical codes and the gram counts
    of the cores by group name."""

    digest: str
    vocabulary: Mapping[str, str]
    patterns: tuple[str, ...]
    counted: tuple[tuple[str, ...], ...]
    core_grams: Mapping[str, int]


def _loaded(body: str) -> object:
    """*body* as JSON, or None when it is not."""
    try:
        return json.loads(body)
    except (ValueError, RecursionError):  # RecursionError: nested too deep
        return None


def _strings(value: object) -> list[str] | None:
    """*value* when it is a list of strings, else None."""
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        return None
    return value


def _counts(value: object) -> dict[str, int] | None:
    """*value* when it is an object of counts (not a JSON ``true``), else
    None."""
    if not isinstance(value, dict) or not all(
        type(v) is int and v >= 0  # pylint: disable=C0123
        for v in value.values()
    ):
        return None
    return value


def read_head(
    updated: object, bodies: Mapping[str, object], stored: object
) -> Head | None:
    """The head of the rows read: *updated* (``last_update_datetime``), the
    *bodies* of ``HEAD_KINDS`` and the *stored* check; None when one is
    missing or not text, the check differs (other rows, another coding), or a
    body does not read (the vocabulary a list of distinct strings, the
    patterns a list of strings, the gram counts an object of counts)."""
    texts = {kind: body for kind, body in bodies.items() if isinstance(body, str)}
    if (
        not isinstance(updated, str)
        or not isinstance(stored, str)
        or texts.keys() != set(HEAD_KINDS)
        or head_digest(updated, texts) != stored
    ):
        return None
    words = _strings(_loaded(texts[WORDS]))
    patterns = _strings(_loaded(texts[PATTERNS]))
    core_grams = _counts(_loaded(texts[CORE_GRAMS]))
    if words is None or patterns is None or core_grams is None:
        return None
    vocabulary = dict(zip(words, map(word_code, range(1, len(words) + 1))))
    if len(vocabulary) != len(words) or len(words) > LAST_NUMBER:
        return None
    return Head(
        stored,
        MappingProxyType(vocabulary),
        tuple(patterns),
        critical_codes(vocabulary),
        MappingProxyType(core_grams),
    )


def _parse_regions(
    body: str | None, length: int, patterns: Sequence[str]
) -> tuple[VarRegion, ...] | None:
    """The regions in *body* (none when it is None) of a text of *length*
    tokens, or None when it is not a JSON list of ``[start, end, pattern
    number]`` with ``0 <= start <= end <= length`` and a number of
    *patterns*."""
    if body is None:
        return ()
    loaded = _loaded(body)
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


class RawEntry(NamedTuple):
    """The rows of one same-text group as read: its *name*, its *text* (of
    its first licence's index row) and *core* (of that licence's row, None
    when it has none or it is the text), its stored *bodies* by kind (a kind
    with no row is not in it) and its stored *check*."""

    name: str
    text: object
    core: str | None
    bodies: Mapping[str, object]
    check: object


def _shaped(raw: RawEntry) -> dict[str, str] | None:
    """The bodies of *raw* when every value read is text, the text and each
    body are not empty, and they are those of an entry (:func:`_complete`);
    else None."""
    if not raw.text or not isinstance(raw.text, str):
        return None
    bodies = {kind: body for kind, body in raw.bodies.items() if body}
    if len(bodies) != len(raw.bodies):
        return None
    texts = {kind: body for kind, body in bodies.items() if isinstance(body, str)}
    if len(texts) != len(bodies) or not _complete(texts, raw.core is not None):
        return None
    return texts


def _complete(bodies: Mapping[str, str], has_core: bool) -> bool:
    """Whether *bodies* hold the codes of the text, and those of a core
    exactly when the row has one (its regions only with its codes)."""
    return (
        TEXT in bodies
        and has_core == (CORE in bodies)
        and (CORE in bodies or CORE_VARS not in bodies)
    )


def _coded(
    head: Head, raw: RawEntry, bodies: Mapping[str, str], kinds: tuple[str, str]
) -> CodedText | None:
    """The text (*kinds* ``TEXT``) or core of *raw* with its codes and
    regions, or None when the regions do not read."""
    codes = bodies[kinds[0]]
    regions = _parse_regions(bodies.get(kinds[1]), len(codes), head.patterns)
    if regions is None:
        return None
    return CodedText(
        row_id=raw.name,
        is_core=kinds[0] == CORE,
        text=str(raw.text) if kinds[0] == TEXT else str(raw.core),
        codes=codes,
        critical=critical_counts_of_codes(codes, head.counted),
        regions=regions,
    )


def entry_check(head: str, raw: RawEntry) -> str | None:
    """The check of the entry *raw* under the head's check *head*
    (:func:`entry_digest`), or None when its rows are of no entry: a row
    missing, not text or empty."""
    bodies = _shaped(raw)
    if bodies is None:
        return None
    return entry_digest(head, raw.name, str(raw.text), raw.core, bodies)


def read_entry(head: Head, raw: RawEntry) -> CorpusEntry | None:
    """The entry ``TextCorpus.build`` gives for the rows of *raw*, read from
    its stored codes and regions; None when they are not exactly those (a row
    missing, not text or empty, or one the check does not hold: other codes,
    another text, another head). Checked before anything is made of them: a
    region past the end of an edited text would raise."""
    bodies = _shaped(raw)
    if bodies is None or raw.check != entry_digest(
        head.digest, raw.name, str(raw.text), raw.core, bodies
    ):
        return None
    try:  # checked: a region past the text's last token is not expected
        text = _coded(head, raw, bodies, (TEXT, TEXT_VARS))
        core = (
            None if raw.core is None else _coded(head, raw, bodies, (CORE, CORE_VARS))
        )
    except (IndexError, ValueError):
        return None
    if text is None or (raw.core is not None and core is None):
        return None
    return CorpusEntry(text=text, core=core)
