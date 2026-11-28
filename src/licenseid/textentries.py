# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The coded List texts of one database, read per candidate.

A call reads the stored entries (``licenseid.textstore``) of the texts it
searches or scores, not every text of the List: about 3 ms against 100 ms for
a first call of a process. What every search needs beside them (the
vocabulary, the patterns, the gram counts of the cores: the head) is read
once per database, and the names of the same-text groups come from the rows
(the index's IDs and ``licenseid.types.TextParts``), as a build takes them.

Each entry and the head are checked against ``text_code_checks``, which
``update`` writes in the transaction of the rows (:func:`write_checks`). A
head or an entry that fails its check drops the stored codes of that
database: the corpus is built in memory from the rows (``TextCorpus.build``,
without the regions of the variable parts, which the rows do not hold) and
never written back. The call that found it is given its corpus from there;
it does not restart.

One :class:`TextStore` per database, owned by ``dbcache.TableCache`` for one
generation of its reads. Its state (the head, the entries loaded, or the
corpus built) is kept for the ``last_update_datetime`` it was read at and is
replaced, never changed: loaded under a lock, published in one assignment.
Every corpus a search reads is cut from it and immutable (threads share
none of a call's). The reads of one call are made in the caller's
transaction (``dbcache.TableCache.snapshot``), so an ``update`` cannot land
between the postings, the ids and the entries.
"""

import sqlite3
import threading
from collections.abc import Collection, Mapping, Sequence
from contextlib import AbstractContextManager
from types import MappingProxyType
from typing import Final, NamedTuple, Protocol

from licenseid.textcorpus import CorpusEntry, TextCorpus, TextRow, group_names, own_core
from licenseid.textstore import (
    ENTRY_KINDS,
    HEAD,
    HEAD_KINDS,
    Head,
    RawEntry,
    entry_check,
    head_digest,
    read_entry,
    read_head,
)
from licenseid.types import TextParts

__all__ = ["Reads", "StoredTexts", "TextStore", "read_text_parts", "write_checks"]

#: Values bound to one query: SQLite's old limit is 999.
CHUNK: Final = 800
_UPDATED: Final = "SELECT value FROM db_metadata WHERE key = 'last_update_datetime'"


class Reads(Protocol):
    """What the store reads of one database (``dbcache.TableCache``): each in
    the caller's transaction."""

    def connection(self) -> AbstractContextManager[sqlite3.Connection]:
        """A connection for one query (``Connections.connection``)."""

    def index_rows(self) -> Mapping[str, int]:
        """The first ``license_texts`` rowid of each ID, in table order."""

    def text_parts(self) -> Mapping[str, TextParts]:
        """The core and the same-text group of each licence with one."""


def read_text_parts(conn: sqlite3.Connection) -> dict[str, TextParts]:
    """The core and the twins of each licence row that has a core or a twin,
    by ID (the first row wins)."""
    rows: list[tuple[str, str | None, int | None, str | None]] = conn.execute(
        "SELECT license_id, core_text, core_word_count, same_text"
        " FROM licenses ORDER BY rowid"
    ).fetchall()
    found: dict[str, TextParts] = {}
    for license_id, core, words, same in rows:
        if core is None and not same:
            continue
        found.setdefault(
            license_id,
            TextParts(
                core if core is not None and words else None,
                words if core is not None and words else None,
                tuple(same.split()) if same else (),
            ),
        )
    return found


def _group(license_id: str, parts: Mapping[str, TextParts]) -> tuple[str, ...]:
    """The same-text group of *license_id* as a build reads it: its twins,
    else itself alone."""
    part = parts.get(license_id)
    return (part.same_text if part else ()) or (license_id,)


class Groups(NamedTuple):
    """The same-text groups of the index's IDs, as a build groups them: the
    ID and index rowid whose rows give each group's text, by name; the name
    of each ID's group; and the cores and twins they were made with."""

    first: Mapping[str, tuple[str, int]]
    representatives: Mapping[str, str]
    parts: Mapping[str, TextParts]


def groups_of(index: Mapping[str, int], parts: Mapping[str, TextParts]) -> Groups:
    """The groups of the IDs of *index* (each ID's first rowid, in table
    order) with their *parts* (``textcorpus.group_names``)."""
    first, representatives = group_names((i, _group(i, parts)) for i in index)
    return Groups(
        MappingProxyType({name: (i, index[i]) for name, i in first.items()}),
        MappingProxyType(representatives),
        parts,
    )


def read_rows(
    conn: sqlite3.Connection, parts: Mapping[str, TextParts]
) -> list[TextRow]:
    """Every text of ``license_texts``, in table order (the first row of an
    ID wins, as a scan finds it), with its core and same-text group: what a
    build codes."""
    rows: list[tuple[str | None, str | None]] = conn.execute(
        "SELECT license_id, search_text FROM license_texts ORDER BY rowid"
    ).fetchall()
    texts: dict[str, str] = {}
    for license_id, text in rows:
        if license_id is not None and text:
            texts.setdefault(license_id, text)
    return [
        TextRow(
            license_id,
            text,
            parts[license_id].core if license_id in parts else None,
            _group(license_id, parts),
        )
        for license_id, text in texts.items()
    ]


def _marks(values: Sequence[object]) -> str:
    return ", ".join("?" * len(values))


def read_raw_entries(
    conn: sqlite3.Connection, names: Sequence[str], groups: Groups
) -> list[RawEntry]:
    """The rows of the groups *names*, as read: the text of each group's
    first licence, its core, its stored codes and regions and its check."""
    first = [groups.first[name] for name in names]
    texts: dict[int, object] = {}
    bodies: dict[str, dict[str, object]] = {name: {} for name in names}
    checks: dict[str, object] = {}
    for start in range(0, len(first), CHUNK):
        rowids = [rowid for _, rowid in first[start : start + CHUNK]]
        texts.update(
            conn.execute(
                "SELECT rowid, search_text FROM license_texts"
                f" WHERE rowid IN ({_marks(rowids)})",
                rowids,
            ).fetchall()
        )
    for start in range(0, len(names), CHUNK):
        part = names[start : start + CHUNK]
        query = (
            "SELECT kind, owner_id, body FROM text_codes"
            f" WHERE kind IN ({_marks(ENTRY_KINDS)}) AND owner_id IN ({_marks(part)})"
        )
        for kind, owner, body in conn.execute(query, (*ENTRY_KINDS, *part)):
            bodies[owner][kind] = body
        checks.update(
            conn.execute(
                "SELECT owner_id, digest FROM text_code_checks"
                f" WHERE owner_id IN ({_marks(part)})",
                part,
            ).fetchall()
        )
    raws = []
    for name, (license_id, rowid) in zip(names, first):
        text = texts.get(rowid)
        parts = groups.parts.get(license_id)
        core = None if parts is None else parts.core
        raws.append(
            RawEntry(name, text, own_core(text, core), bodies[name], checks.get(name))
        )
    return raws


def _head_rows(conn: sqlite3.Connection) -> tuple[dict[str, object], object]:
    """The bodies of the head's rows by kind, and its stored check."""
    bodies = dict(
        conn.execute(
            "SELECT kind, body FROM text_codes"
            f" WHERE kind IN ({_marks(HEAD_KINDS)}) AND owner_id = ?",
            (*HEAD_KINDS, HEAD),
        ).fetchall()
    )
    row = conn.execute(
        "SELECT digest FROM text_code_checks WHERE owner_id = ?", (HEAD,)
    ).fetchone()
    return bodies, None if row is None else row[0]


def _first_rowids(conn: sqlite3.Connection) -> dict[str, int]:
    """The first ``license_texts`` rowid of each ID, in table order."""
    found: dict[str, int] = {}
    for license_id, rowid in conn.execute(
        "SELECT license_id, rowid FROM license_texts ORDER BY rowid"
    ):
        if license_id is not None:
            found.setdefault(license_id, rowid)
    return found


def write_checks(conn: sqlite3.Connection, updated: str) -> None:
    """Store the checks of the head and of each entry of the texts and codes
    *conn* holds, with *updated* (the ``last_update_datetime`` written beside
    them): inside ``update``'s transaction, after the texts, licence rows and
    codes. Read back from those rows through the reads of a lookup, so a
    lookup of the same rows computes the same checks."""
    bodies, _ = _head_rows(conn)
    head = head_digest(
        updated, {kind: str(body) for kind, body in bodies.items() if body is not None}
    )
    parts = read_text_parts(conn)
    index = _first_rowids(conn)
    groups = groups_of(index, parts)
    raws = read_raw_entries(conn, list(groups.first), groups)
    checks = [(raw.name, entry_check(head, raw)) for raw in raws]
    conn.executemany(
        "INSERT INTO text_code_checks (owner_id, digest) VALUES (?, ?)",
        [(HEAD, head), *((name, check) for name, check in checks if check)],
    )


class _Stored(NamedTuple):
    """The stored codes of one database for one ``last_update_datetime``:
    the head and the entries loaded so far."""

    updated: object
    head: Head
    groups: Groups
    entries: Mapping[str, CorpusEntry]


class _Built(NamedTuple):
    """The corpus of one database built in memory from its rows, once a
    check of its stored codes failed, for one ``last_update_datetime``."""

    updated: object
    corpus: TextCorpus


_State = _Stored | _Built


def _built(
    conn: sqlite3.Connection, parts: Mapping[str, TextParts], updated: object
) -> _Built:
    """The state of a database whose stored codes failed a check: its corpus
    built in memory from the rows, never written back."""
    return _Built(updated, TextCorpus.build(read_rows(conn, parts)))


class TextStore:
    """The entries of one database read so far (module docstring)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._state: _State | None = None

    def state(self, reads: Reads) -> _State:
        """The state for the ``last_update_datetime`` of the caller's
        transaction: kept, else its head read (or the corpus built)."""
        with reads.connection() as conn:
            row = conn.execute(_UPDATED).fetchone()
            updated = None if row is None else row[0]
            state = self._state
            if state is not None and state.updated == updated:
                return state
            with self._lock:
                state = self._state
                if state is None or state.updated != updated:
                    state = self._first(conn, reads, updated)
                    self._state = state
                return state

    @staticmethod
    def _first(conn: sqlite3.Connection, reads: Reads, updated: object) -> _State:
        """The state of a database at *updated* before any entry is read."""
        bodies, check = _head_rows(conn)
        head = read_head(updated, bodies, check)
        if head is None:
            return _built(conn, reads.text_parts(), updated)
        groups = groups_of(reads.index_rows(), reads.text_parts())
        return _Stored(updated, head, groups, MappingProxyType({}))

    def cut(
        self, reads: Reads, state: _State, ids: Collection[str]
    ) -> tuple[TextCorpus, _State]:
        """The corpus of the same-text groups of the licences *ids*, in the
        order of the whole corpus (by group name), and the state it was cut
        from: their entries loaded first where *state* lacks one."""
        if isinstance(state, _Built):
            return state.corpus.cut(ids), state
        representatives = state.groups.representatives
        names = sorted({representatives[i] for i in ids if i in representatives})
        loaded: _State = state
        if any(name not in state.entries for name in names):
            loaded = self._load(reads, state, names)
        if isinstance(loaded, _Built):
            return loaded.corpus.cut(ids), loaded
        return (
            TextCorpus(
                vocabulary=loaded.head.vocabulary,
                entries=tuple(loaded.entries[name] for name in names),
                representatives=representatives,
            ),
            loaded,
        )

    def _load(self, reads: Reads, state: _Stored, names: Sequence[str]) -> _State:
        """*state* with the entries of *names* it lacks (those another thread
        loaded for the same time count), or the corpus built when one fails
        its check; published unless the database moved to another time."""
        with self._lock, reads.connection() as conn:
            current = self._state
            base: _State = state
            if current is not None and current.updated == state.updated:
                base = current
            if isinstance(base, _Built):
                return base
            missing = [name for name in names if name not in base.entries]
            if not missing:
                return base
            raws = read_raw_entries(conn, missing, base.groups)
            entries = dict(base.entries)
            for raw in raws:
                entry = read_entry(base.head, raw)
                if entry is None:
                    loaded: _State = _built(conn, base.groups.parts, base.updated)
                    break
                entries[raw.name] = entry
            else:
                loaded = base._replace(entries=MappingProxyType(entries))
            if current is None or current.updated == loaded.updated:
                self._state = loaded
            return loaded


class StoredTexts:
    """The texts one call reads from a database (``licenseid.textcandidates``
    asks it): the state is taken at the first question, in the call's
    transaction, and follows the loads of the call."""

    def __init__(self, store: TextStore, reads: Reads) -> None:
        self._store = store
        self._reads = reads
        self._state: _State | None = None

    def _current(self) -> _State:
        if self._state is None:
            self._state = self._store.state(self._reads)
        return self._state

    def core_grams(self, license_id: str) -> int | None:
        """The distinct word 3-grams of the core of *license_id*'s text, None
        when it has no core (or no text)."""
        state = self._current()
        if isinstance(state, _Built):
            entry = state.corpus.entry(license_id)
            return (
                None if entry is None or entry.core is None else entry.core.gram_count
            )
        name = state.groups.representatives.get(license_id)
        return None if name is None else state.head.core_grams.get(name)

    def corpus(self, ids: Collection[str]) -> TextCorpus:
        """The corpus of the same-text groups of the licences *ids*."""
        corpus, self._state = self._store.cut(self._reads, self._current(), ids)
        return corpus
